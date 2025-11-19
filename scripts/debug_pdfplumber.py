import sys
from pathlib import Path

import pdfplumber


def test_pdfplumber():
    pdf_path = Path(
        r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Data\002_3N4-S4274343 datasheet for K06101_Rev.02.pdf"
    )

    print(f"Testing pdfplumber on {pdf_path}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Opened successfully. Pages: {len(pdf.pages)}")

            page = pdf.pages[1]  # Page 2 (index 1)
            print(f"Processing Page 2...")

            # Try extracting tables
            tables = page.extract_tables()
            print(f"Found {len(tables)} tables")

            for i, table in enumerate(tables):
                print(f"\n--- Table {i+1} ---")
                for row in table:
                    # Clean None values
                    clean_row = [cell if cell is not None else "" for cell in row]
                    print(clean_row)

                # Check for target data
                table_text = str(table)
                if "4.70" in table_text and "Discharge" in table_text:
                    print("\n[!] FOUND TARGET DATA IN TABLE!")

    except Exception as e:
        print(f"pdfplumber failed: {e}")


if __name__ == "__main__":
    test_pdfplumber()
