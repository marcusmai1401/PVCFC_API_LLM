"""Quick check: Is it TXI or TSAH on page 17?"""
import fitz

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
page_num = 17

doc = fitz.open(pdf_path)
page = doc[page_num - 1]
text = page.get_text()

print("=" * 80)
print(f"Page {page_num} Raw Text Search")
print("=" * 80)

# Check what's actually there
print(f"\n'TXI' found in text: {'TXI' in text}")
print(f"'TSAH' found in text: {'TSAH' in text}")
print(f"'2077' found in text: {'2077' in text}")

if "TSAH" in text:
    print("\n⚠️  PDF contains 'TSAH' not 'TXI'!")
    print("   This means ground truth has wrong prefix.")
    print("   The tag should be '04 TSAH 2077' not '04 TXI 2077'")

    # Find context
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "TSAH" in line or "2077" in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print(f"\n   Context around line {i}:")
            for j in range(start, end):
                marker = " →→→ " if j == i else "     "
                print(f"   {marker}{lines[j]}")
elif "TXI" in text:
    print("\n✓ PDF contains 'TXI'")
    # Find context
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "TXI" in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print(f"\n   Context around line {i}:")
            for j in range(start, end):
                marker = " →→→ " if j == i else "     "
                print(f"   {marker}{lines[j]}")

doc.close()
