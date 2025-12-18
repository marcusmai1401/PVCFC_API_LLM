#!/usr/bin/env python
"""
Batch Re-classify Documents

This script re-classifies all existing documents in OpenSearch/Weaviate
using the 4-category classification pipeline (Gemini 2.5 Flash + CADLikeGate).

Features:
- Fetches all unique doc_ids from OpenSearch
- Runs ClassificationPipeline for each PDF
- Updates metadata in both OpenSearch and Weaviate
- Progress tracking with resume capability
- Rate limiting to avoid API quota issues

Usage:
    python scripts/utilities/batch_reclassify.py [options]

Options:
    --dry-run           Show what would be classified without making changes
    --batch-size N      Number of documents per batch (default: 10)
    --delay N           Delay between documents in seconds (default: 1.0)
    --resume            Resume from last checkpoint
    --doc-id DOC_ID     Classify only a specific document
    --skip-classified   Skip documents that are already classified
    --pdf-dir PATH      Directory containing PDF files (default: D:/Data_Raw)

Requirements:
    - OpenSearch running with rag_chunks index
    - Weaviate running with Chunk collection
    - GOOGLE_API_KEY environment variable set
    - PDF files accessible in pdf-dir

Note:
    Default PDF directory is read from .env (DOCUMENTS_DIR) or falls back to D:/Data_Raw
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# Load environment variables
try:
    from dotenv import load_dotenv

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        logger.info(f"Loaded environment from {env_path}")
except ImportError:
    pass

# Import classification pipeline
try:
    from app.classification.classifier import ClassificationResult
    from app.classification.pipeline import (
        ClassificationPipeline,
        PipelineResult,
        get_classification_pipeline,
    )

    CLASSIFICATION_AVAILABLE = True
except ImportError as e:
    logger.error(f"Classification pipeline not available: {e}")
    CLASSIFICATION_AVAILABLE = False
    sys.exit(1)

# Import OpenSearch client
try:
    from opensearchpy import OpenSearch
    from opensearchpy.helpers import bulk
except ImportError:
    logger.error("opensearch-py not installed! Run: pip install opensearch-py")
    sys.exit(1)

# Import Weaviate client
try:
    import weaviate
except ImportError:
    logger.error("weaviate-client not installed! Run: pip install weaviate-client")
    sys.exit(1)


# Configuration
CHECKPOINT_FILE = PROJECT_ROOT / "artifacts" / "reclassify_checkpoint.json"
RESULTS_FILE = PROJECT_ROOT / "artifacts" / "reclassify_results.json"


def create_opensearch_client() -> OpenSearch:
    """Create OpenSearch client connection"""
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )

    # Test connection
    try:
        info = client.info()
        logger.info(f"Connected to OpenSearch: {info['version']['number']}")
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {e}")
        raise

    return client


def connect_to_weaviate() -> weaviate.WeaviateClient:
    """Connect to Weaviate"""
    host = os.environ.get("WEAVIATE_HOST", "localhost")
    port = int(os.environ.get("WEAVIATE_PORT", "8080"))

    client = weaviate.connect_to_local(host=host, port=port)
    logger.info(f"Connected to Weaviate at {host}:{port}")
    return client


def get_all_doc_ids(
    os_client: OpenSearch, index_name: str = "rag_chunks"
) -> List[Dict[str, Any]]:
    """
    Get all unique doc_ids from OpenSearch with their metadata

    Returns list of dicts with:
    - doc_id: Document ID
    - filename: Original filename
    - current_category: Current category (if any)
    - current_status: Current classification status (if any)

    Note: The rag_chunks index has fields at root level (doc_id, file_name, etc.)
    not nested under metadata. This function handles both schemas.
    """
    logger.info("Fetching all unique doc_ids from OpenSearch...")

    # First, check the schema by sampling a document
    sample = os_client.search(index=index_name, body={"size": 1})
    if sample["hits"]["hits"]:
        sample_doc = sample["hits"]["hits"][0]["_source"]
        # Detect if fields are at root level or under metadata
        has_root_doc_id = "doc_id" in sample_doc
        has_metadata_doc_id = "metadata" in sample_doc and "doc_id" in sample_doc.get(
            "metadata", {}
        )
        logger.info(
            f"Schema detection: root_doc_id={has_root_doc_id}, metadata_doc_id={has_metadata_doc_id}"
        )
    else:
        has_root_doc_id = True  # Default assumption
        has_metadata_doc_id = False

    # Build query based on detected schema
    if has_root_doc_id:
        # Fields at root level (current rag_chunks schema)
        doc_id_field = "doc_id"
        source_fields = [
            "doc_id",
            "file_name",
            "category",
            "doc_type",
            "classification_status",
        ]
    else:
        # Fields under metadata (new schema)
        doc_id_field = "metadata.doc_id"
        source_fields = [
            "metadata.doc_id",
            "metadata.filename",
            "metadata.category",
            "metadata.doc_type",
            "metadata.classification_status",
            "metadata.file_path",
        ]

    # Use aggregation to get unique doc_ids
    query = {
        "size": 0,
        "aggs": {
            "unique_docs": {
                "terms": {"field": doc_id_field, "size": 100000},  # Max documents
                "aggs": {
                    "doc_info": {"top_hits": {"size": 1, "_source": source_fields}}
                },
            }
        },
    }

    response = os_client.search(index=index_name, body=query)

    documents = []
    buckets = response.get("aggregations", {}).get("unique_docs", {}).get("buckets", [])

    for bucket in buckets:
        doc_id = bucket.get("key", "")
        hits = bucket.get("doc_info", {}).get("hits", {}).get("hits", [])

        if hits:
            source = hits[0].get("_source", {})

            if has_root_doc_id:
                # Root level fields
                documents.append(
                    {
                        "doc_id": doc_id,
                        "filename": source.get("file_name", ""),
                        "file_path": "",  # Not stored in current schema
                        "current_category": source.get("category"),
                        "current_doc_type": source.get("doc_type"),
                        "current_status": source.get("classification_status"),
                    }
                )
            else:
                # Nested metadata fields
                metadata = source.get("metadata", {})
                documents.append(
                    {
                        "doc_id": doc_id,
                        "filename": metadata.get("filename", ""),
                        "file_path": metadata.get("file_path", ""),
                        "current_category": metadata.get("category"),
                        "current_doc_type": metadata.get("doc_type"),
                        "current_status": metadata.get("classification_status"),
                    }
                )

    logger.info(f"Found {len(documents)} unique documents")
    return documents


def find_pdf_path(doc_info: Dict[str, Any], pdf_dir: Path) -> Optional[Path]:
    """
    Find the PDF file path for a document

    Tries multiple strategies:
    1. Use file_path from metadata if exists
    2. Search by filename in pdf_dir
    3. Search by doc_id pattern
    """
    filename = doc_info.get("filename", "")
    file_path = doc_info.get("file_path", "")
    doc_id = doc_info.get("doc_id", "")

    # Strategy 1: Use file_path from metadata
    if file_path:
        path = Path(file_path)
        if path.exists():
            return path
        # Try relative to pdf_dir
        path = pdf_dir / path.name
        if path.exists():
            return path

    # Strategy 2: Search by filename
    if filename:
        # Direct match
        path = pdf_dir / filename
        if path.exists():
            return path

        # Recursive search
        matches = list(pdf_dir.rglob(filename))
        if matches:
            return matches[0]

    # Strategy 3: Search by doc_id pattern
    if doc_id:
        # Try doc_id.pdf
        path = pdf_dir / f"{doc_id}.pdf"
        if path.exists():
            return path

        # Search for files containing doc_id
        for pdf_file in pdf_dir.rglob("*.pdf"):
            if doc_id in pdf_file.stem:
                return pdf_file

    return None


def update_opensearch_classification(
    os_client: OpenSearch,
    doc_id: str,
    classification: Dict[str, Any],
    index_name: str = "rag_chunks",
    dry_run: bool = False,
) -> int:
    """
    Update classification metadata for all chunks of a document in OpenSearch

    Note: The rag_chunks index has fields at root level (doc_id, category, etc.)
    not nested under metadata. This function handles both schemas.

    Returns number of chunks updated
    """
    # Detect schema by checking if doc_id field exists at root
    sample = os_client.search(index=index_name, body={"size": 1})
    has_root_doc_id = False
    if sample["hits"]["hits"]:
        sample_doc = sample["hits"]["hits"][0]["_source"]
        has_root_doc_id = "doc_id" in sample_doc

    doc_id_field = "doc_id" if has_root_doc_id else "metadata.doc_id"

    if dry_run:
        # Count how many chunks would be updated
        count_query = {"query": {"term": {doc_id_field: doc_id}}}
        response = os_client.count(index=index_name, body=count_query)
        return response.get("count", 0)

    # Build update script based on schema
    if has_root_doc_id:
        # Root level fields (current schema)
        script_source = """
            ctx._source.category = params.category;
            ctx._source.doc_type = params.doc_type;
            ctx._source.classification_status = params.status;
            ctx._source.classification_confidence = params.confidence;
            ctx._source.classification_method = params.method;
        """
    else:
        # Nested metadata fields (new schema)
        script_source = """
            ctx._source.metadata.category = params.category;
            ctx._source.metadata.doc_type = params.doc_type;
            ctx._source.metadata.classification_status = params.status;
            ctx._source.metadata.classification_confidence = params.confidence;
            ctx._source.metadata.classification_method = params.method;
        """

    # Update all chunks for this doc_id
    update_query = {
        "script": {
            "source": script_source,
            "lang": "painless",
            "params": {
                "category": classification.get("category", "UNCATEGORIZED"),
                "doc_type": classification.get("doc_type", "Unknown"),
                "status": classification.get("status", "classified"),
                "confidence": classification.get("confidence", 0.0),
                "method": classification.get("method", "ai_classifier"),
            },
        },
        "query": {"term": {doc_id_field: doc_id}},
    }

    response = os_client.update_by_query(
        index=index_name, body=update_query, refresh=True
    )

    return response.get("updated", 0)


def update_weaviate_classification(
    wv_client: weaviate.WeaviateClient,
    doc_id: str,
    classification: Dict[str, Any],
    collection_name: str = "Chunk",
    dry_run: bool = False,
) -> int:
    """
    Update classification metadata for all objects of a document in Weaviate

    Returns number of objects updated
    """
    if not wv_client.collections.exists(collection_name):
        logger.warning(f"Weaviate collection '{collection_name}' does not exist")
        return 0

    collection = wv_client.collections.get(collection_name)
    updated_count = 0

    # Fetch objects for this doc_id
    # Note: Weaviate v4 filtering syntax
    try:
        response = collection.query.fetch_objects(
            filters=weaviate.classes.query.Filter.by_property("doc_id").equal(doc_id),
            limit=10000,
            return_properties=["doc_id"],
        )

        if dry_run:
            return len(response.objects)

        # Update each object
        for obj in response.objects:
            try:
                collection.data.update(
                    uuid=obj.uuid,
                    properties={
                        "category": classification.get("category", "UNCATEGORIZED"),
                        "doc_type": classification.get("doc_type", "Unknown"),
                        "classification_status": classification.get(
                            "status", "classified"
                        ),
                    },
                )
                updated_count += 1
            except Exception as e:
                logger.warning(f"Failed to update Weaviate object {obj.uuid}: {e}")

    except Exception as e:
        logger.warning(f"Failed to query Weaviate for doc_id {doc_id}: {e}")

    return updated_count


def load_checkpoint() -> Dict[str, Any]:
    """Load checkpoint from file"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"processed_doc_ids": [], "last_updated": None}


