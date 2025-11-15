"""
Run full PDF ingestion on all files in Data_Raw directory
"""
import sys
from pathlib import Path

# Add project root to path (handle both root and scripts/ingestion execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor


def main():
    """Run full ingestion"""

    # Configuration
    input_dir = Path(r"D:\Data_Raw")
    output_dir = Path("data/processed")

    logger.info(f"\n{'='*80}")
    logger.info("FULL PDF INGESTION - PHASE 1 MIGRATION")
    logger.info(f"{'='*80}\n")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")

    # Check input directory
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return False

    # Count PDF files
    pdf_files = list(input_dir.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files\n")

    if len(pdf_files) == 0:
        logger.warning("No PDF files found!")
        return False

    # Show first 5 files
    logger.info("Sample files:")
    for pdf in pdf_files[:5]:
        logger.info(f"  - {pdf.name}")
    if len(pdf_files) > 5:
        logger.info(f"  ... and {len(pdf_files) - 5} more\n")

    # Initialize processor with Google Cloud Vision OCR
    processor = PDFProcessor(
        extract_tables=False,  # Disabled for now
        extract_images=False,
        enable_ocr=True,  # Use Google Cloud Vision
        force_ocr_all_pages=False,  # Only OCR if needed
        min_text_length=10,
    )

    logger.info("Starting batch processing...\n")

    # Process all PDFs
    try:
        documents = processor.process_directory(
            directory=input_dir, pattern="*.pdf", recursive=False
        )

        logger.info(f"\n{'='*80}")
        logger.info(f"Processing complete!")
        logger.info(f"{'='*80}\n")
        logger.info(
            f"Successfully processed: {len(documents)}/{len(pdf_files)} documents"
        )

        if len(documents) < len(pdf_files):
            failed = len(pdf_files) - len(documents)
            logger.warning(f"Failed to process: {failed} documents")

        # Save processed documents
        logger.info(f"\nSaving processed documents to: {output_dir}")
        processor.save_processed_documents(documents, output_dir)

        logger.info(f"\n{'='*80}")
        logger.info("✅ INGESTION COMPLETE!")
        logger.info(f"{'='*80}\n")
        logger.success(f"Output: {output_dir}")

        # Show statistics
        total_pages = sum(doc.num_pages for doc in documents)
        total_chars = sum(doc.total_chars for doc in documents)

        logger.info(f"\nStatistics:")
        logger.info(f"  Total documents: {len(documents)}")
        logger.info(f"  Total pages: {total_pages}")
        logger.info(f"  Total characters: {total_chars:,}")
        logger.info(f"  Average pages/doc: {total_pages/len(documents):.1f}")

        return True

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        logger.exception(e)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
