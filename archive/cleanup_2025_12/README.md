# Cleanup Archive - December 2025

## Date: 2025-12-03

## Purpose
Archived non-essential files from production codebase to reduce clutter.

## Archived Folders

| Folder | Files | Description |
|--------|-------|-------------|
| `data/` | 1,394 | Old test data (production uses D:\PVCFC_Artifacts) |
| `logs/` | 220 | Old log files |
| `tests/` | 165 | Test files (unit, integration, manual) |
| `utilities/` | 6 | Old utility scripts |
| `launchers/` | 14 | Non-essential launcher scripts |
| `scripts/` | 211 | Debug/test/one-time scripts |
| `tools/` | 83 | Analysis/debug tools |

## Essential Files KEPT in Production

### launchers/
- `start_api.ps1` - Start API server
- `start_ui.ps1` - Start Streamlit UI

### tools/
- `ingest.py` - Main ingestion pipeline
- `pdf_renderer.py` - PDF rendering (used by API)
- `reindex_pid_tags.py` - P&ID tag reindexing

### scripts/
- `opensearch/create_rag_chunks_index.py` - Create OpenSearch index
- `opensearch/create_spatial_components_index.py` - Create spatial index
- `utilities/index_production_chunks.py` - Index chunks to databases

## Recovery
To restore any file, move it from this archive back to the original location.

Example:
```powershell
Move-Item "archive\cleanup_2025_12\tools\some_tool.py" "tools\some_tool.py"
```
