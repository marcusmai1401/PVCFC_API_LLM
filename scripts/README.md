# PVCFC RAG Scripts

Utility and diagnostic scripts organized by purpose.

## 📁 Structure

```
scripts/
├── diagnostics/         # Diagnostic and debugging scripts
├── utilities/           # General utility scripts
├── weaviate/           # Weaviate-specific setup and testing
└── [existing]/         # phase1_index_to_weaviate.py, verify_weaviate_data.py, etc.
```

## 🔍 Diagnostics (`diagnostics/`)

Scripts for diagnosing and debugging issues:

- `check_pdf_pages.py` - Verify PDF page counts
- `check_s4274343.py` - Check specific document S4274343
- `check_truncated.py` - Check for truncated documents
- `deep_diagnostic.py` - Deep diagnostic analysis
- `diagnose_pages.py` - Diagnose page-related issues
- `find_invalid_pages.py` - Find invalid page references
- `map_all_pdf_pages.py` - Map all PDF pages in corpus
- `verify_high_pages.py` - Verify documents with high page numbers

**Usage:**
```bash
python scripts/diagnostics/check_pdf_pages.py
python scripts/diagnostics/deep_diagnostic.py
```

## 🛠️ Utilities (`utilities/`)

General-purpose utility scripts:

- `build_indices_safe.py` - Safe index building with validation
- `fix_doc_id_map.py` - Fix document ID mapping issues
- `validate_reingestion.py` - Validate document re-ingestion

**Usage:**
```bash
python scripts/utilities/build_indices_safe.py
python scripts/utilities/validate_reingestion.py
```

## 🔷 Weaviate (`weaviate/`)

Weaviate setup and testing scripts:

- `setup_weaviate_embedded.py` - Set up embedded Weaviate instance
- `test_weaviate_search.py` - Test Weaviate search functionality

**Usage:**
```bash
python scripts/weaviate/setup_weaviate_embedded.py
python scripts/weaviate/test_weaviate_search.py "CO2 compressor"
```

## 📝 Notes

- All scripts should be run from the project root directory
- Make sure virtual environment is activated before running
- See individual script headers for detailed usage instructions

---

For main documentation, see [../docs/README.md](../docs/README.md)
