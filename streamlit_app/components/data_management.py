"""
📁 Data Management Component

Utilities for importing/exporting annotation data, evaluation results,
and managing document collections for the RAG pipeline.
"""

import base64
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


def show_data_management():
    """Display the data management interface."""
    st.title("📁 Data Management - Import/Export & Organization")

    st.markdown(
        """
    Manage your data efficiently with tools for importing/exporting QA datasets,
    evaluation results, and organizing document collections for your RAG pipeline.
    """
    )

    # Tabs for different data management functions
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📊 Dataset Management",
            "📋 Evaluation Data",
            "📚 Document Collections",
            "🔄 Batch Operations",
        ]
    )

    with tab1:
        show_dataset_management()

    with tab2:
        show_evaluation_data_management()

    with tab3:
        show_document_collections()

    with tab4:
        show_batch_operations()


def show_dataset_management():
    """Show dataset management interface."""
    st.markdown("### 📊 Dataset Management")

    st.markdown(
        """
    Manage your QA datasets for training and evaluation. Import from various sources,
    validate quality, and export in multiple formats.
    """
    )

    # Dataset overview
    col1, col2 = st.columns([2, 1])

    with col1:
        # Current datasets
        st.markdown("#### 📋 Current Datasets")

        if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
            dataset_info = analyze_dataset(st.session_state.qa_dataset)

            # Dataset summary
            col_a, col_b, col_c, col_d = st.columns(4)

            with col_a:
                st.metric("Total QA Pairs", dataset_info["total"])

            with col_b:
                st.metric("Avg Query Length", f"{dataset_info['avg_query_length']:.0f}")

            with col_c:
                st.metric("Most Common Intent", dataset_info["top_intent"])

            with col_d:
                st.metric(
                    "Quality Score",
                    f"{dataset_info['avg_quality']:.2f}"
                    if dataset_info["avg_quality"]
                    else "N/A",
                )

            # Quality breakdown
            st.markdown("**📈 Quality Distribution**")
            quality_data = get_quality_distribution(st.session_state.qa_dataset)

            if quality_data:
                df_quality = pd.DataFrame(quality_data)
                st.bar_chart(df_quality.set_index("Quality Range")["Count"])
            else:
                st.info(
                    "No quality scores available. Rate your QA pairs in the annotation interface."
                )

        else:
            st.info(
                "📝 No datasets available. Create QA pairs in the annotation interface or import existing data."
            )

    with col2:
        # Quick actions
        st.markdown("#### ⚡ Quick Actions")

        if st.button("🔍 Validate Dataset"):
            if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
                validation_results = validate_dataset(st.session_state.qa_dataset)
                show_validation_summary(validation_results)
            else:
                st.warning("No dataset to validate.")

        if st.button("📊 Generate Report"):
            if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
                report_data = generate_dataset_report(st.session_state.qa_dataset)
                show_dataset_report(report_data)
            else:
                st.warning("No dataset to report on.")

        if st.button("🧹 Clean Dataset"):
            if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
                cleaned_data = clean_dataset(st.session_state.qa_dataset)
                st.session_state.qa_dataset = cleaned_data
                st.success(
                    f"✅ Dataset cleaned! Removed duplicates and invalid entries."
                )
            else:
                st.warning("No dataset to clean.")

    st.markdown("---")

    # Import/Export section
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📥 Import Dataset")

        import_format = st.selectbox(
            "Import Format", ["JSON", "JSONL", "CSV", "Excel", "HuggingFace Dataset"]
        )

        uploaded_file = st.file_uploader(
            "Upload dataset file",
            type=["json", "jsonl", "csv", "xlsx", "xls"],
            help=f"Upload a {import_format} file containing QA pairs",
        )

        if uploaded_file is not None:
            try:
                imported_data = import_dataset(uploaded_file, import_format.lower())

                st.success(f"✅ Successfully imported {len(imported_data)} QA pairs!")

                # Preview imported data
                if st.checkbox("👀 Preview imported data"):
                    preview_df = pd.DataFrame(imported_data[:5])
                    st.dataframe(preview_df)

                # Import options
                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button("🔄 Replace Current Dataset"):
                        st.session_state.qa_dataset = imported_data
                        st.success("✅ Dataset replaced!")
                        st.rerun()

                with col_b:
                    if st.button("➕ Merge with Current"):
                        if "qa_dataset" not in st.session_state:
                            st.session_state.qa_dataset = []

                        original_count = len(st.session_state.qa_dataset)
                        st.session_state.qa_dataset.extend(imported_data)
                        new_count = len(st.session_state.qa_dataset)

                        st.success(
                            f"✅ Merged! Dataset now has {new_count} items (added {new_count - original_count})."
                        )
                        st.rerun()

            except Exception as e:
                st.error(f"❌ Import failed: {str(e)}")

    with col2:
        st.markdown("#### 📤 Export Dataset")

        if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
            export_format = st.selectbox(
                "Export Format",
                ["JSON", "JSONL", "CSV", "Excel", "HuggingFace Dataset", "ZIP Archive"],
            )

            # Export options
            with st.expander("🔧 Export Options"):
                include_metadata = st.checkbox("Include metadata", value=True)
                include_quality_scores = st.checkbox(
                    "Include quality scores", value=True
                )
                filter_by_quality = st.checkbox(
                    "Filter by quality threshold", value=False
                )

                if filter_by_quality:
                    quality_threshold = st.slider(
                        "Minimum quality score",
                        min_value=0.0,
                        max_value=10.0,
                        value=7.0,
                        step=0.1,
                    )

            if st.button("📦 Generate Export"):
                # Apply filters
                export_data = st.session_state.qa_dataset.copy()

                if filter_by_quality:
                    export_data = [
                        qa
                        for qa in export_data
                        if qa.get("quality_score", 0) >= quality_threshold
                    ]

                # Generate export
                export_content = generate_export(
                    export_data,
                    export_format.lower(),
                    include_metadata,
                    include_quality_scores,
                )

                filename = f"qa_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                if export_format == "ZIP Archive":
                    st.download_button(
                        label="⬇️ Download ZIP Archive",
                        data=export_content,
                        file_name=f"{filename}.zip",
                        mime="application/zip",
                    )
                else:
                    file_ext = {
                        "json": "json",
                        "jsonl": "jsonl",
                        "csv": "csv",
                        "excel": "xlsx",
                        "huggingface dataset": "json",
                    }[export_format.lower()]

                    mime_type = {
                        "json": "application/json",
                        "jsonl": "application/jsonl",
                        "csv": "text/csv",
                        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    }.get(file_ext, "application/octet-stream")

                    st.download_button(
                        label=f"⬇️ Download {export_format}",
                        data=export_content,
                        file_name=f"{filename}.{file_ext}",
                        mime=mime_type,
                    )

                st.success(
                    f"✅ Exported {len(export_data)} QA pairs in {export_format} format!"
                )

        else:
            st.info("📝 No dataset available for export.")


