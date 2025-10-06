"""
Production Ingestion Script for PVCFC Data
Ingests all PDFs from D:\Data_Raw with table extraction enabled
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    print("=" * 80)
    print("PVCFC PRODUCTION DATA INGESTION WITH TABLE EXTRACTION")
    print("=" * 80)
    print()

    # Configuration
    source_dir = r"D:\Data_Raw"
    output_dir = Path("artifacts/ingestion_production")

    # Verify source directory exists
    if not Path(source_dir).exists():
        print(f"❌ ERROR: Source directory not found: {source_dir}")
        return 1

    # Count PDFs
    pdf_count = len(list(Path(source_dir).rglob("*.pdf")))
    print(f"📁 Source directory: {source_dir}")
    print(f"📄 Total PDFs found: {pdf_count}")
    print(f"📦 Output directory: {output_dir}")
    print()

    # Ingestion parameters
    params = {
        "extract_tables": True,
        "table_min_rows": 2,
        "table_min_cols": 2,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "chunk_strategy": "hierarchical",
        "workers": 4,  # Parallel processing
        "ocr": False,  # Disable OCR initially
        "parser": "auto",
    }

    print("⚙️  INGESTION CONFIGURATION")
    print("-" * 80)
    print(
        f"  • Table extraction: {'✅ ENABLED' if params['extract_tables'] else '❌ DISABLED'}"
    )
    print(f"  • Table minimum: {params['table_min_rows']}x{params['table_min_cols']}")
    print(
        f"  • Chunk size: {params['chunk_size']} chars (overlap: {params['chunk_overlap']})"
    )
    print(f"  • Chunk strategy: {params['chunk_strategy']}")
    print(f"  • Workers: {params['workers']} parallel threads")
    print(f"  • OCR: {'✅ ENABLED' if params['ocr'] else '❌ DISABLED'}")
    print(f"  • Parser: {params['parser']}")
    print()

    # Confirm before proceeding
    print("⚠️  This will process 150 PDF files. Estimated time: 10-15 minutes")
    response = input("Continue? [y/N]: ")
    if response.lower() != "y":
        print("Cancelled by user.")
        return 0

    print()
    print("🚀 Starting ingestion...")
    print("-" * 80)

    # Build command
    cmd = [
        sys.executable,
        "tools/ingest.py",
        "--source-dir",
        source_dir,
        "--output-dir",
        str(output_dir),
        "--workers",
        str(params["workers"]),
        "--chunk-size",
        str(params["chunk_size"]),
        "--chunk-overlap",
        str(params["chunk_overlap"]),
        "--chunk-strategy",
        params["chunk_strategy"],
        "--parser",
        params["parser"],
    ]

    # Add table extraction flags
    if params["extract_tables"]:
        cmd.extend(
            [
                "--extract-tables",
                "--table-min-rows",
                str(params["table_min_rows"]),
                "--table-min-cols",
                str(params["table_min_cols"]),
            ]
        )

    # Add OCR flag if enabled
    if params["ocr"]:
        cmd.append("--ocr")

    # Add versioning flags
    cmd.extend(
        [
            "--create-version",
            "--version-id",
            "production_baseline",
            "--version-description",
            "Production ingestion from D:\\Data_Raw (150 PDFs)",
            "--version-tags",
            "production",
            "baseline",
        ]
    )

    # Run ingestion
    start_time = datetime.now()
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        result = subprocess.run(
            cmd, check=True, text=True, capture_output=False  # Stream output to console
        )

        end_time = datetime.now()
        duration = end_time - start_time

        print()
        print("=" * 80)
        print("✅ INGESTION COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"Duration: {duration}")
        print(f"Output location: {output_dir}")
        print()

        # Show output structure
        print("📊 OUTPUT STRUCTURE:")
        for subdir in ["chunks", "documents", "markdown", "manifests"]:
            dir_path = output_dir / subdir
            if dir_path.exists():
                file_count = len(list(dir_path.glob("*")))
                print(f"  • {subdir}/: {file_count} files")

        return 0

    except subprocess.CalledProcessError as e:
        print()
        print("=" * 80)
        print("❌ INGESTION FAILED")
        print("=" * 80)
        print(f"Error code: {e.returncode}")
        return 1

    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("⚠️  INGESTION INTERRUPTED BY USER")
        print("=" * 80)
        return 130


if __name__ == "__main__":
    sys.exit(main())
