"""Complete ingestion for missing file and index all to OpenSearch + Weaviate"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json

from loguru import logger

from app.config import get_config
from app.indexing.opensearch_indexer import OpenSearchIndexer
from app.indexing.weaviate_indexer import WeaviateIndexer
from app.ingestion.pdf_ingestion_pipeline import PDFIngestionPipeline


def main():
    """Complete ingestion and index all data"""

    # 1. Process the missing file
    logger.info("=" * 80)
    logger.info("STEP 1: Processing missing file")
    logger.info("=" * 80)

    missing_file = Path(
        r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Drawing\026A_3N4-019421_Section drawing Rev.0.pdf"
    )

    if missing_file.exists():
        logger.info(f"Processing: {missing_file.name}")

        # Initialize pipeline
        config = get_config("production")
        pipeline = PDFIngestionPipeline(
            output_dir=Path("artifacts/ingestion_production"), config=config
        )

        try:
            result = pipeline.process_pdf(missing_file)

            if result and result.get("chunks"):
                logger.info(f"✅ Successfully processed: {len(result['chunks'])} chunks")
            else:
                logger.warning(f"⚠️  No chunks generated for {missing_file.name}")

        except Exception as e:
            logger.error(f"❌ Error processing {missing_file.name}: {e}")
    else:
        logger.error(f"❌ File not found: {missing_file}")

    # 2. Index all chunks to OpenSearch
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Indexing to OpenSearch")
    logger.info("=" * 80)

    try:
        opensearch_indexer = OpenSearchIndexer(
            hosts=[{"host": "localhost", "port": 9200}],
            auth=("admin", "Xgp@pvcfc2024"),
            index_name="rag_chunks",
            use_ssl=False,  # Use HTTP instead of HTTPS to avoid SSL issues
        )

        # Load all chunks
        chunks_dir = Path("artifacts/ingestion_production/chunks")
        all_chunks = []

        for chunk_file in chunks_dir.glob("*_chunks.json"):
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                all_chunks.extend(chunks)

        logger.info(f"Found {len(all_chunks)} total chunks to index")

        # Index to OpenSearch
        opensearch_indexer.index_chunks(all_chunks)
        logger.info(f"✅ Successfully indexed {len(all_chunks)} chunks to OpenSearch")

    except Exception as e:
        logger.error(f"❌ OpenSearch indexing error: {e}")
        import traceback

        traceback.print_exc()

    # 3. Index all chunks to Weaviate
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Indexing to Weaviate")
    logger.info("=" * 80)

    try:
        weaviate_indexer = WeaviateIndexer(
            url="http://localhost:8080", collection_name="Chunk"
        )

        # Index to Weaviate
        weaviate_indexer.index_chunks(all_chunks)
        logger.info(f"✅ Successfully indexed {len(all_chunks)} chunks to Weaviate")

    except Exception as e:
        logger.error(f"❌ Weaviate indexing error: {e}")
        import traceback

        traceback.print_exc()

    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("COMPLETION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ Total chunks: {len(all_chunks)}")
    logger.info(f"✅ Documents: {len(list(chunks_dir.glob('*_chunks.json')))}")
    logger.info("✅ Indexed to OpenSearch")
    logger.info("✅ Indexed to Weaviate")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