def show_evaluation_data_management():
    """Show evaluation data management interface."""
    st.markdown("### 📋 Evaluation Data Management")

    st.markdown(
        """
    Manage evaluation results, benchmark datasets, and performance tracking data.
    """
    )

    # Evaluation results management
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 Evaluation Results")

        # Upload evaluation results
        uploaded_results = st.file_uploader(
            "Upload evaluation results",
            type=["json", "jsonl"],
            help="Upload batch evaluation results for analysis",
        )

        if uploaded_results is not None:
            try:
                results_data = json.loads(uploaded_results.getvalue().decode("utf-8"))

                # Store in session state
                st.session_state.evaluation_results = results_data

                st.success(f"✅ Loaded evaluation results!")

                # Results summary
                if isinstance(results_data, list):
                    total_queries = len(results_data)
                    success_rate = (
                        sum(1 for r in results_data if not r.get("has_error", False))
                        / total_queries
                    )
                    avg_response_time = (
                        sum(r.get("total_latency_ms", 0) for r in results_data)
                        / total_queries
                        / 1000
                    )

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Total Queries", total_queries)
                    with col_b:
                        st.metric("Success Rate", f"{success_rate:.1%}")
                    with col_c:
                        st.metric("Avg Response Time", f"{avg_response_time:.2f}s")

            except Exception as e:
                st.error(f"❌ Failed to load results: {str(e)}")

        # Results history
        if "evaluation_results" in st.session_state:
            st.markdown("**📈 Results Management**")

            if st.button("📊 Analyze Results"):
                st.info("📊 Analysis available in Evaluation Results tab")

            if st.button("💾 Export Results"):
                results_json = json.dumps(st.session_state.evaluation_results, indent=2)
                st.download_button(
                    "⬇️ Download Results",
                    results_json,
                    f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    "application/json",
                )

    with col2:
        st.markdown("#### 🎯 Benchmark Datasets")

        # Benchmark dataset management
        benchmark_datasets = {
            "MS MARCO": {
                "description": "Microsoft machine reading comprehension dataset",
                "size": "1M+ queries",
            },
            "Natural Questions": {
                "description": "Real questions from Google Search",
                "size": "300K+ questions",
            },
            "SQuAD 2.0": {
                "description": "Stanford Question Answering Dataset",
                "size": "150K+ questions",
            },
            "BEIR": {
                "description": "Benchmark for Information Retrieval",
                "size": "Multiple datasets",
            },
        }

        selected_benchmark = st.selectbox(
            "Select benchmark dataset", list(benchmark_datasets.keys())
        )

        if selected_benchmark:
            dataset_info = benchmark_datasets[selected_benchmark]
            st.markdown(f"**Description:** {dataset_info['description']}")
            st.markdown(f"**Size:** {dataset_info['size']}")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(f"📥 Import {selected_benchmark}"):
                    st.info(f"🚧 Integration with {selected_benchmark} coming soon!")

            with col_b:
                if st.button("🔗 View Documentation"):
                    st.info(f"📖 Opening {selected_benchmark} documentation...")

        # Custom benchmark creation
        st.markdown("**🛠️ Create Custom Benchmark**")

        with st.form("create_benchmark"):
            benchmark_name = st.text_input("Benchmark Name")
            benchmark_desc = st.text_area("Description", height=80)

            if st.form_submit_button("🎯 Create Benchmark"):
                if benchmark_name:
                    if "custom_benchmarks" not in st.session_state:
                        st.session_state.custom_benchmarks = []

                    benchmark = {
                        "name": benchmark_name,
                        "description": benchmark_desc,
                        "created_at": datetime.now().isoformat(),
                        "queries": [],
                    }

                    st.session_state.custom_benchmarks.append(benchmark)
                    st.success(f"✅ Created benchmark: {benchmark_name}")
                else:
                    st.error("Please provide a benchmark name")


