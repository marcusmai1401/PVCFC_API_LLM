"""
Debug Script: Run Indexing Only
This script runs ONLY the indexing phase (Step 3) of the pipeline.
It uses the existing chunks from 'artifacts/ingestion_production/chunks'.
It leverages the embedding cache, so it should be fast to reach the point where it previously hung.
"""
import os
import sys
import time
from pathlib import Path

from loguru import logger

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set Google Cloud credentials
credentials_path = PROJECT_ROOT / "credentials.json"
if credentials_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)

from scripts.ingest_production import run_indexing


def main():
    logger.info("DEBUG: Starting Indexing-Only Run")

    # Configuration
    # Use ARTIFACTS_DIR from env, fallback to local artifacts
    artifacts_base = os.getenv("ARTIFACTS_DIR", "artifacts")

    # Point to the EXISTING output directory from the previous run
    output_dir = Path(artifacts_base) / "ingestion_production"
    chunks_dir = output_dir / "chunks"

    index_output_dir = Path(artifacts_base) / "index_production"

    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        logger.error("Please run the full ingestion pipeline first, or check the path.")
        return

    logger.info(f"Reading chunks from: {chunks_dir}")
    logger.info(f"Outputting index to: {index_output_dir}")
    logger.info(
        "Note: This will use the embedding cache, so previously processed chunks will be skipped."
    )

    start_time = time.time()

    try:
        success = run_indexing(chunks_dir, index_output_dir)

        if success:
            logger.success("Index build completed successfully!")
        else:
            logger.error("Index build failed.")

    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
    except Exception as e:
        logger.exception(f"An error occurred: {e}")

    elapsed = time.time() - start_time
    logger.info(f"Total time: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
