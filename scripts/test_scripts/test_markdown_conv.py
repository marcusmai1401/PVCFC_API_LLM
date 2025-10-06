import json

from app.rag.converters.markdown_converter import MarkdownConverter

# Load processed document
doc_path = "artifacts/test_ingestion_tables/documents/DOCID_Data_Sheet_for_CO2_Compressor_Steam_Turbine.rev0E_ab13491a_processed.json"
with open(doc_path, encoding="utf-8") as f:
    doc = json.load(f)

# Create extraction data manually
extraction = {"file_path": doc["file_path"], "pages": []}

for page in doc["pages"]:
    page_data = {
        "page_num": page["page_num"] - 1,  # 0-indexed
        "full_text": page["text"],
        "blocks": [{"text": page["text"], "structure_type": "paragraph"}],
    }
    # Add tables if present
    if page.get("tables"):
        page_data["tables"] = page["tables"]
    extraction["pages"].append(page_data)

print(f"Extraction has {len(extraction['pages'])} pages")
pages_with_tables = [p for p in extraction["pages"] if p.get("tables")]
print(f"Pages with tables in extraction: {len(pages_with_tables)}")

# Convert to markdown
converter = MarkdownConverter()
md_result = converter.convert_with_structure(extraction)
markdown = md_result["markdown"]

# Check if TABLE markers are in markdown
has_markers = "TABLE START" in markdown
print(f"\nMarkdown has TABLE markers: {has_markers}")
print(f"Markdown length: {len(markdown)} chars")

if has_markers:
    print("\n✅ SUCCESS! Tables are in markdown with markers")
    # Find first table marker
    idx = markdown.find("TABLE START")
    print(f"\nSample table section:\n{markdown[idx:idx+500]}")
else:
    print("\n❌ PROBLEM: No TABLE markers in markdown")
    print("\nFirst 1000 chars of markdown:")
    print(markdown[:1000])
