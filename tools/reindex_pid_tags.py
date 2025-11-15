"""Re-index PID tags from ingestion artifacts to OpenSearch

This script:
1. Reads doc_id_map.json to get all PDF paths
2. Extracts tags from CAD-like PDFs only
3. Bulk indexes to pvcfc_pid_tags index in OpenSearch
"""
import json
import os
import sys
from pathlib import Path

from loguru import logger

# Fix protobuf version conflict: use pure-Python implementation
# This enables Google Cloud Vision OCR compatibility
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from opensearchpy import OpenSearch, helpers

from app.core.config import settings
from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor


def load_doc_id_map(artifacts_dir: Path):
    """Load doc_id_map.json"""
    map_file = artifacts_dir / "doc_id_map.json"

    if not map_file.exists():
        logger.error(f"doc_id_map.json not found: {map_file}")
        return {}

    with open(map_file, encoding="utf-8") as f:
        return json.load(f)


def is_cad_like_pdf(pdf_path: Path) -> bool:
    """Check if PDF is CAD-like (P&ID)"""
    filename = pdf_path.name.lower()

    # Check for P&ID keywords
    pid_keywords = ["p&id", "pid", "ammonia", "urea", "drawing"]

    return any(kw in filename for kw in pid_keywords)


def extract_tags_from_pdf(pdf_path: Path, doc_id: str):
    """Extract all tags from a PDF"""
    logger.info(f"Extracting tags from: {pdf_path.name}")

    extractor = TagExtractor()
    layout_builder = PageLayoutBuilder()

    import fitz

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    all_tags = []

    for page_num in range(1, total_pages + 1):
        try:
            layout = layout_builder.build_layout(pdf_path, page_num, doc_id)
            page_tags = extractor.extract_tags(layout)

            if page_tags:
                all_tags.extend(page_tags)
                if page_num % 10 == 0:
                    logger.info(
                        f"  Page {page_num}/{total_pages}: {len(all_tags)} total tags"
                    )

        except Exception as e:
            logger.warning(f"  Page {page_num}: Error - {e}")

    logger.info(f"  Total: {len(all_tags)} tags from {total_pages} pages")
    return all_tags


def create_opensearch_client():
    """Create OpenSearch client"""
    return OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )


def recreate_tags_index(client: OpenSearch, index_name: str):
    """Delete and recreate tags index with proper mapping"""

    # Delete old index
    if client.indices.exists(index=index_name):
        logger.info(f"Deleting existing index: {index_name}")
        client.indices.delete(index=index_name)

    # Create new index with mapping
    mapping = {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
                "tag": {"type": "keyword"},
                "unit": {"type": "keyword"},
                "prefix": {"type": "keyword"},
                "suffix": {"type": "keyword"},
                "variant": {"type": "keyword"},
                "annotation": {"type": "keyword"},
                "bbox": {"type": "float"},
                "confidence": {"type": "float"},
                "has_variant": {"type": "boolean"},
                "has_annotation": {"type": "boolean"},
            }
        },
    }

    client.indices.create(index=index_name, body=mapping)
    logger.info(f"Created new index: {index_name}")


def bulk_index_tags(client: OpenSearch, tags, index_name: str):
    """Bulk index tags to OpenSearch"""

    actions = []
    for tag in tags:
        # Create unique ID
        tag_id = f"{tag.doc_id}_p{tag.page}_{tag.tag.replace(' ', '_')}"

        action = {
            "_op_type": "index",
            "_index": index_name,
            "_id": tag_id,
            "_source": {
                "doc_id": tag.doc_id,
                "page": tag.page if tag.page else 1,
                "tag": tag.tag,
                "unit": tag.parts.unit if hasattr(tag, "parts") else None,
                "prefix": tag.parts.prefix if hasattr(tag, "parts") else None,
                "suffix": tag.parts.suffix if hasattr(tag, "parts") else None,
                "variant": tag.parts.variant if hasattr(tag, "parts") else None,
                "annotation": tag.parts.annotation if hasattr(tag, "parts") else None,
                "bbox": tag.bbox if hasattr(tag, "bbox") else None,
                "confidence": getattr(tag, "confidence", None),
                "has_variant": tag.has_variant
                if hasattr(tag, "has_variant")
                else False,
                "has_annotation": tag.has_annotation
                if hasattr(tag, "has_annotation")
                else False,
            },
        }
        actions.append(action)

    if not actions:
        logger.warning("No actions to index!")
        return 0, []

    logger.info(f"Bulk indexing {len(actions)} tags...")
    success, errors = helpers.bulk(client, actions, raise_on_error=False)

    return success, errors


def main():
    logger.info("=" * 80)
    logger.info("RE-INDEX PID TAGS TO OPENSEARCH")
    logger.info("=" * 80)

    # Paths
    artifacts_dir = Path("artifacts/ingestion")

    # Load doc_id_map
    doc_id_map = load_doc_id_map(artifacts_dir)
    logger.info(f"Loaded {len(doc_id_map)} documents from doc_id_map")

    # Filter CAD-like PDFs
    cad_pdfs = {}
    for doc_id, pdf_path_str in doc_id_map.items():
        pdf_path = Path(pdf_path_str)
        if pdf_path.exists() and is_cad_like_pdf(pdf_path):
            cad_pdfs[doc_id] = pdf_path

    logger.info(f"Found {len(cad_pdfs)} CAD-like PDFs")

    if not cad_pdfs:
        logger.error("No CAD-like PDFs found!")
        return 1

    # Extract tags from all PDFs
    all_tags = []
    for doc_id, pdf_path in cad_pdfs.items():
        logger.info(f"\nProcessing: {doc_id}")
        try:
            tags = extract_tags_from_pdf(pdf_path, doc_id)
            all_tags.extend(tags)
        except Exception as e:
            logger.error(f"Failed to extract from {doc_id}: {e}")

    logger.info(f"\n{'='*80}")
    logger.info(f"Total tags extracted: {len(all_tags)}")
    logger.info(f"{'='*80}")

    if not all_tags:
        logger.error("No tags extracted!")
        return 1

    # Connect to OpenSearch
    logger.info("\nConnecting to OpenSearch...")
    client = create_opensearch_client()

    # Get index name from env
    index_name = os.getenv("TAGS_INDEX_NAME", "pvcfc_pid_tags")

    # Recreate index
    recreate_tags_index(client, index_name)

    # Bulk index
    success, errors = bulk_index_tags(client, all_tags, index_name)

    logger.info(f"\n{'='*80}")
    logger.info("INDEXING COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Success: {success}")
    logger.info(f"Errors: {len(errors) if errors else 0}")

    if errors:
        logger.warning("\nFirst 3 errors:")
        for err in errors[:3]:
            logger.warning(f"  {err}")

    # Force refresh to make documents searchable immediately
    client.indices.refresh(index=index_name)

    # Verify
    logger.info("\nVerifying indexed tags...")
    result = client.count(index=index_name)
    tag_count = result["count"]
    logger.success(f"✅ Total tags in index: {tag_count}")

    # Sample search
    result = client.search(
        index=index_name, body={"query": {"match_all": {}}, "size": 5}
    )

    logger.info("\nSample tags:")
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        logger.info(f"  {src['tag']} - {src['doc_id']} p.{src['page']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
