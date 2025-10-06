import json

# Load processed document
doc_path = "artifacts/test_ingestion_tables/documents/DOCID_Data_Sheet_for_CO2_Compressor_Steam_Turbine.rev0E_ab13491a_processed.json"
with open(doc_path, encoding="utf-8") as f:
    doc = json.load(f)

# Check pages with tables
pages_with_tables = [p for p in doc["pages"] if p.get("tables")]

print(f"Total pages: {len(doc['pages'])}")
print(f"Pages with tables: {len(pages_with_tables)}")

if pages_with_tables:
    first = pages_with_tables[0]
    print(f"\nFirst page with tables: Page {first['page_num']}")
    print(f"Number of tables on this page: {len(first['tables'])}")
    print(f"First table keys: {list(first['tables'][0].keys())}")
    print(f"\nFirst table has markdown: {'markdown' in first['tables'][0]}")

    if "markdown" in first["tables"][0]:
        print(f"\nTable markdown sample (first 300 chars):")
        print(first["tables"][0]["markdown"][:300])
