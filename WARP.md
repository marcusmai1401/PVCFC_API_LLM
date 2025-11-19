# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a **RAG (Retrieval-Augmented Generation) System** for PVCFC (PetroVietnam Ca Mau Fertilizer Code) technical documentation.
It features a **Dual Pipeline** architecture that automatically distinguishes between:
1.  **Technical Documents** (Manuals, Datasheets, SOPs) - Processed via Standard Pipeline.
2.  **P&ID (Piping & Instrumentation Diagrams)** - Processed via Extended Pipeline (CAD-like Gate, Spatial Layout, Tag Extraction).

## Architecture & Tech Stack

*   **Backend:** FastAPI (`app/`) running on Uvicorn.
*   **Frontend:** Streamlit (`streamlit_app/`) for demos and testing.
*   **Database:**
    *   **Weaviate (Vector):** Stores semantic embeddings (Gemini/OpenAI).
    *   **OpenSearch (Keyword):** Stores BM25 indices for keyword search.
*   **OCR & Vision:** Google Cloud Vision API + Real-ESRGAN (2x upscaling) for scanned PDFs.
*   **LLM:** Gemini 1.5 Pro/Flash (via `google-generativeai`).
*   **Search Strategy:** Hybrid Retrieval (BM25 + Vector) + RRF Fusion + BGE Reranking.

### Key Directories
*   `app/`: Main application source code.
*   `scripts/`: Utility scripts for indexing, diagnostics, and Weaviate management.
*   `tools/`: Ingestion and build tools.
*   `launchers/`: PowerShell scripts to start services.
*   `Rules/`: Project-specific rules.

## Development Environment

*   **OS:** Windows (PowerShell is the primary shell).
*   **Python:** 3.11
*   **Virtual Environment:** `.venv` located in root.

### Setup
1.  **Create Virtual Environment:**
    ```powershell
    py -3.11 -m venv .venv
    ```
2.  **Activate:**
    ```powershell
    .venv\Scripts\Activate.ps1
    ```
3.  **Install Dependencies:**
    ```powershell
    pip install -r requirements.txt
    ```
4.  **Environment Variables:**
    Copy `.env.example` to `.env` and configure API keys (Gemini, OpenAI, etc.).

## Common Commands

### Running the Application
*   **Start API Server:**
    ```powershell
    make run
    # OR
    .\launchers\start_api.ps1
    ```
    Server runs on `http://localhost:8000`.

*   **Start Streamlit UI (if available):**
    ```powershell
    streamlit run streamlit_app/app.py
    ```

### Testing
*   **Run Unit Tests:**
    ```powershell
    make test
    # OR
    pytest tests/
    ```

### Data Ingestion & Indexing
*   **Ingest Documents (Phase 1):**
    ```powershell
    python tools/ingest.py --source-dir "D:\Data_Raw" --output-dir "D:\PVCFC_Artifacts\ingestion_production" --enable-ocr --enable-pid-tags
    ```
*   **Build Indices (Phase 2):**
    ```powershell
    # Create OpenSearch indexes
    python scripts/opensearch/create_rag_chunks_index.py --delete-if-exists

    # Index chunks to Weaviate + OpenSearch
    python scripts/utilities/index_production_chunks.py
    ```

## User Rules (Critical)
*Derived from `Rules/Rules for AI Agent.txt`*

1.  **Code Style:** Do NOT use icons or emojis in code comments or strings.
2.  **Changelog (Immediate):** After code changes, write a description file in `CHANGELOG_README` (create folder if missing).
3.  **Documentation:** Use `docs/` folder (or `DOCUMENTS_CHATBOX/docs/` if applicable) to store development notes and debugging info.
4.  **Phase Completion:** Upon completing a phase, summarize into a markdown file in `CHANGELOG_README`.
5.  **Planning:** Follow `Build_plan_README` (if present) for phase execution.

## Troubleshooting
*   **LS/Dir:** Use `ls` (PowerShell alias for `Get-ChildItem`) without Unix flags like `-F`.
*   **Paging:** Git and other commands may use pagers. Use `--no-pager` where possible or pipe to `cat` (e.g., `git --no-pager log`).
