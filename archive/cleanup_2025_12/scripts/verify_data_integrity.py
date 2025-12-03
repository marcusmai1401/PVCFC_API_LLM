"""
Verify Data Integrity
Checks the document counts in OpenSearch, FAISS, and BM25 to ensure they match the expected number of chunks.
"""
import json
import os
import pickle
import sys
from pathlib import Path

from loguru import logger

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set Google Cloud credentials
credentials_path = PROJECT_ROOT / "credentials.json"
if credentials_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)

from opensearchpy import OpenSearch


def main():
    logger.info("Checking Data Integrity...")

    # Configuration
    artifacts_base = os.getenv("ARTIFACTS_DIR", "artifacts")
    output_dir = Path(artifacts_base) / "ingestion_production"
    chunks_dir = output_dir / "chunks"
    index_output_dir = Path(artifacts_base) / "index_production"

    # 1. Count Source Chunks
    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        return

    chunk_files = list(chunks_dir.glob("*_chunks.json"))
    total_chunks = 0
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
            total_chunks += len(data)

    logger.info(f"Expected Total Chunks (from JSONs): {total_chunks:,}")

    # 2. Check OpenSearch
    opensearch_host = os.getenv("OPENSEARCH_HOST", "localhost")
    opensearch_port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    opensearch_index = os.getenv("OPENSEARCH_INDEX", "rag_chunks")

    try:
        client = OpenSearch(
            hosts=[{"host": opensearch_host, "port": opensearch_port}], timeout=10
        )
        if client.indices.exists(index=opensearch_index):
            count = client.count(index=opensearch_index)["count"]
            logger.info(f"OpenSearch Index '{opensearch_index}': {count:,} docs")

            if count != total_chunks:
                logger.warning(
                    f"⚠️  OpenSearch mismatch! Expected {total_chunks}, got {count}"
                )
            else:
                logger.success("✓ OpenSearch count matches")
        else:
            logger.error(f"OpenSearch index '{opensearch_index}' does not exist!")
    except Exception as e:
        logger.error(f"Failed to check OpenSearch: {e}")

    # 3. Check BM25
    bm25_path = index_output_dir / "bm25" / "documents.json"
    if bm25_path.exists():
        with open(bm25_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
            logger.info(f"BM25 Index: {len(docs):,} docs")
            if len(docs) != total_chunks:
                logger.warning(
                    f"⚠️  BM25 mismatch! Expected {total_chunks}, got {len(docs)}"
                )
            else:
                logger.success("✓ BM25 count matches")
    else:
        logger.error(f"BM25 index not found at {bm25_path}")

    # 4. Check FAISS
    faiss_path = index_output_dir / "faiss" / "texts.json"
    if faiss_path.exists():
        with open(faiss_path, "r", encoding="utf-8") as f:
            texts = json.load(f)
            logger.info(f"FAISS Index: {len(texts):,} docs")
            if len(texts) != total_chunks:
                logger.warning(
                    f"⚠️  FAISS mismatch! Expected {total_chunks}, got {len(texts)}"
                )
            else:
                logger.success("✓ FAISS count matches")
    else:
        logger.error(f"FAISS index not found at {faiss_path}")


if __name__ == "__main__":
    main()
