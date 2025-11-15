#!/usr/bin/env python
"""
Check spatial component index status
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from app.rag.spatial.component_indexer import SpatialComponentIndexer

logger.info("=" * 80)
logger.info("Checking Spatial Component Index")
logger.info("=" * 80)

indexer = SpatialComponentIndexer()

# Get total count
total_count = indexer.get_component_count()
logger.info(f"\nTotal components in index: {total_count}")

if total_count == 0:
    logger.error("❌ Spatial component index is EMPTY!")
    logger.error("   You need to run ingestion with P&ID tag extraction enabled.")
    sys.exit(1)

# Get all doc_ids
doc_ids = indexer.get_all_doc_ids()
logger.info(f"\nDocuments in spatial index: {len(doc_ids)}")

for doc_id in doc_ids:
    count = indexer.get_component_count(doc_id=doc_id)
    logger.info(f"  - {doc_id}: {count} components")

# Check for Ammonia P&ID specifically
logger.info("\n" + "=" * 80)
logger.info("Checking Ammonia P&ID Components")
logger.info("=" * 80)

ammonia_docs = [
    doc_id for doc_id in doc_ids if "ammonia" in doc_id.lower() or "04000" in doc_id
]

if not ammonia_docs:
    logger.warning("⚠️  No Ammonia P&ID document found in spatial index")
    logger.info("\nSearching for components with text '04', 'PV', '5012'...")

    # Try searching across all docs
    for component_text in ["04", "PV", "5012"]:
        results = indexer.search_components(component_text=component_text, size=10)
        logger.info(f"\n  Component '{component_text}': {len(results)} results")
        if results:
            for r in results[:3]:  # Show first 3
                logger.info(
                    f"    - Doc: {r['doc_id']}, Page: {r['page']}, Type: {r['component_type']}"
                )
else:
    logger.info(f"✅ Found {len(ammonia_docs)} Ammonia P&ID document(s)")

    for doc_id in ammonia_docs:
        logger.info(f"\n  Document: {doc_id}")

        # Check for specific components
        for component_text in ["04", "PV", "5012"]:
            results = indexer.search_components(
                component_text=component_text, doc_id=doc_id, size=100
            )
            logger.info(
                f"    - Component '{component_text}': {len(results)} occurrences"
            )

            # Check page 56 specifically
            page_56_results = [r for r in results if r["page"] == 56]
            if page_56_results:
                logger.success(
                    f"      ✅ Found on page 56: {len(page_56_results)} instances"
                )
            else:
                if results:
                    pages = sorted(set(r["page"] for r in results))
                    logger.info(
                        f"      Pages: {pages[:10]}{'...' if len(pages) > 10 else ''}"
                    )

logger.info("\n" + "=" * 80)
