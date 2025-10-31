"""
Re-extract and re-index P&ID tags with fixed variant detection logic
"""
import json
from pathlib import Path

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor


def main():
    # Configuration
    pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_896a8a91"
    output_file = Path("artifacts/ingestion_production/entities/tags.jsonl")

    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return

    # Clear existing tags file
    if output_file.exists():
        output_file.unlink()
        logger.info(f"Cleared existing tags file: {output_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Initialize extractors
    layout_builder = PageLayoutBuilder()
    tag_extractor = TagExtractor()

    # Extract tags from all pages (117 pages)
    total_tags = 0
    for page_num in range(1, 118):  # 1-117
        logger.info(f"Processing page {page_num}/117...")

        try:
            # Build layout
            layout = layout_builder.build_layout(
                pdf_path=pdf_path, page_num=page_num, doc_id=doc_id
            )

            # Extract tags
            tags = tag_extractor.extract_tags(layout)

            # Save to JSONL
            with open(output_file, "a", encoding="utf-8") as f:
                for tag in tags:
                    json_line = tag.model_dump_json()
                    f.write(json_line + "\n")

            total_tags += len(tags)
            logger.info(f"  Page {page_num}: {len(tags)} tags extracted")

        except Exception as e:
            logger.error(f"  Page {page_num}: Failed - {e}")
            continue

    logger.success(f"✓ Extraction complete! Total tags: {total_tags}")
    logger.info(f"Output: {output_file}")

    # Now re-index to OpenSearch
    logger.info("\n" + "=" * 60)
    logger.info("Re-indexing tags to OpenSearch...")
    logger.info("=" * 60)

    import subprocess

    result = subprocess.run(
        ["python", "scripts/opensearch/bulk_upsert_tags.py"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.success("✓ Re-indexing complete!")
        print(result.stdout)
    else:
        logger.error(f"✗ Re-indexing failed:\n{result.stderr}")


if __name__ == "__main__":
    main()
