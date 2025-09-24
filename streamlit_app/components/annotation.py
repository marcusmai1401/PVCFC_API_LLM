"""
✏️ Data Annotation Component

Interface for creating and editing QA pairs for evaluation datasets.
Supports batch annotation, quality validation, and dataset management.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


def show_annotation_page():
    """Display the data annotation interface."""
    st.title("✏️ Data Annotation - QA Dataset Builder")

    st.markdown(
        """
    Create high-quality QA pairs for evaluating your RAG pipeline. Build comprehensive datasets with proper validation and metadata.
    """
    )

    # Tabs for different annotation modes
    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Create New QA", "📝 Edit Existing", "📊 Dataset Overview", "💾 Import/Export"]
    )

    with tab1:
        show_create_qa_interface()

    with tab2:
        show_edit_qa_interface()

    with tab3:
        show_dataset_overview()

    with tab4:
        show_import_export_interface()


def show_create_qa_interface():
    """Interface for creating new QA pairs."""
    st.markdown("### ➕ Create New QA Pair")

    # Initialize session state for current QA
    if "current_qa" not in st.session_state:
        st.session_state.current_qa = get_empty_qa_template()

    # QA Form
    with st.form("create_qa_form", clear_on_submit=False):
        col1, col2 = st.columns([2, 1])

        with col1:
            # Basic information
            st.markdown("#### 📋 Basic Information")

            query = st.text_area(
                "Question/Query *",
                value=st.session_state.current_qa.get("query", ""),
                height=100,
                help="The question that users might ask your RAG system",
                placeholder="What is the purpose of vector embeddings in RAG systems?",
            )

            intent = st.selectbox(
                "Query Intent *",
                [
                    "definition",
                    "explanation",
                    "comparison",
                    "how-to",
                    "troubleshooting",
                    "factual",
                    "opinion",
                    "other",
                ],
                index=[
                    "definition",
                    "explanation",
                    "comparison",
                    "how-to",
                    "troubleshooting",
                    "factual",
                    "opinion",
                    "other",
                ].index(st.session_state.current_qa.get("intent", "definition")),
                help="The primary intent behind this query",
            )

            expected_behavior = st.text_area(
                "Expected Behavior *",
                value=st.session_state.current_qa.get("expected_behavior", ""),
                height=80,
                help="Describe what the ideal system response should accomplish",
                placeholder="Should provide a clear definition of vector embeddings and explain their role in document retrieval",
            )

            # Optional answer snippet
            expected_answer_snippet = st.text_area(
                "Expected Answer Snippet (Optional)",
                value=st.session_state.current_qa.get("expected_answer_snippet", ""),
                height=120,
                help="A sample answer or key points that should be included",
                placeholder="Vector embeddings are dense numerical representations that capture semantic meaning...",
            )

        with col2:
            # Metadata and categorization
            st.markdown("#### 🏷️ Categorization")

            doc_category = st.selectbox(
                "Document Category",
                ["technical", "business", "legal", "medical", "general", "other"],
                index=[
                    "technical",
                    "business",
                    "legal",
                    "medical",
                    "general",
                    "other",
                ].index(st.session_state.current_qa.get("doc_category", "technical")),
            )

            difficulty = st.selectbox(
                "Difficulty Level",
                ["easy", "medium", "hard"],
                index=["easy", "medium", "hard"].index(
                    st.session_state.current_qa.get("difficulty", "medium")
                ),
            )

            language = st.selectbox(
                "Language",
                ["en", "vi", "fr", "es", "de", "other"],
                index=["en", "vi", "fr", "es", "de", "other"].index(
                    st.session_state.current_qa.get("language", "en")
                ),
            )

            # Tags
            tags_input = st.text_input(
                "Tags (comma-separated)",
                value=", ".join(st.session_state.current_qa.get("tags", [])),
                help="Add relevant tags for organization",
            )

            # Expected documents/citations
            st.markdown("#### 📚 Expected Sources")
            expected_citations = st.text_area(
                "Expected Citations (Optional)",
                value="\n".join(
                    st.session_state.current_qa.get("expected_citations", [])
                ),
                height=80,
                help="List relevant document names or sources (one per line)",
                placeholder="rag_guide.pdf\nvector_database_intro.md\nembeddings_comparison.docx",
            )

            doc_hints = st.text_area(
                "Document Hints (Optional)",
                value="\n".join(st.session_state.current_qa.get("doc_hints", [])),
                height=80,
                help="Keywords or phrases that might help retrieve relevant docs",
                placeholder="vector similarity\nsemantic search\ndocument retrieval",
            )

        # Form actions
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            submitted = st.form_submit_button("💾 Save QA Pair", type="primary")

        with col2:
            preview = st.form_submit_button("👀 Preview")

        with col3:
            validate = st.form_submit_button("✅ Validate")

        with col4:
            clear = st.form_submit_button("🧹 Clear Form")

    # Handle form actions
    if submitted:
        if query.strip() and intent and expected_behavior.strip():
            qa_data = {
                "id": str(uuid.uuid4()),
                "query": query.strip(),
                "intent": intent,
                "expected_behavior": expected_behavior.strip(),
                "expected_answer_snippet": expected_answer_snippet.strip()
                if expected_answer_snippet.strip()
                else None,
                "doc_category": doc_category,
                "difficulty": difficulty,
                "language": language,
                "tags": [tag.strip() for tag in tags_input.split(",") if tag.strip()],
                "expected_citations": [
                    cite.strip()
                    for cite in expected_citations.split("\n")
                    if cite.strip()
                ],
                "doc_hints": [
                    hint.strip() for hint in doc_hints.split("\n") if hint.strip()
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "annotator",
                "quality_score": None,
                "validation_notes": "",
            }

            # Add to session state dataset
            if "qa_dataset" not in st.session_state:
                st.session_state.qa_dataset = []

            st.session_state.qa_dataset.append(qa_data)
            st.success(
                f"✅ QA pair saved! Dataset now has {len(st.session_state.qa_dataset)} items."
            )

            # Clear form
            st.session_state.current_qa = get_empty_qa_template()
            st.rerun()
        else:
            st.error("❌ Please fill in all required fields (marked with *).")

    if preview:
        show_qa_preview(
            {
                "query": query,
                "intent": intent,
                "expected_behavior": expected_behavior,
                "expected_answer_snippet": expected_answer_snippet,
                "doc_category": doc_category,
                "difficulty": difficulty,
                "language": language,
                "tags": [tag.strip() for tag in tags_input.split(",") if tag.strip()],
                "expected_citations": [
                    cite.strip()
                    for cite in expected_citations.split("\n")
                    if cite.strip()
                ],
                "doc_hints": [
                    hint.strip() for hint in doc_hints.split("\n") if hint.strip()
                ],
            }
        )

    if validate:
        validation_results = validate_qa_pair(
            {
                "query": query,
                "intent": intent,
                "expected_behavior": expected_behavior,
                "expected_answer_snippet": expected_answer_snippet,
            }
        )
        show_validation_results(validation_results)

    if clear:
        st.session_state.current_qa = get_empty_qa_template()
        st.rerun()


def show_edit_qa_interface():
    """Interface for editing existing QA pairs."""
    st.markdown("### 📝 Edit Existing QA Pairs")

    if "qa_dataset" not in st.session_state or not st.session_state.qa_dataset:
        st.info(
            "📝 No QA pairs available for editing. Create some first in the 'Create New QA' tab."
        )
        return

    dataset = st.session_state.qa_dataset

    # Select QA to edit
    qa_options = [
        f"{i+1}. {qa['query'][:50]}..."
        if len(qa["query"]) > 50
        else f"{i+1}. {qa['query']}"
        for i, qa in enumerate(dataset)
    ]

    selected_idx = st.selectbox(
        "Select QA pair to edit:",
        range(len(qa_options)),
        format_func=lambda x: qa_options[x],
    )

    if selected_idx is not None:
        qa_to_edit = dataset[selected_idx].copy()

        # Edit form
        with st.form("edit_qa_form"):
            col1, col2 = st.columns([2, 1])

            with col1:
                # Editable fields
                new_query = st.text_area(
                    "Question/Query", value=qa_to_edit["query"], height=100
                )
                new_intent = st.selectbox(
                    "Intent",
                    [
                        "definition",
                        "explanation",
                        "comparison",
                        "how-to",
                        "troubleshooting",
                        "factual",
                        "opinion",
                        "other",
                    ],
                    index=[
                        "definition",
                        "explanation",
                        "comparison",
                        "how-to",
                        "troubleshooting",
                        "factual",
                        "opinion",
                        "other",
                    ].index(qa_to_edit["intent"]),
                )
                new_expected_behavior = st.text_area(
                    "Expected Behavior",
                    value=qa_to_edit["expected_behavior"],
                    height=80,
                )
                new_expected_answer_snippet = st.text_area(
                    "Expected Answer Snippet",
                    value=qa_to_edit.get("expected_answer_snippet", "") or "",
                    height=120,
                )

            with col2:
                new_doc_category = st.selectbox(
                    "Document Category",
                    ["technical", "business", "legal", "medical", "general", "other"],
                    index=[
                        "technical",
                        "business",
                        "legal",
                        "medical",
                        "general",
                        "other",
                    ].index(qa_to_edit.get("doc_category", "technical")),
                )
                new_difficulty = st.selectbox(
                    "Difficulty",
                    ["easy", "medium", "hard"],
                    index=["easy", "medium", "hard"].index(
                        qa_to_edit.get("difficulty", "medium")
                    ),
                )
                new_language = st.selectbox(
                    "Language",
                    ["en", "vi", "fr", "es", "de", "other"],
                    index=["en", "vi", "fr", "es", "de", "other"].index(
                        qa_to_edit.get("language", "en")
                    ),
                )

                new_tags = st.text_input(
                    "Tags", value=", ".join(qa_to_edit.get("tags", []))
                )
                new_expected_citations = st.text_area(
                    "Expected Citations",
                    value="\n".join(qa_to_edit.get("expected_citations", [])),
                    height=80,
                )
                new_doc_hints = st.text_area(
                    "Document Hints",
                    value="\n".join(qa_to_edit.get("doc_hints", [])),
                    height=80,
                )

            # Quality assessment
            st.markdown("#### 🏆 Quality Assessment")
            col1, col2 = st.columns(2)
            with col1:
                quality_score = st.slider(
                    "Quality Score",
                    1,
                    10,
                    value=qa_to_edit.get("quality_score", 5) or 5,
                )
            with col2:
                validation_notes = st.text_area(
                    "Validation Notes",
                    value=qa_to_edit.get("validation_notes", ""),
                    height=60,
                )

            # Form actions
            col1, col2, col3 = st.columns(3)
            with col1:
                update = st.form_submit_button("💾 Update QA Pair", type="primary")
            with col2:
                delete = st.form_submit_button("🗑️ Delete QA Pair", type="secondary")
            with col3:
                duplicate = st.form_submit_button("📋 Duplicate QA Pair")

        # Handle actions
        if update:
            # Update the QA pair
            updated_qa = qa_to_edit.copy()
            updated_qa.update(
                {
                    "query": new_query.strip(),
                    "intent": new_intent,
                    "expected_behavior": new_expected_behavior.strip(),
                    "expected_answer_snippet": new_expected_answer_snippet.strip()
                    if new_expected_answer_snippet.strip()
                    else None,
                    "doc_category": new_doc_category,
                    "difficulty": new_difficulty,
                    "language": new_language,
                    "tags": [tag.strip() for tag in new_tags.split(",") if tag.strip()],
                    "expected_citations": [
                        cite.strip()
                        for cite in new_expected_citations.split("\n")
                        if cite.strip()
                    ],
                    "doc_hints": [
                        hint.strip()
                        for hint in new_doc_hints.split("\n")
                        if hint.strip()
                    ],
                    "quality_score": quality_score,
                    "validation_notes": validation_notes,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            st.session_state.qa_dataset[selected_idx] = updated_qa
            st.success("✅ QA pair updated successfully!")
            st.rerun()

        if delete:
            if st.session_state.get("confirm_delete", False):
                del st.session_state.qa_dataset[selected_idx]
                st.session_state.confirm_delete = False
                st.success("🗑️ QA pair deleted successfully!")
                st.rerun()
            else:
                st.session_state.confirm_delete = True
                st.warning("⚠️ Click 'Delete QA Pair' again to confirm deletion.")

        if duplicate:
            duplicated_qa = qa_to_edit.copy()
            duplicated_qa["id"] = str(uuid.uuid4())
            duplicated_qa["query"] = f"[COPY] {duplicated_qa['query']}"
            duplicated_qa["created_at"] = datetime.now(timezone.utc).isoformat()

            st.session_state.qa_dataset.append(duplicated_qa)
            st.success("📋 QA pair duplicated successfully!")
            st.rerun()


def show_dataset_overview():
    """Display dataset statistics and overview."""
    st.markdown("### 📊 Dataset Overview")

    if "qa_dataset" not in st.session_state or not st.session_state.qa_dataset:
        st.info("📊 No QA pairs in dataset yet. Create some in the 'Create New QA' tab.")
        return

    dataset = st.session_state.qa_dataset
    df = pd.DataFrame(dataset)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total QA Pairs", len(dataset))

    with col2:
        intents = df["intent"].value_counts()
        st.metric(
            "Most Common Intent",
            intents.index[0] if not intents.empty else "N/A",
            delta=f"{intents.iloc[0]} items" if not intents.empty else "",
        )

    with col3:
        categories = df["doc_category"].value_counts()
        st.metric(
            "Most Common Category",
            categories.index[0] if not categories.empty else "N/A",
            delta=f"{categories.iloc[0]} items" if not categories.empty else "",
        )

    with col4:
        if "quality_score" in df.columns and df["quality_score"].notna().sum() > 0:
            avg_quality = df["quality_score"].dropna().mean()
            st.metric("Average Quality", f"{avg_quality:.1f}/10")
        else:
            st.metric("Average Quality", "Not rated")

    # Distribution charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📋 Intent Distribution")
        intent_counts = df["intent"].value_counts()
        st.bar_chart(intent_counts)

    with col2:
        st.markdown("#### 🏷️ Category Distribution")
        category_counts = df["doc_category"].value_counts()
        st.bar_chart(category_counts)

    # Data table
    st.markdown("#### 📝 All QA Pairs")

    # Display options
    col1, col2, col3 = st.columns(3)
    with col1:
        show_columns = st.multiselect(
            "Select columns to display:",
            [
                "query",
                "intent",
                "doc_category",
                "difficulty",
                "language",
                "tags",
                "quality_score",
            ],
            default=["query", "intent", "doc_category", "difficulty"],
        )

    with col2:
        filter_intent = st.selectbox(
            "Filter by Intent:", ["All"] + df["intent"].unique().tolist()
        )

    with col3:
        filter_category = st.selectbox(
            "Filter by Category:", ["All"] + df["doc_category"].unique().tolist()
        )

    # Apply filters
    filtered_df = df.copy()
    if filter_intent != "All":
        filtered_df = filtered_df[filtered_df["intent"] == filter_intent]
    if filter_category != "All":
        filtered_df = filtered_df[filtered_df["doc_category"] == filter_category]

    # Display filtered data
    if show_columns:
        display_df = filtered_df[show_columns].copy()

        # Truncate long text for display
        for col in display_df.columns:
            if display_df[col].dtype == "object":
                display_df[col] = (
                    display_df[col]
                    .astype(str)
                    .apply(lambda x: x[:100] + "..." if len(x) > 100 else x)
                )

        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Select columns to display the data table.")


def show_import_export_interface():
    """Interface for importing and exporting QA datasets."""
    st.markdown("### 💾 Import/Export Data")

    # Export section
    st.markdown("#### 📤 Export Dataset")

    if "qa_dataset" in st.session_state and st.session_state.qa_dataset:
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📄 Export as JSON"):
                json_data = json.dumps(
                    st.session_state.qa_dataset, indent=2, ensure_ascii=False
                )
                st.download_button(
                    label="⬇️ Download JSON",
                    data=json_data,
                    file_name=f"qa_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                )

        with col2:
            if st.button("📊 Export as CSV"):
                df = pd.DataFrame(st.session_state.qa_dataset)
                csv_data = df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv_data,
                    file_name=f"qa_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

        with col3:
            if st.button("📝 Export as JSONL"):
                jsonl_data = "\n".join(
                    [
                        json.dumps(qa, ensure_ascii=False)
                        for qa in st.session_state.qa_dataset
                    ]
                )
                st.download_button(
                    label="⬇️ Download JSONL",
                    data=jsonl_data,
                    file_name=f"qa_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
                    mime="application/jsonl",
                )
    else:
        st.info("No dataset to export. Create some QA pairs first.")

    st.markdown("---")

    # Import section
    st.markdown("#### 📥 Import Dataset")

    uploaded_file = st.file_uploader(
        "Upload QA dataset file",
        type=["json", "jsonl", "csv"],
        help="Upload a JSON, JSONL, or CSV file containing QA pairs",
    )

    if uploaded_file is not None:
        try:
            file_extension = uploaded_file.name.split(".")[-1].lower()

            if file_extension == "json":
                data = json.loads(uploaded_file.getvalue().decode("utf-8"))
                if isinstance(data, list):
                    imported_qa = data
                else:
                    st.error("JSON file should contain an array of QA objects.")
                    return

            elif file_extension == "jsonl":
                lines = uploaded_file.getvalue().decode("utf-8").strip().split("\n")
                imported_qa = [json.loads(line) for line in lines if line.strip()]

            elif file_extension == "csv":
                df = pd.read_csv(uploaded_file)
                imported_qa = df.to_dict("records")

            # Validate and add IDs if missing
            for qa in imported_qa:
                if "id" not in qa:
                    qa["id"] = str(uuid.uuid4())
                if "created_at" not in qa:
                    qa["created_at"] = datetime.now(timezone.utc).isoformat()

            # Merge or replace options
            col1, col2 = st.columns(2)

            with col1:
                if st.button("🔄 Replace Current Dataset"):
                    st.session_state.qa_dataset = imported_qa
                    st.success(f"✅ Replaced dataset with {len(imported_qa)} QA pairs!")
                st.rerun()

            with col2:
                if st.button("➕ Merge with Current Dataset"):
                    if "qa_dataset" not in st.session_state:
                        st.session_state.qa_dataset = []

                    original_count = len(st.session_state.qa_dataset)
                    st.session_state.qa_dataset.extend(imported_qa)
                    new_count = len(st.session_state.qa_dataset)

                    st.success(
                        f"✅ Added {len(imported_qa)} QA pairs! Dataset now has {new_count} total items."
                    )
                    st.rerun()

            # Preview imported data
            st.markdown("#### 👀 Preview Imported Data")
            preview_df = pd.DataFrame(imported_qa[:5])  # Show first 5 rows
            st.dataframe(preview_df)

        except Exception as e:
            st.error(f"❌ Error importing file: {str(e)}")


def get_empty_qa_template() -> Dict[str, Any]:
    """Get an empty QA template."""
    return {
        "query": "",
        "intent": "definition",
        "expected_behavior": "",
        "expected_answer_snippet": "",
        "doc_category": "technical",
        "difficulty": "medium",
        "language": "en",
        "tags": [],
        "expected_citations": [],
        "doc_hints": [],
    }


def show_qa_preview(qa_data: Dict[str, Any]):
    """Show a preview of the QA pair."""
    st.markdown("#### 👀 QA Preview")

    with st.expander("📋 Preview QA Pair", expanded=True):
        st.markdown(f"**Query:** {qa_data['query']}")
        st.markdown(f"**Intent:** {qa_data['intent']}")
        st.markdown(f"**Expected Behavior:** {qa_data['expected_behavior']}")

        if qa_data.get("expected_answer_snippet"):
            st.markdown(f"**Expected Answer:** {qa_data['expected_answer_snippet']}")

        st.markdown(
            f"**Category:** {qa_data['doc_category']} | **Difficulty:** {qa_data['difficulty']} | **Language:** {qa_data['language']}"
        )

        if qa_data.get("tags"):
            st.markdown(f"**Tags:** {', '.join(qa_data['tags'])}")

        if qa_data.get("expected_citations"):
            st.markdown(
                f"**Expected Citations:** {', '.join(qa_data['expected_citations'])}"
            )

        if qa_data.get("doc_hints"):
            st.markdown(f"**Document Hints:** {', '.join(qa_data['doc_hints'])}")


def validate_qa_pair(qa_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a QA pair and return validation results."""
    results = {"is_valid": True, "warnings": [], "errors": [], "suggestions": []}

    # Check required fields
    if not qa_data.get("query", "").strip():
        results["errors"].append("Query is required")
        results["is_valid"] = False

    if not qa_data.get("expected_behavior", "").strip():
        results["errors"].append("Expected behavior is required")
        results["is_valid"] = False

    # Check query length
    query_length = len(qa_data.get("query", ""))
    if query_length < 10:
        results["warnings"].append(
            "Query is quite short - consider adding more context"
        )
    elif query_length > 500:
        results["warnings"].append("Query is very long - consider breaking it down")

    # Check expected behavior length
    behavior_length = len(qa_data.get("expected_behavior", ""))
    if behavior_length < 20:
        results["warnings"].append("Expected behavior description is quite brief")

    # Suggestions
    if not qa_data.get("expected_answer_snippet"):
        results["suggestions"].append(
            "Consider adding an expected answer snippet for better evaluation"
        )

    if not qa_data.get("expected_citations"):
        results["suggestions"].append("Consider specifying expected source documents")

    return results


def show_validation_results(results: Dict[str, Any]):
    """Display validation results."""
    st.markdown("#### ✅ Validation Results")

    if results["is_valid"]:
        st.success("✅ QA pair is valid!")
    else:
        st.error("❌ QA pair has validation errors")

    if results["errors"]:
        st.markdown("**🚫 Errors:**")
        for error in results["errors"]:
            st.error(f"• {error}")

    if results["warnings"]:
        st.markdown("**⚠️ Warnings:**")
        for warning in results["warnings"]:
            st.warning(f"• {warning}")

    if results["suggestions"]:
        st.markdown("**💡 Suggestions:**")
        for suggestion in results["suggestions"]:
            st.info(f"• {suggestion}")
