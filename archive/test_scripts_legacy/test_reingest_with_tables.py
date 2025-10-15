"""
Test Re-ingestion with Table Extraction
Task 7: Re-ingest documents with table extraction enabled and verify results
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def run_ingestion_test():
    """Run test ingestion with table extraction"""

    print("\n" + "=" * 80)
    print("TASK 7: RE-INGESTION TEST WITH TABLE EXTRACTION")
    print("=" * 80 + "\n")

    # Define paths
    source_dir = Path("data/raw/phase1_pilot")
    output_dir = Path("artifacts/test_ingestion_tables")

    if not source_dir.exists():
        print(f"❌ ERROR: Source directory not found: {source_dir}")
        return False

    # Clean output directory if exists
    if output_dir.exists():
        print(f"Cleaning previous output: {output_dir}")
        import shutil

        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print(f"Table extraction: ENABLED")
    print()

    # Run ingestion with table extraction
    cmd = [
        sys.executable,
        "tools/ingest.py",
        "--source-dir",
        str(source_dir),
        "--output-dir",
        str(output_dir),
        "--workers",
        "2",
        "--extract-tables",  # Enable table extraction
        "--table-min-rows",
        "2",
        "--table-min-cols",
        "2",
        "--chunk-size",
        "1000",
        "--chunk-overlap",
        "200",
        "--chunk-strategy",
        "hierarchical",
    ]

    print("Running ingestion...")
    print(f"Command: {' '.join(cmd)}\n")
    print("─" * 80)

    start_time = datetime.now()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        duration = (datetime.now() - start_time).total_seconds()

        # Print stdout
        if result.stdout:
            print(result.stdout)

        # Print stderr (loguru output)
        if result.stderr:
            print(result.stderr)

        print("─" * 80)
        print(f"\nIngestion completed in {duration:.1f}s")
        print(f"Exit code: {result.returncode}")

        if result.returncode != 0:
            print("❌ Ingestion failed!")
            return False

        print("✓ Ingestion succeeded\n")

    except Exception as e:
        print(f"❌ ERROR running ingestion: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Verify outputs
    print("=" * 80)
    print("VERIFYING OUTPUTS")
    print("=" * 80 + "\n")

    checks = {}

    # Check directories exist
    chunks_dir = output_dir / "chunks"
    documents_dir = output_dir / "documents"
    markdown_dir = output_dir / "markdown"
    manifests_dir = output_dir / "manifests"

    checks["Chunks directory"] = chunks_dir.exists()
    checks["Documents directory"] = documents_dir.exists()
    checks["Markdown directory"] = markdown_dir.exists()
    checks["Manifests directory"] = manifests_dir.exists()

    # Check for files
    if chunks_dir.exists():
        chunk_files = list(chunks_dir.glob("*.json"))
        checks[f"Chunk files created"] = len(chunk_files) > 0
        if chunk_files:
            print(f"✓ Found {len(chunk_files)} chunk files")

    if documents_dir.exists():
        doc_files = list(documents_dir.glob("*.json"))
        checks["Document files created"] = len(doc_files) > 0
        if doc_files:
            print(f"✓ Found {len(doc_files)} document files")

    # Check manifests
    corpus_manifest = manifests_dir / "corpus.jsonl"
    checksums_manifest = manifests_dir / "checksums.jsonl"

    checks["Corpus manifest"] = corpus_manifest.exists()
    checks["Checksums manifest"] = checksums_manifest.exists()

    # Verify tables in chunks
    print(f"\nAnalyzing chunks for table content...")

    tables_found = 0
    chunks_with_tables = 0
    total_chunks = 0

    if chunks_dir.exists():
        for chunk_file in chunks_dir.glob("*_chunks.json"):
            try:
                with open(chunk_file, "r", encoding="utf-8") as f:
                    chunks = json.load(f)

                total_chunks += len(chunks)

                for chunk in chunks:
                    # Check if chunk has table markers
                    chunk_text = chunk.get("text", "")

                    if "<!-- TABLE" in chunk_text and "|" in chunk_text:
                        chunks_with_tables += 1

                        # Count tables in this chunk
                        tables_in_chunk = chunk_text.count("<!-- TABLE")
                        tables_found += tables_in_chunk

            except Exception as e:
                logger.warning(f"Error reading {chunk_file}: {e}")

    print(f"✓ Total chunks: {total_chunks}")
    print(f"✓ Chunks with tables: {chunks_with_tables}")
    print(f"✓ Tables found: {tables_found}")

    checks["Chunks analyzed"] = total_chunks > 0
    checks["Tables detected"] = tables_found > 0

    # Print verification summary
    print(f"\n{'='*80}")
    print("VERIFICATION RESULTS")
    print(f"{'='*80}\n")

    all_passed = True
    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False

    # Summary stats
    print(f"\n{'─'*80}")
    print("Summary:")
    print(f"  - Total chunks: {total_chunks}")
    print(f"  - Chunks with tables: {chunks_with_tables}")
    print(f"  - Table markers found: {tables_found}")
    print(
        f"  - Table coverage: {chunks_with_tables/total_chunks*100:.1f}%"
        if total_chunks > 0
        else "  - Table coverage: N/A"
    )
    print(f"{'─'*80}\n")

    return all_passed


def analyze_sample_chunks():
    """Analyze and show sample chunks with tables"""

    print("=" * 80)
    print("SAMPLE CHUNK ANALYSIS")
    print("=" * 80 + "\n")

    output_dir = Path("artifacts/test_ingestion_tables")
    chunks_dir = output_dir / "chunks"

    if not chunks_dir.exists():
        print("No chunks directory found")
        return

    # Find first chunk file with tables
    for chunk_file in chunks_dir.glob("*_chunks.json"):
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)

            # Find chunk with table
            for chunk in chunks:
                if "<!-- TABLE" in chunk.get("text", ""):
                    print(f"File: {chunk_file.name}")
                    print(f"Chunk ID: {chunk.get('chunk_id', 'N/A')}")
                    print(f"Doc ID: {chunk.get('doc_id', 'N/A')}")
                    print(f"Size: {chunk.get('char_count', 0)} chars")
                    print(f"Metadata: {chunk.get('metadata', {})}")
                    print(f"\nChunk text preview:")
                    print("─" * 80)

                    text = chunk.get("text", "")

                    # Find table section
                    start = text.find("<!-- TABLE")
                    if start >= 0:
                        # Show some context before table
                        context_start = max(0, start - 100)
                        context_end = min(len(text), start + 500)
                        preview = text[context_start:context_end]

                        print(preview)
                        if context_end < len(text):
                            print("... (truncated)")

                    print("─" * 80)

                    # Only show first example
                    return

        except Exception as e:
            continue

    print("No chunks with tables found")


if __name__ == "__main__":
    print("\n" + "█" * 80)
    print("TASK 7: RE-INGESTION WITH TABLE EXTRACTION")
    print("█" * 80)

    # Run test
    success = run_ingestion_test()

    # Analyze samples if successful
    if success:
        analyze_sample_chunks()

    # Final result
    print("\n" + "█" * 80)
    print(f"RESULT: {'✓ TEST PASSED' if success else '✗ TEST FAILED'}")
    print("█" * 80 + "\n")

    sys.exit(0 if success else 1)
