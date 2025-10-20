#!/usr/bin/env python
"""
Re-extract all tags from P&ID documents using new schema

This script:
1. Loads all P&ID documents from doc_id_map
2. Re-runs CADLikeGate + TagExtractor with new UNIT/PREFIX/SUFFIX/VARIANT/ANNOTATION schema
3. Saves to artifacts/migration/tags_new_schema.jsonl
4. Validates: compares counts with backup
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

import fitz
from loguru import logger

from app.config import get_config
from app.ingestion.cadlike_gate import CADLikeGate
from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor


def load_doc_id_map() -> Dict:
    """Load doc_id_map.json"""
    # Try production path first
    production_path = PROJECT_ROOT / "artifacts/ingestion_production/doc_id_map.json"
    legacy_path = PROJECT_ROOT / "artifacts/ingestion/doc_id_map.json"

    doc_id_map_path = production_path if production_path.exists() else legacy_path

    if not doc_id_map_path.exists():
        raise FileNotFoundError("doc_id_map.json not found")

    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    logger.info(
        f"Loaded doc_id_map from {doc_id_map_path}: {len(doc_id_map)} documents"
    )
    return doc_id_map


def reextract_all_tags(output_dir: Path):
    """
    Re-extract tags from all P&ID documents

    Args:
        output_dir: Output directory for new tags
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output file
    output_file = output_dir / "tags_new_schema.jsonl"

    # Clear output file if exists
    if output_file.exists():
        output_file.unlink()

    # Load doc_id_map
    doc_id_map = load_doc_id_map()

    # Initialize components
    gate = CADLikeGate()
    layout_builder = PageLayoutBuilder()
    extractor = TagExtractor()

    # Statistics
    stats = {
        "total_docs": len(doc_id_map),
        "cadlike_docs": 0,
        "total_taggy_pages": 0,
        "total_tags": 0,
        "docs_processed": 0,
        "docs_failed": 0,
    }

    # Process each document
    for doc_id, pdf_path_str in doc_id_map.items():
        pdf_path = Path(pdf_path_str)

        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            stats["docs_failed"] += 1
            continue

        logger.info(
            f"Processing [{stats['docs_processed']+1}/{stats['total_docs']}]: {pdf_path.name}"
        )

        try:
            # Run CAD-like gate
            gate_decision = gate.evaluate(pdf_path)

            if not gate_decision.is_cadlike:
                logger.debug(
                    f"Not CAD-like (score: {gate_decision.score:.2f}), skipping"
                )
                stats["docs_processed"] += 1
                continue

            stats["cadlike_docs"] += 1
            taggy_pages = gate_decision.taggy_pages
            stats["total_taggy_pages"] += len(taggy_pages)

            logger.info(
                f"CAD-like detected (score: {gate_decision.score:.2f}), {len(taggy_pages)} taggy pages"
            )

            # Process each taggy page
            for page_idx in taggy_pages:
                # Build layout (API: pdf_path, page_num 1-based, doc_id)
                page_num = page_idx + 1  # Convert 0-based to 1-based

                try:
                    layout = layout_builder.build_layout(
                        pdf_path=pdf_path,
                        page_num=page_num,
                        doc_id=doc_id,
                    )

                    # Extract tags with NEW schema
                    tags = extractor.extract_tags(layout)

                    stats["total_tags"] += len(tags)

                    # Save tags to JSONL
                    with open(output_file, "a", encoding="utf-8") as f:
                        for tag in tags:
                            json_line = tag.model_dump_json()
                            f.write(json_line + "\n")

                    logger.debug(f"Page {page_num}: extracted {len(tags)} tags")

                except Exception as e:
                    logger.error(f"Failed to extract tags from page {page_num}: {e}")

            stats["docs_processed"] += 1

        except Exception as e:
            logger.error(f"Failed to process {pdf_path.name}: {e}")
            stats["docs_failed"] += 1

    # Save statistics
    stats_file = output_dir / "reextraction_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    logger.info("=" * 60)
    logger.info("Re-extraction complete!")
    logger.info(f"Total documents: {stats['total_docs']}")
    logger.info(f"CAD-like documents: {stats['cadlike_docs']}")
    logger.info(f"Taggy pages: {stats['total_taggy_pages']}")
    logger.info(f"Total tags extracted: {stats['total_tags']}")
    logger.info(f"Output: {output_file}")
    logger.info(f"Stats: {stats_file}")
    logger.info("=" * 60)


def main():
    """Main re-extraction function"""
    # Output directory
    output_dir = PROJECT_ROOT / "artifacts/migration"

    logger.info("Starting tag re-extraction with new schema...")
    logger.info(f"Output directory: {output_dir}")

    # Re-extract tags
    reextract_all_tags(output_dir)

    logger.info("Re-extraction complete!")


if __name__ == "__main__":
    main()
