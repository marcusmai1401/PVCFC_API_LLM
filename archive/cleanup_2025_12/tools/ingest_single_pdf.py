"""
Ingest a single PDF for testing tag extraction and indexing.
Usage:
  python tools/ingest_single_pdf.py --pdf "D:\\Data_Raw\\...\\116_3N4-S4275354 Instrument List  _Rev.1.pdf" \
      --output artifacts/ingestion_test --chunk-size 1000 --chunk-overlap 200
"""
import argparse
import shutil
import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import tools.ingest
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="Absolute path to PDF")
    parser.add_argument("--output", default="artifacts/ingestion_test")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--parser", default="auto")
    parser.add_argument("--extract-tables", action="store_true")
    parser.add_argument(
        "--enable-ocr", action="store_true", help="Enable OCR for scanned PDFs"
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return 1

    # Create a staging directory that contains only this single PDF
    staging_dir = Path(args.output) / "_single_pdf_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    staged_pdf = staging_dir / pdf_path.name
    try:
        if staged_pdf.exists():
            staged_pdf.unlink()
        shutil.copy2(pdf_path, staged_pdf)
    except Exception as e:
        print(f"❌ Failed to stage PDF: {e}")
        return 1

    from tools.ingest import main as ingest_main

    # Build argv for ingest.py, pointing source-dir to staging folder
    ingest_argv = [
        "--source-dir",
        str(staging_dir),
        "--output-dir",
        args.output,
        "--chunk-size",
        str(args.chunk_size),
        "--chunk-overlap",
        str(args.chunk_overlap),
        "--chunk-strategy",
        "hierarchical",
        "--parser",
        args.parser,
    ]

    if args.extract_tables:
        ingest_argv.append("--extract-tables")

    if args.enable_ocr:
        ingest_argv.append("--enable-ocr")

    # Call ingest main with constructed argv
    sys.argv = ["tools/ingest.py"] + ingest_argv
    return ingest_main()


if __name__ == "__main__":
    sys.exit(main())