def show_document_collections():
    """Show document collections management."""
    st.markdown("### 📚 Document Collections")

    st.markdown(
        """
    Manage document collections for your RAG knowledge base.
    Upload, organize, and process documents for optimal retrieval.
    """
    )

    # Document upload section
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### 📁 Upload Documents")

        # Bulk document upload
        uploaded_docs = st.file_uploader(
            "Upload documents",
            accept_multiple_files=True,
            type=["pdf", "txt", "docx", "md", "html"],
            help="Upload multiple documents to add to your knowledge base",
        )

        if uploaded_docs:
            st.success(f"📄 Selected {len(uploaded_docs)} documents")

            # Processing options
            with st.expander("🔧 Processing Options"):
                chunk_size = st.slider("Chunk size (characters)", 500, 2000, 1000)
                chunk_overlap = st.slider("Chunk overlap", 50, 500, 200)

                extract_metadata = st.checkbox("Extract metadata", value=True)
                auto_categorize = st.checkbox("Auto-categorize documents", value=False)

                if auto_categorize:
                    categories = st.multiselect(
                        "Available categories",
                        ["technical", "business", "legal", "medical", "general"],
                        default=["general"],
                    )

            if st.button("🚀 Process Documents"):
                # Simulate document processing
                processed_docs = []

                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, doc in enumerate(uploaded_docs):
                    status_text.text(f"Processing {doc.name}...")
                    progress_bar.progress((i + 1) / len(uploaded_docs))

                    # Simulate processing
                    doc_info = {
                        "filename": doc.name,
                        "size": len(doc.getvalue()),
                        "type": doc.name.split(".")[-1],
                        "processed_at": datetime.now().isoformat(),
                        "chunks": max(1, len(doc.getvalue()) // chunk_size),
                        "metadata": {"category": "general"}
                        if not auto_categorize
                        else {"category": categories[0] if categories else "general"},
                    }
                    processed_docs.append(doc_info)

                status_text.text("✅ Processing complete!")

                # Store processed documents
                if "document_collection" not in st.session_state:
                    st.session_state.document_collection = []

                st.session_state.document_collection.extend(processed_docs)

                st.success(f"✅ Processed {len(processed_docs)} documents!")

    with col2:
        st.markdown("#### 📊 Collection Stats")

        if (
            "document_collection" in st.session_state
            and st.session_state.document_collection
        ):
            docs = st.session_state.document_collection

            total_docs = len(docs)
            total_chunks = sum(doc.get("chunks", 0) for doc in docs)
            total_size = sum(doc.get("size", 0) for doc in docs)

            st.metric("Total Documents", total_docs)
            st.metric("Total Chunks", total_chunks)
            st.metric("Total Size", f"{total_size / 1024 / 1024:.1f} MB")

            # Document types
            doc_types = {}
            for doc in docs:
                doc_type = doc.get("type", "unknown")
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

            st.markdown("**📄 Document Types**")
            for doc_type, count in doc_types.items():
                st.metric(doc_type.upper(), count)

        else:
            st.info("📚 No documents uploaded yet")

    # Document list
    if (
        "document_collection" in st.session_state
        and st.session_state.document_collection
    ):
        st.markdown("---")
        st.markdown("#### 📋 Document Collection")

        # Filter options
        col1, col2, col3 = st.columns(3)

        with col1:
            filter_type = st.selectbox(
                "Filter by type",
                ["All"]
                + list(
                    set(
                        doc.get("type", "")
                        for doc in st.session_state.document_collection
                    )
                ),
            )

        with col2:
            filter_category = st.selectbox(
                "Filter by category",
                ["All"]
                + list(
                    set(
                        doc.get("metadata", {}).get("category", "")
                        for doc in st.session_state.document_collection
                    )
                ),
            )

        with col3:
            sort_by = st.selectbox(
                "Sort by", ["filename", "size", "processed_at", "chunks"]
            )

        # Filter and display documents
        filtered_docs = st.session_state.document_collection

        if filter_type != "All":
            filtered_docs = [
                doc for doc in filtered_docs if doc.get("type") == filter_type
            ]

        if filter_category != "All":
            filtered_docs = [
                doc
                for doc in filtered_docs
                if doc.get("metadata", {}).get("category") == filter_category
            ]

        # Sort documents
        if sort_by in ["size", "chunks"]:
            filtered_docs = sorted(
                filtered_docs, key=lambda x: x.get(sort_by, 0), reverse=True
            )
        else:
            filtered_docs = sorted(filtered_docs, key=lambda x: x.get(sort_by, ""))

        # Display document table
        doc_df = pd.DataFrame(filtered_docs)
        if not doc_df.empty:
            st.dataframe(
                doc_df[["filename", "type", "size", "chunks", "processed_at"]],
                use_container_width=True,
            )
        else:
            st.info("No documents match the current filters")


def show_batch_operations():
    """Show batch operations interface."""
    st.markdown("### 🔄 Batch Operations")

    st.markdown(
        """
    Perform bulk operations on your datasets and documents.
    Useful for large-scale data processing and maintenance tasks.
    """
    )

    # Batch operation types
    operation_type = st.selectbox(
        "Select batch operation",
        [
            "Validate All Datasets",
            "Clean and Deduplicate",
            "Batch Quality Assessment",
            "Format Conversion",
            "Metadata Extraction",
            "Backup Creation",
        ],
    )

    if operation_type == "Validate All Datasets":
        show_batch_validation()
    elif operation_type == "Clean and Deduplicate":
        show_batch_cleaning()
    elif operation_type == "Batch Quality Assessment":
        show_batch_quality_assessment()
    elif operation_type == "Format Conversion":
        show_batch_format_conversion()
    elif operation_type == "Metadata Extraction":
        show_batch_metadata_extraction()
    else:  # Backup Creation
        show_backup_creation()


def show_batch_validation():
    """Show batch validation interface."""
    st.markdown("#### ✅ Validate All Datasets")

    if st.button("🚀 Run Validation"):
        datasets_to_validate = []

        if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
            datasets_to_validate.append(("QA Dataset", st.session_state.qa_dataset))

        if (
            "custom_benchmarks" in st.session_state
            and st.session_state.custom_benchmarks
        ):
            for benchmark in st.session_state.custom_benchmarks:
                datasets_to_validate.append(
                    (f"Benchmark: {benchmark['name']}", benchmark.get("queries", []))
                )

        if not datasets_to_validate:
            st.warning("No datasets available for validation")
            return

        st.markdown("**🔍 Validation Results:**")

        for dataset_name, dataset in datasets_to_validate:
            with st.expander(f"📊 {dataset_name}"):
                validation_results = validate_dataset(dataset)
                show_validation_summary(validation_results)


def show_batch_cleaning():
    """Show batch cleaning interface."""
    st.markdown("#### 🧹 Clean and Deduplicate")

    cleaning_options = st.multiselect(
        "Select cleaning operations",
        [
            "Remove duplicates",
            "Fix encoding issues",
            "Normalize text",
            "Remove empty entries",
            "Validate required fields",
        ],
        default=["Remove duplicates", "Remove empty entries"],
    )

    if st.button("🚀 Run Cleaning") and cleaning_options:
        if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
            original_count = len(st.session_state.qa_dataset)

            # Apply cleaning operations
            cleaned_data = st.session_state.qa_dataset.copy()

            if "Remove duplicates" in cleaning_options:
                seen_queries = set()
                cleaned_data = []
                for qa in st.session_state.qa_dataset:
                    if qa.get("query") not in seen_queries:
                        cleaned_data.append(qa)
                        seen_queries.add(qa.get("query"))

            if "Remove empty entries" in cleaning_options:
                cleaned_data = [
                    qa
                    for qa in cleaned_data
                    if qa.get("query", "").strip()
                    and qa.get("expected_behavior", "").strip()
                ]

            st.session_state.qa_dataset = cleaned_data
            new_count = len(st.session_state.qa_dataset)

            st.success(
                f"✅ Cleaning complete! Reduced from {original_count} to {new_count} entries ({original_count - new_count} removed)"
            )
        else:
            st.warning("No QA dataset available for cleaning")


def show_batch_quality_assessment():
    """Show batch quality assessment interface."""
    st.markdown("#### 🏆 Batch Quality Assessment")

    if st.button("🚀 Assess Quality"):
        if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
            progress_bar = st.progress(0)
            status_text = st.empty()

            assessed_count = 0

            for i, qa in enumerate(st.session_state.qa_dataset):
                status_text.text(f"Assessing quality for item {i + 1}...")
                progress_bar.progress((i + 1) / len(st.session_state.qa_dataset))

                # Simulate quality assessment
                if not qa.get("quality_score"):
                    # Simple quality scoring based on content length and completeness
                    score = 5.0  # Base score

                    # Query quality
                    if len(qa.get("query", "")) > 20:
                        score += 1.0
                    if len(qa.get("query", "")) > 50:
                        score += 0.5

                    # Expected behavior quality
                    if len(qa.get("expected_behavior", "")) > 30:
                        score += 1.0

                    # Additional content
                    if qa.get("expected_answer_snippet"):
                        score += 1.0
                    if qa.get("expected_citations"):
                        score += 0.5

                    qa["quality_score"] = min(10.0, score)
                    qa["quality_assessed_at"] = datetime.now().isoformat()
                    assessed_count += 1

            status_text.text("✅ Quality assessment complete!")
            st.success(f"✅ Assessed quality for {assessed_count} items!")
        else:
            st.warning("No QA dataset available for assessment")


def show_batch_format_conversion():
    """Show batch format conversion interface."""
    st.markdown("#### 🔄 Format Conversion")

    source_format = st.selectbox("Source format", ["JSON", "JSONL", "CSV"])
    target_format = st.selectbox("Target format", ["JSON", "JSONL", "CSV", "Excel"])

    st.info("🚧 Batch format conversion coming soon!")


def show_batch_metadata_extraction():
    """Show batch metadata extraction interface."""
    st.markdown("#### 🔍 Metadata Extraction")

    if (
        "document_collection" in st.session_state
        and st.session_state.document_collection
    ):
        st.markdown(
            f"**📄 {len(st.session_state.document_collection)} documents available for metadata extraction**"
        )

        if st.button("🚀 Extract Metadata"):
            st.info("🚧 Batch metadata extraction coming soon!")
    else:
        st.info("No documents available for metadata extraction")


def show_backup_creation():
    """Show backup creation interface."""
    st.markdown("#### 💾 Backup Creation")

    backup_items = st.multiselect(
        "Select items to backup",
        [
            "QA Datasets",
            "Evaluation Results",
            "Document Collections",
            "Configuration Settings",
            "Custom Benchmarks",
        ],
        default=["QA Datasets", "Configuration Settings"],
    )

    if st.button("📦 Create Backup") and backup_items:
        backup_data = {}

        if "QA Datasets" in backup_items and "qa_dataset" in st.session_state:
            backup_data["qa_dataset"] = st.session_state.qa_dataset

        if (
            "Evaluation Results" in backup_items
            and "evaluation_results" in st.session_state
        ):
            backup_data["evaluation_results"] = st.session_state.evaluation_results

        if (
            "Document Collections" in backup_items
            and "document_collection" in st.session_state
        ):
            backup_data["document_collection"] = st.session_state.document_collection

        if "Configuration Settings" in backup_items:
            backup_data["configurations"] = {
                "model_config": st.session_state.get("model_config", {}),
                "retrieval_config": st.session_state.get("retrieval_config", {}),
                "evaluation_config": st.session_state.get("evaluation_config", {}),
            }

        if (
            "Custom Benchmarks" in backup_items
            and "custom_benchmarks" in st.session_state
        ):
            backup_data["custom_benchmarks"] = st.session_state.custom_benchmarks

        backup_data["backup_created_at"] = datetime.now().isoformat()
        backup_data["backup_version"] = "1.0"

        backup_json = json.dumps(backup_data, indent=2, ensure_ascii=False)

        st.download_button(
            "⬇️ Download Backup",
            backup_json,
            f"rag_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
        )

        st.success("✅ Backup created successfully!")


# Utility functions
def analyze_dataset(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze dataset and return summary statistics."""
    if not dataset:
        return {}

    total = len(dataset)

    # Calculate average query length
    query_lengths = [len(qa.get("query", "")) for qa in dataset]
    avg_query_length = sum(query_lengths) / len(query_lengths) if query_lengths else 0

    # Find most common intent
    intents = [qa.get("intent", "unknown") for qa in dataset]
    intent_counts = {}
    for intent in intents:
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    top_intent = (
        max(intent_counts.items(), key=lambda x: x[1])[0]
        if intent_counts
        else "unknown"
    )

    # Calculate average quality score
    quality_scores = [
        qa.get("quality_score") for qa in dataset if qa.get("quality_score") is not None
    ]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None

    return {
        "total": total,
        "avg_query_length": avg_query_length,
        "top_intent": top_intent,
        "avg_quality": avg_quality,
    }


def get_quality_distribution(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get quality score distribution."""
    quality_scores = [
        qa.get("quality_score") for qa in dataset if qa.get("quality_score") is not None
    ]

    if not quality_scores:
        return []

    ranges = [
        (0, 3, "Poor (0-3)"),
        (3, 5, "Fair (3-5)"),
        (5, 7, "Good (5-7)"),
        (7, 9, "Very Good (7-9)"),
        (9, 10, "Excellent (9-10)"),
    ]

    distribution = []
    for min_val, max_val, label in ranges:
        count = sum(1 for score in quality_scores if min_val <= score < max_val)
        if min_val == 9:  # Include 10 in the last range
            count = sum(1 for score in quality_scores if min_val <= score <= max_val)
        distribution.append({"Quality Range": label, "Count": count})

    return distribution


def validate_dataset(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate dataset and return results."""
    total_items = len(dataset)
    if total_items == 0:
        return {"total_items": 0, "valid_items": 0, "errors": [], "warnings": []}

    valid_items = 0
    errors = []
    warnings = []

    for i, qa in enumerate(dataset):
        item_valid = True

        # Check required fields
        if not qa.get("query", "").strip():
            errors.append(f"Item {i+1}: Missing or empty query")
            item_valid = False

        if not qa.get("expected_behavior", "").strip():
            errors.append(f"Item {i+1}: Missing or empty expected behavior")
            item_valid = False

        # Check data quality
        if len(qa.get("query", "")) < 10:
            warnings.append(f"Item {i+1}: Very short query (< 10 characters)")

        if len(qa.get("query", "")) > 500:
            warnings.append(f"Item {i+1}: Very long query (> 500 characters)")

        if item_valid:
            valid_items += 1

    return {
        "total_items": total_items,
        "valid_items": valid_items,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:10],  # Show first 10 errors
        "warnings": warnings[:10],  # Show first 10 warnings
    }


def show_validation_summary(validation_results: Dict[str, Any]):
    """Display validation results summary."""
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Items", validation_results["total_items"])
    with col2:
        st.metric("Valid Items", validation_results["valid_items"])
    with col3:
        validity_rate = (
            validation_results["valid_items"] / validation_results["total_items"]
            if validation_results["total_items"] > 0
            else 0
        )
        st.metric("Validity Rate", f"{validity_rate:.1%}")

    if validation_results["errors"]:
        st.markdown("**🚫 Errors:**")
        for error in validation_results["errors"]:
            st.error(error)

    if validation_results["warnings"]:
        st.markdown("**⚠️ Warnings:**")
        for warning in validation_results["warnings"]:
            st.warning(warning)

    if not validation_results["errors"] and not validation_results["warnings"]:
        st.success("✅ Dataset validation passed with no issues!")


def clean_dataset(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean dataset by removing duplicates and invalid entries."""
    cleaned = []
    seen_queries = set()

    for qa in dataset:
        query = qa.get("query", "").strip()
        expected_behavior = qa.get("expected_behavior", "").strip()

        # Skip if missing required fields or duplicate
        if not query or not expected_behavior or query in seen_queries:
            continue

        cleaned.append(qa)
        seen_queries.add(query)

    return cleaned


def import_dataset(uploaded_file, format_type: str) -> List[Dict[str, Any]]:
    """Import dataset from uploaded file."""
    try:
        if format_type == "json":
            data = json.loads(uploaded_file.getvalue().decode("utf-8"))
            return data if isinstance(data, list) else [data]

        elif format_type == "jsonl":
            lines = uploaded_file.getvalue().decode("utf-8").strip().split("\n")
            return [json.loads(line) for line in lines if line.strip()]

        elif format_type in ["csv", "excel"]:
            df = (
                pd.read_csv(uploaded_file)
                if format_type == "csv"
                else pd.read_excel(uploaded_file)
            )
            return df.to_dict("records")

        else:
            raise ValueError(f"Unsupported format: {format_type}")

    except Exception as e:
        raise Exception(f"Failed to import {format_type} file: {str(e)}")


def generate_export(
    data: List[Dict[str, Any]],
    format_type: str,
    include_metadata: bool,
    include_quality: bool,
) -> bytes:
    """Generate export data in specified format."""
    # Filter data based on options
    export_data = data.copy()

    if not include_metadata:
        # Remove metadata fields
        for item in export_data:
            item.pop("created_at", None)
            item.pop("created_by", None)
            item.pop("updated_at", None)

    if not include_quality:
        # Remove quality fields
        for item in export_data:
            item.pop("quality_score", None)
            item.pop("validation_notes", None)
            item.pop("quality_assessed_at", None)

    if format_type == "json":
        return json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")

    elif format_type == "jsonl":
        lines = [json.dumps(item, ensure_ascii=False) for item in export_data]
        return "\n".join(lines).encode("utf-8")

    elif format_type == "csv":
        df = pd.DataFrame(export_data)
        return df.to_csv(index=False).encode("utf-8")

    elif format_type == "excel":
        df = pd.DataFrame(export_data)
        output = io.BytesIO()
        df.to_excel(output, index=False)
        return output.getvalue()

    elif format_type == "zip archive":
        # Create ZIP with multiple formats
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON
            json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
            zip_file.writestr("dataset.json", json_data)

            # Add CSV
            df = pd.DataFrame(export_data)
            csv_data = df.to_csv(index=False)
            zip_file.writestr("dataset.csv", csv_data)

            # Add README
            readme = f"""RAG Dataset Export
Created: {datetime.now().isoformat()}
Total items: {len(export_data)}
Formats included: JSON, CSV

File descriptions:
- dataset.json: Complete dataset in JSON format
- dataset.csv: Dataset in CSV format for spreadsheet applications
"""
            zip_file.writestr("README.txt", readme)

        return zip_buffer.getvalue()

    else:
        raise ValueError(f"Unsupported export format: {format_type}")


def generate_dataset_report(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate comprehensive dataset report."""
    analysis = analyze_dataset(dataset)
    validation = validate_dataset(dataset)
    quality_dist = get_quality_distribution(dataset)

    return {
        "analysis": analysis,
        "validation": validation,
        "quality_distribution": quality_dist,
        "generated_at": datetime.now().isoformat(),
    }


def show_dataset_report(report_data: Dict[str, Any]):
    """Display dataset report."""
    st.markdown("#### 📊 Dataset Report")

    # Analysis section
    analysis = report_data["analysis"]
    if analysis:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Items", analysis["total"])
        with col2:
            st.metric("Avg Query Length", f"{analysis['avg_query_length']:.0f} chars")
        with col3:
            st.metric("Top Intent", analysis["top_intent"])
        with col4:
            if analysis["avg_quality"]:
                st.metric("Avg Quality", f"{analysis['avg_quality']:.1f}/10")

    # Validation section
    validation = report_data["validation"]
    validity_rate = (
        validation["valid_items"] / validation["total_items"]
        if validation["total_items"] > 0
        else 0
    )

    if validity_rate == 1.0:
        st.success(
            f"✅ Dataset is 100% valid ({validation['valid_items']}/{validation['total_items']} items)"
        )
    else:
        st.warning(
            f"⚠️ Dataset validity: {validity_rate:.1%} ({validation['valid_items']}/{validation['total_items']} items)"
        )

        if validation["errors"]:
            st.error(f"🚫 {validation['error_count']} errors found")
        if validation["warnings"]:
            st.warning(f"⚠️ {validation['warning_count']} warnings found")

    # Quality distribution
    quality_dist = report_data["quality_distribution"]
    if quality_dist:
        st.markdown("**🏆 Quality Distribution**")
        df_quality = pd.DataFrame(quality_dist)
        st.bar_chart(df_quality.set_index("Quality Range")["Count"])
