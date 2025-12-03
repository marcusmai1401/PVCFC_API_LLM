"""Process missing file and index all chunks to OpenSearch + Weaviate"""
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup environment
from dotenv import load_dotenv

env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        creds_path = str(PROJECT_ROOT / "credentials.json")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor
from app.ingestion.text_chunker import ParentChildChunker


def process_missing_file():
    """Process the missing PDF file"""
    logger.info("=" * 80)
    logger.info("STEP 1: Processing missing file")
    logger.info("=" * 80)

    file_path = Path(
        r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Drawing\026A_3N4-019421_Section drawing Rev.0.pdf"
    )

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return None

    logger.info(f"Processing: {file_path.name}")

    # Process PDF
    processor = PDFProcessor(
        enable_ocr=True,
        extract_tables=True,
        force_ocr_all_pages=False,
    )

    pdf_doc = processor.process_pdf(file_path)
    full_text = "\n".join(p.text for p in pdf_doc.pages)

    if not full_text.strip():
        logger.warning("No text extracted, skipping chunking")
        return None

    # Chunking with Phase 3 Parent-Child strategy
    chunker = ParentChildChunker(
        parent_chunk_size=1800,
        parent_overlap=200,
        child_chunk_size=400,
        child_overlap=50,
        min_chunk_size=100,
    )

    doc_dict = pdf_doc.to_dict()
    chunks = chunker.chunk_document(doc_dict, doc_id=file_path.stem)

    # Save chunks
    output_file = (
        Path("artifacts/ingestion_production/chunks") / f"{file_path.stem}_chunks.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    logger.success(f"✅ Processed: {len(chunks)} chunks saved to {output_file.name}")
    return len(chunks)


def index_to_opensearch():
    """Index all chunks to OpenSearch"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Indexing to OpenSearch")
    logger.info("=" * 80)

    try:
        from opensearchpy import OpenSearch
        from opensearchpy.helpers import bulk

        # Connect
        client = OpenSearch(
            [{"host": "localhost", "port": 9200}],
            http_auth=("admin", "Xgp@pvcfc2024"),
            use_ssl=False,
        )

        logger.info(f"Connected to OpenSearch v{client.info()['version']['number']}")

        # Delete old index if exists
        if "rag_chunks" in [
            idx
            for idx in client.cat.indices(format="json")
            if idx["index"] == "rag_chunks"
        ]:
            logger.info("Deleting old rag_chunks index...")
            client.indices.delete(index="rag_chunks")

        # Create index with Phase 3 parent-child mapping
        mapping = {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "text": {"type": "text"},
                    "parent_text": {
                        "type": "text",
                        "index": False,
                    },  # Phase 3: Parent text (not indexed, stored only)
                    "page_start": {"type": "integer"},
                    "page_end": {"type": "integer"},
                    "page": {"type": "integer"},
                    "chunk_index": {"type": "integer"},
                    "tags": {"type": "keyword"},
                    "tags_raw": {"type": "keyword"},
                    "metadata": {
                        "type": "object",
                        "enabled": True,
                        "properties": {
                            "parent_id": {"type": "keyword"},
                            "parent_text": {"type": "text", "index": False},
                            "chunk_type": {"type": "keyword"},
                            "is_parent": {"type": "boolean"},
                            "parent_index": {"type": "integer"},
                            "parent_char_count": {"type": "integer"},
                        },
                    },
                }
            }
        }
        client.indices.create(index="rag_chunks", body=mapping)
        logger.info("Created rag_chunks index")

        # Load all chunks
        chunks_dir = Path("artifacts/ingestion_production/chunks")
        all_chunks = []

        for chunk_file in sorted(chunks_dir.glob("*_chunks.json")):
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                all_chunks.extend(chunks)

        logger.info(
            f"Loaded {len(all_chunks)} chunks from {len(list(chunks_dir.glob('*_chunks.json')))} files"
        )

        # Bulk index with Phase 3 parent_text mapping
        actions = []
        for chunk in all_chunks:
            metadata = chunk.get("metadata", {})

            source = {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "text": chunk["text"],
                "parent_text": metadata.get(
                    "parent_text"
                ),  # Phase 3: Extract parent_text from metadata
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "page": metadata.get("page"),
                "chunk_index": chunk.get("chunk_index", 0),
                "tags": metadata.get("tags", []),
                "tags_raw": metadata.get("tags_raw", []),
                "metadata": metadata,
            }

            actions.append(
                {"_index": "rag_chunks", "_id": chunk["chunk_id"], "_source": source}
            )

        success, failed = bulk(client, actions, raise_on_error=False)
        logger.success(
            f"✅ Indexed {success} chunks to OpenSearch (failed: {len(failed)})"
        )

        return len(all_chunks)

    except Exception as e:
        logger.error(f"❌ OpenSearch error: {e}")
        import traceback

        traceback.print_exc()
        return 0


def index_to_weaviate():
    """Index all chunks to Weaviate"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Indexing to Weaviate")
    logger.info("=" * 80)

    try:
        import weaviate
        import weaviate.classes as wvc

        # Connect
        client = weaviate.connect_to_local()

        if not client.is_ready():
            logger.error("Weaviate not ready")
            return 0

        logger.info("Connected to Weaviate")

        # Delete old collection if exists
        if client.collections.exists("Chunk"):
            logger.info("Deleting old Chunk collection...")
            client.collections.delete("Chunk")

        # Create collection with Phase 3 parent-child schema
        client.collections.create(
            name="Chunk",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            properties=[
                wvc.config.Property(
                    name="chunk_id", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(name="doc_id", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="parent_text", data_type=wvc.config.DataType.TEXT
                ),  # Phase 3
                wvc.config.Property(
                    name="parent_id", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="chunk_type", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="is_parent", data_type=wvc.config.DataType.BOOL
                ),
                wvc.config.Property(
                    name="parent_index", data_type=wvc.config.DataType.INT
                ),
                wvc.config.Property(
                    name="parent_char_count", data_type=wvc.config.DataType.INT
                ),
                wvc.config.Property(
                    name="chunk_index", data_type=wvc.config.DataType.INT
                ),
                wvc.config.Property(
                    name="page_start", data_type=wvc.config.DataType.INT
                ),
                wvc.config.Property(name="page_end", data_type=wvc.config.DataType.INT),
                wvc.config.Property(name="page", data_type=wvc.config.DataType.INT),
                wvc.config.Property(
                    name="tags", data_type=wvc.config.DataType.TEXT_ARRAY
                ),
                wvc.config.Property(
                    name="tags_raw", data_type=wvc.config.DataType.TEXT_ARRAY
                ),
            ],
        )
        logger.info("Created Chunk collection")

        # Load all chunks
        chunks_dir = Path("artifacts/ingestion_production/chunks")
        all_chunks = []

        for chunk_file in sorted(chunks_dir.glob("*_chunks.json")):
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                all_chunks.extend(chunks)

        logger.info(f"Loaded {len(all_chunks)} chunks")

        # Batch insert
        chunks_collection = client.collections.get("Chunk")

        with chunks_collection.batch.dynamic() as batch:
            for chunk in all_chunks:
                metadata = chunk.get("metadata", {})

                batch.add_object(
                    properties={
                        "chunk_id": chunk["chunk_id"],
                        "doc_id": chunk["doc_id"],
                        "text": chunk["text"],
                        "parent_text": metadata.get("parent_text"),  # Phase 3
                        "parent_id": metadata.get("parent_id"),
                        "chunk_type": metadata.get("chunk_type"),
                        "is_parent": metadata.get("is_parent", False),
                        "parent_index": metadata.get("parent_index"),
                        "parent_char_count": metadata.get("parent_char_count"),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "page_start": chunk.get("page_start"),
                        "page_end": chunk.get("page_end"),
                        "page": metadata.get("page"),
                        "tags": metadata.get("tags", []),
                        "tags_raw": metadata.get("tags_raw", []),
                    }
                )

        # Get count
        result = chunks_collection.aggregate.over_all(total_count=True)
        logger.success(f"✅ Indexed {result.total_count} chunks to Weaviate")

        client.close()
        return result.total_count

    except Exception as e:
        logger.error(f"❌ Weaviate error: {e}")
        import traceback

        traceback.print_exc()
        return 0


def main():
    """Main execution"""

    # Step 1: Process missing file
    new_chunks = process_missing_file()

    # Step 2: Index to OpenSearch
    opensearch_count = index_to_opensearch()

    # Step 3: Index to Weaviate
    weaviate_count = index_to_weaviate()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("COMPLETION SUMMARY")
    logger.info("=" * 80)
    if new_chunks:
        logger.info(f"✅ Processed missing file: {new_chunks} chunks")
    logger.info(f"✅ OpenSearch: {opensearch_count} chunks indexed")
    logger.info(f"✅ Weaviate: {weaviate_count} chunks indexed")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