def save_checkpoint(checkpoint: Dict[str, Any]):
    """Save checkpoint to file"""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    checkpoint["last_updated"] = datetime.now().isoformat()
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)


def save_results(results: List[Dict[str, Any]]):
    """Save classification results to file"""
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total": len(results),
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def run_batch_reclassify(
    pdf_dir: Path,
    batch_size: int = 10,
    delay: float = 1.0,
    dry_run: bool = False,
    resume: bool = False,
    skip_classified: bool = False,
    specific_doc_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main function to run batch re-classification

    Args:
        pdf_dir: Directory containing PDF files
        batch_size: Number of documents per batch
        delay: Delay between documents (seconds)
        dry_run: If True, don't make actual changes
        resume: If True, resume from checkpoint
        skip_classified: If True, skip already classified documents
        specific_doc_id: If set, only classify this document

    Returns:
        Statistics dictionary
    """
    stats = {
        "total_documents": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "pdf_not_found": 0,
        "already_classified": 0,
        "guardrail_triggered": 0,
        "needs_review": 0,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "results": [],
    }

    # Connect to databases
    logger.info("Connecting to databases...")
    os_client = create_opensearch_client()
    wv_client = None
    try:
        wv_client = connect_to_weaviate()
    except Exception as e:
        logger.warning(f"Could not connect to Weaviate: {e}")
        logger.warning("Will only update OpenSearch")

    # Initialize classification pipeline
    logger.info("Initializing classification pipeline...")
    pipeline = get_classification_pipeline(
        use_cadlike_gate=True, cad_score_threshold=0.55
    )

    # Get all documents
    documents = get_all_doc_ids(os_client)
    stats["total_documents"] = len(documents)

    # Filter for specific doc_id if provided
    if specific_doc_id:
        documents = [d for d in documents if d["doc_id"] == specific_doc_id]
        if not documents:
            logger.error(f"Document not found: {specific_doc_id}")
            return stats
        logger.info(f"Processing single document: {specific_doc_id}")

    # Load checkpoint if resuming
    processed_doc_ids: Set[str] = set()
    if resume:
        checkpoint = load_checkpoint()
        processed_doc_ids = set(checkpoint.get("processed_doc_ids", []))
        logger.info(
            f"Resuming from checkpoint: {len(processed_doc_ids)} already processed"
        )

    # Filter documents
    documents_to_process = []
    for doc in documents:
        doc_id = doc["doc_id"]

        # Skip if already processed (resume mode)
        if doc_id in processed_doc_ids:
            stats["skipped"] += 1
            continue

        # Skip if already classified (if flag set)
        if skip_classified and doc.get("current_status") == "classified":
            stats["already_classified"] += 1
            continue

        documents_to_process.append(doc)

    logger.info(f"Documents to process: {len(documents_to_process)}")
    logger.info(f"Skipped (checkpoint): {stats['skipped']}")
    logger.info(f"Skipped (already classified): {stats['already_classified']}")

    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 60)

    # Process documents
    for idx, doc_info in enumerate(documents_to_process):
        doc_id = doc_info["doc_id"]
        filename = doc_info.get("filename", doc_id)

        logger.info(f"\n[{idx + 1}/{len(documents_to_process)}] Processing: {filename}")

        # Find PDF file
        pdf_path = find_pdf_path(doc_info, pdf_dir)

        if not pdf_path:
            logger.warning(f"  ❌ PDF not found for {filename}")
            stats["pdf_not_found"] += 1
            stats["results"].append(
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "status": "pdf_not_found",
                    "error": "PDF file not found",
                }
            )
            continue

        logger.info(f"  📄 Found PDF: {pdf_path}")

        try:
            # Run classification
            if not dry_run:
                result = pipeline.classify_document(
                    pdf_path=pdf_path, doc_metadata={"doc_id": doc_id}
                )
                classification = result.classification.to_dict()

                # Log result
                if result.guardrail_triggered:
                    logger.info(
                        f"  📋 Classification (guardrail): "
                        f"{classification['category']}/{classification['doc_type']} "
                        f"(CAD_score={result.cad_score:.3f})"
                    )
                    stats["guardrail_triggered"] += 1
                else:
                    logger.info(
                        f"  📋 Classification (AI): "
                        f"{classification['category']}/{classification['doc_type']} "
                        f"(confidence={classification['confidence']:.2f})"
                    )

                if classification.get("status") == "needs_review":
                    stats["needs_review"] += 1

                # Update OpenSearch
                os_updated = update_opensearch_classification(
                    os_client, doc_id, classification, dry_run=False
                )
                logger.info(f"  ✅ Updated {os_updated} chunks in OpenSearch")

                # Update Weaviate
                if wv_client:
                    wv_updated = update_weaviate_classification(
                        wv_client, doc_id, classification, dry_run=False
                    )
                    logger.info(f"  ✅ Updated {wv_updated} objects in Weaviate")

                # Record result
                stats["results"].append(
                    {
                        "doc_id": doc_id,
                        "filename": filename,
                        "status": "success",
                        "classification": classification,
                        "os_chunks_updated": os_updated,
                        "wv_objects_updated": wv_updated if wv_client else 0,
                    }
                )

            else:
                # Dry run - just count what would be updated
                os_count = update_opensearch_classification(
                    os_client, doc_id, {}, dry_run=True
                )
                logger.info(f"  [DRY RUN] Would update {os_count} chunks in OpenSearch")

                stats["results"].append(
                    {
                        "doc_id": doc_id,
                        "filename": filename,
                        "status": "dry_run",
                        "would_update_chunks": os_count,
                    }
                )

            stats["processed"] += 1

            # Update checkpoint
            processed_doc_ids.add(doc_id)
            if not dry_run and (idx + 1) % batch_size == 0:
                save_checkpoint({"processed_doc_ids": list(processed_doc_ids)})
                logger.info(
                    f"  💾 Checkpoint saved ({len(processed_doc_ids)} processed)"
                )

        except Exception as e:
            logger.error(f"  ❌ Classification failed: {e}")
            stats["failed"] += 1
            stats["results"].append(
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "status": "failed",
                    "error": str(e),
                }
            )

        # Rate limiting
        if delay > 0 and idx < len(documents_to_process) - 1:
            time.sleep(delay)

    # Final checkpoint
    if not dry_run:
        save_checkpoint({"processed_doc_ids": list(processed_doc_ids)})

    # Close Weaviate connection
    if wv_client:
        wv_client.close()

    stats["end_time"] = datetime.now().isoformat()

    # Save results
    save_results(stats["results"])

    return stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Batch re-classify documents using 4-category taxonomy"
    )
    # Import config for default pdf_dir
    from app.config.pipeline_config import get_config

    default_pdf_dir = str(get_config().DOCUMENTS_DIR)

    parser.add_argument(
        "--pdf-dir",
        type=str,
        default=default_pdf_dir,
        help=f"Directory containing PDF files (default: {default_pdf_dir})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of documents per batch for checkpointing (default: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between documents in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be classified without making changes",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last checkpoint"
    )
    parser.add_argument(
        "--skip-classified",
        action="store_true",
        help="Skip documents that are already classified",
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Classify only a specific document by doc_id",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear checkpoint file before starting",
    )

    args = parser.parse_args()

    # Clear checkpoint if requested
    if args.clear_checkpoint and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("Cleared checkpoint file")

    # Validate PDF directory
    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        logger.error(f"PDF directory not found: {pdf_dir}")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("BATCH RE-CLASSIFY DOCUMENTS")
    logger.info("=" * 80)
    logger.info(f"PDF Directory: {pdf_dir}")
    logger.info(f"Batch Size: {args.batch_size}")
    logger.info(f"Delay: {args.delay}s")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Resume: {args.resume}")
    logger.info(f"Skip Classified: {args.skip_classified}")
    if args.doc_id:
        logger.info(f"Specific Doc ID: {args.doc_id}")
    logger.info("=" * 80)

    # Run batch reclassification
    stats = run_batch_reclassify(
        pdf_dir=pdf_dir,
        batch_size=args.batch_size,
        delay=args.delay,
        dry_run=args.dry_run,
        resume=args.resume,
        skip_classified=args.skip_classified,
        specific_doc_id=args.doc_id,
    )

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Documents: {stats['total_documents']}")
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"PDF Not Found: {stats['pdf_not_found']}")
    logger.info(f"Skipped (checkpoint): {stats['skipped']}")
    logger.info(f"Skipped (already classified): {stats['already_classified']}")
    logger.info(f"Guardrail Triggered (P&ID): {stats['guardrail_triggered']}")
    logger.info(f"Needs Review: {stats['needs_review']}")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("\nThis was a DRY RUN. Run without --dry-run to apply changes.")
    else:
        logger.info(f"\nResults saved to: {RESULTS_FILE}")
        logger.info(f"Checkpoint saved to: {CHECKPOINT_FILE}")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
