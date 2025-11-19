import json
import shutil
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.append(r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC")

from tools.ingest import IngestionPipeline


def debug_ingestion():
    # Config
    source_pdf = Path(
        r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Data\002_3N4-S4274343 datasheet for K06101_Rev.02.pdf"
    )
    temp_input_dir = Path("debug_input_3")
    temp_output_dir = Path("debug_output_3")

    # Setup
    if temp_input_dir.exists():
        shutil.rmtree(temp_input_dir)
    if temp_output_dir.exists():
        shutil.rmtree(temp_output_dir)
    temp_input_dir.mkdir()

    # Copy PDF
    shutil.copy(source_pdf, temp_input_dir / source_pdf.name)
    print(f"Copied {source_pdf.name} to {temp_input_dir}")

    # Run Pipeline
    pipeline = IngestionPipeline(
        source_dir=temp_input_dir,
        output_dir=temp_output_dir,
        workers=1,
        enable_ocr=False,  # Disable OCR to check if it's a vector PDF
        extract_tables=True,
        emit_jsonl=True,
    )

    print("Running ingestion...")
    stats = pipeline.run()
    print(f"Ingestion finished. Stats: {stats}")

    # Analyze Output
    chunks_file = temp_output_dir / "chunks" / "chunks.jsonl"
    if not chunks_file.exists():
        print("Error: chunks.jsonl not found!")
        return

    print("\nAnalyzing chunks for Page 2...")
    found_target = False

    with open(chunks_file, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            page = chunk.get("metadata", {}).get("page")

            if page == 2:
                text = chunk.get("text", "")
                print(f"\n--- Chunk ID: {chunk['chunk_id']} (Page {page}) ---")
                print(text[:500] + "..." if len(text) > 500 else text)

                # Check for target data
                # Target: Discharge Pressure ... Normal ... 1st Stage ... 4.70
                lower_text = text.lower()
                if "discharge" in lower_text and "4.70" in text:
                    print("\n[!] FOUND TARGET DATA (4.70) IN THIS CHUNK!")
                    found_target = True
                else:
                    print("\n[ ] Target data (4.70) NOT found clearly in this chunk.")

    if not found_target:
        print(
            "\n[WARNING] Target data '4.70' (Discharge Pressure) was NOT found in any Page 2 chunk."
        )


if __name__ == "__main__":
    debug_ingestion()
