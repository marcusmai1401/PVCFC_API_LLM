"""
Ingest Panel Component - One-click document ingestion and OCR
"""

from datetime import datetime

import pandas as pd
import streamlit as st


def render():
    """Render ingest panel component"""
    st.header("📥 Ingest Panel")
    st.caption("Upload and process documents with automatic OCR and indexing")

    # Main layout
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Document Input")

        # Input method
        input_method = st.radio(
            "Input Method", ["File Upload", "Folder Path"], horizontal=True
        )

        if input_method == "File Upload":
            uploaded_files = st.file_uploader(
                "Select documents",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
                help="Upload PDF or image files for processing",
            )

            if uploaded_files:
                st.info(f"📁 {len(uploaded_files)} file(s) selected")
                for file in uploaded_files:
                    st.caption(f"• {file.name} ({file.size/1024:.1f} KB)")
        else:
            folder_path = st.text_input(
                "Folder Path",
                placeholder="e.g., C:\\Documents\\PDFs",
                help="Absolute path to folder containing documents",
            )

        # OCR Settings
        st.subheader("Processing Options")

        ocr_mode = st.selectbox(
            "OCR Mode",
            ["Auto (Detect)", "Force OCR", "Skip OCR"],
            help="Auto: OCR only for scanned pages",
        )

        language = st.selectbox(
            "OCR Language",
            ["Vietnamese", "English", "Multi-language"],
            help="Primary language for OCR",
        )

        # Chunking settings
        with st.expander("Advanced Settings"):
            chunk_size = st.slider("Chunk Size (tokens)", 100, 1000, 500)
            hierarchical = st.checkbox("Hierarchical Chunking", value=True)

            # Index options
            st.write("Index Options")
            build_bm25 = st.checkbox("Build BM25 Index", value=True)
            build_faiss = st.checkbox("Build FAISS Index", value=True)

            if build_faiss:
                embedding_provider = st.selectbox(
                    "Embedding Provider",
                    ["OpenAI", "Local (sentence-transformers)", "Gemini"],
                )

        # Collection name
        collection = st.text_input(
            "Collection Name (optional)",
            placeholder="e.g., pilot_docs_v1",
            help="Name for this document collection",
        )

        # Start button
        if st.button("🚀 Start Ingestion", type="primary", use_container_width=True):
            if input_method == "File Upload" and uploaded_files:
                with st.spinner("Starting ingestion job..."):
                    # TODO: Implement API call in Phase 3
                    st.success("Ingestion started! Job ID: ing-20250916-demo")
                    st.info("Phase 3 will implement actual ingestion")
            elif input_method == "Folder Path" and folder_path:
                with st.spinner("Starting ingestion job..."):
                    st.success("Ingestion started! Job ID: ing-20250916-demo")
                    st.info("Phase 3 will implement actual ingestion")
            else:
                st.warning("Please select files or specify folder path")

    with col2:
        st.subheader("Job Status")

        # Job monitoring tabs
        active_tab, history_tab, logs_tab = st.tabs(["Active Jobs", "History", "Logs"])

        with active_tab:
            # Sample active job
            st.info("🔄 Active ingestion jobs will appear here")

            # Placeholder for active job
            with st.container():
                st.write("**Job: ing-20250916-demo**")
                progress = st.progress(0.65)
                st.caption("Status: Running | Stage: Chunking | Progress: 65%")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Pages", "124")
                with col2:
                    st.metric("Chunks", "580")
                with col3:
                    st.metric("Time", "92s")

                # Action buttons
                action_col1, action_col2 = st.columns(2)
                with action_col1:
                    st.button("Cancel", disabled=True, use_container_width=True)
                with action_col2:
                    st.button("View Logs", use_container_width=True)

        with history_tab:
            # Job history table
            st.info("📋 Completed jobs will be listed here")

            # Sample history
            history_data = {
                "Job ID": ["ing-20250916-001", "ing-20250916-002"],
                "Status": ["✅ Success", "❌ Failed"],
                "Documents": [12, 8],
                "Duration": ["3m 24s", "1m 12s"],
                "Date": [datetime.now().strftime("%Y-%m-%d %H:%M")] * 2,
            }

            df = pd.DataFrame(history_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

        with logs_tab:
            st.info("📜 Job logs will stream here")

            # Sample log output
            with st.expander("Sample Log Output"):
                st.code(
                    """
[2025-09-16 10:30:15] Starting ingestion job ing-20250916-demo
[2025-09-16 10:30:16] Processing 12 documents
[2025-09-16 10:30:17] Document 1/12: sample.pdf
[2025-09-16 10:30:18] - Detected as vector PDF
[2025-09-16 10:30:19] - Extracted 45 pages
[2025-09-16 10:30:22] - Created 120 chunks
[2025-09-16 10:30:23] Document 2/12: scan.pdf
[2025-09-16 10:30:24] - Detected as scanned PDF
[2025-09-16 10:30:25] - Running OCR (Vietnamese)...
                """,
                    language="log",
                )

    # Index management
    st.divider()
    st.subheader("Index Management")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Reload Indices", use_container_width=True):
            with st.spinner("Reloading..."):
                st.success("Indices reloaded")

    with col2:
        if st.button("📊 View Stats", use_container_width=True):
            st.info("Phase 3 will show index statistics")

    with col3:
        if st.button("📸 Snapshots", use_container_width=True):
            st.info("Phase 3 will show index snapshots")

    with col4:
        if st.button("⏮️ Rollback", use_container_width=True):
            st.info("Phase 3 will enable rollback")
