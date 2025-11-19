#!/usr/bin/env python
"""
Script đơn giản để clear ALL data trước khi re-ingestion
"""
import os
import shutil
import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except:
    pass

import weaviate
from loguru import logger
from opensearchpy import OpenSearch

# Settings
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "8080"))
WEAVIATE_COLLECTION = os.getenv("WEAVIATE_COLLECTION", "Chunk")

RAG_CHUNKS_INDEX = os.getenv("OPENSEARCH_INDEX", "rag_chunks")
SPATIAL_INDEX = "pvcfc_pid_spatial_components"


def clear_opensearch():
    """Clear OpenSearch indexes"""
    logger.info("Clearing OpenSearch indexes...")
    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        timeout=60,
    )

    # Delete rag_chunks
    if client.indices.exists(index=RAG_CHUNKS_INDEX):
        client.indices.delete(index=RAG_CHUNKS_INDEX)
        logger.success(f"Deleted {RAG_CHUNKS_INDEX}")

    # Delete spatial_components
    if client.indices.exists(index=SPATIAL_INDEX):
        client.indices.delete(index=SPATIAL_INDEX)
        logger.success(f"Deleted {SPATIAL_INDEX}")

    logger.info("")


def clear_weaviate():
    """Clear Weaviate collection"""
    logger.info("Clearing Weaviate collection...")
    try:
        client = weaviate.connect_to_local(host=WEAVIATE_HOST, port=WEAVIATE_PORT)
        if client.collections.exists(WEAVIATE_COLLECTION):
            client.collections.delete(WEAVIATE_COLLECTION)
            logger.success(f"Deleted {WEAVIATE_COLLECTION} collection")
        else:
            logger.info(f"Collection {WEAVIATE_COLLECTION} does not exist")
        client.close()
    except Exception as e:
        logger.error(f"Error clearing Weaviate: {e}")
        raise
    logger.info("")


def clear_artifacts():
    """Clear artifacts directories"""
    logger.info("Clearing artifacts directories...")

    # Use ARTIFACTS_DIR from env, fallback to local
    artifacts_base = os.getenv("ARTIFACTS_DIR")
    if artifacts_base:
        artifacts_root = Path(artifacts_base)
    else:
        artifacts_root = PROJECT_ROOT / "artifacts"

    dirs = [
        artifacts_root / "ingestion_production",
        artifacts_root / "index_production",
    ]

    for d in dirs:
        if d.exists():
            shutil.rmtree(d)
            logger.success(f"Deleted {d}")
        else:
            logger.info(f"{d} does not exist")
    logger.info("")


def recreate_opensearch_indexes():
    """Recreate OpenSearch indexes"""
    logger.info("Recreating OpenSearch indexes...")

    # Import và chạy trực tiếp thay vì subprocess
    try:
        # Import create_rag_chunks_index
        sys.path.insert(0, str(PROJECT_ROOT))
        import argparse

        from scripts.opensearch.create_rag_chunks_index import main as create_rag_main

        # Tạo args
        class Args:
            delete_if_exists = True

        # Monkey patch argparse để dùng Args object
        original_parse = argparse.ArgumentParser.parse_args

        def mock_parse(self, args=None, namespace=None):
            return Args()

        argparse.ArgumentParser.parse_args = mock_parse

        create_rag_main()

        # Import create_spatial_components_index
        from scripts.opensearch.create_spatial_components_index import (
            main as create_spatial_main,
        )

        create_spatial_main()

        logger.success("Created rag_chunks index")
        logger.success("Created spatial_components index")

    except Exception as e:
        logger.error(f"Failed to recreate indexes: {e}")
        # Fallback: chạy bằng subprocess với full path
        import subprocess

        os.chdir(PROJECT_ROOT)

        script1 = PROJECT_ROOT / "scripts" / "opensearch" / "create_rag_chunks_index.py"
        result1 = subprocess.run(
            [sys.executable, str(script1), "--delete-if-exists"], cwd=PROJECT_ROOT
        )

        script2 = (
            PROJECT_ROOT
            / "scripts"
            / "opensearch"
            / "create_spatial_components_index.py"
        )
        result2 = subprocess.run(
            [sys.executable, str(script2), "--delete-if-exists"], cwd=PROJECT_ROOT
        )

        if result1.returncode != 0 or result2.returncode != 0:
            raise Exception("Failed to create indexes")

    logger.info("")


def main():
    """Main"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    logger.warning("=" * 80)
    logger.warning("WARNING: This will DELETE ALL EXISTING DATA!")
    logger.warning("=" * 80)
    logger.warning("")

    if not args.yes:
        response = input("Type 'yes' to continue: ")
        if response.lower() != "yes":
            logger.info("Aborted")
            return

    try:
        clear_opensearch()
        clear_weaviate()
        clear_artifacts()
        recreate_opensearch_indexes()

        logger.success("")
        logger.success("=" * 80)
        logger.success("ALL DATA CLEARED - READY FOR FULL INGESTION")
        logger.success("=" * 80)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
