"""
✏️ Enhanced Data Annotation Component

Advanced interface for creating and editing QA pairs with evaluation integration.
Supports relevance scoring, feedback management, and evaluation result annotations.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class AnnotationManager:
    """Manages annotation data with persistence and evaluation integration."""

    def __init__(self):
        """Initialize the annotation manager."""
        self.data_dir = project_root / "data" / "evaluation"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.annotations_file = self.data_dir / "annotations.json"
        self.qa_dataset_file = self.data_dir / "qa_dataset.jsonl"

    def load_annotations(self) -> Dict[str, Any]:
        """Load existing annotations from file."""
        if self.annotations_file.exists():
            with open(self.annotations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_annotations(self, annotations: Dict[str, Any]):
        """Save annotations to file."""
        with open(self.annotations_file, "w", encoding="utf-8") as f:
            json.dump(annotations, f, indent=2, ensure_ascii=False)

    def load_qa_dataset(self) -> List[Dict[str, Any]]:
        """Load QA dataset from JSONL file."""
        dataset = []
        if self.qa_dataset_file.exists():
            with open(self.qa_dataset_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        dataset.append(json.loads(line))
        return dataset

    def save_qa_dataset(self, dataset: List[Dict[str, Any]]):
        """Save QA dataset to JSONL file."""
        with open(self.qa_dataset_file, "w", encoding="utf-8") as f:
            for item in dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")


class EnhancedAnnotationInterface:
    """Enhanced annotation interface with evaluation integration."""

    def __init__(self):
        """Initialize the annotation interface."""
        self.manager = AnnotationManager()

    def show_main_interface(self):
        """Display the main annotation interface."""
        st.title("✏️ Enhanced Data Annotation Tool")

        st.markdown(
            """
        Create high-quality QA pairs and annotate evaluation results for continuous improvement.
        """
        )

        # Tabs for different annotation modes
        tabs = st.tabs(
            [
                "➕ Create QA Pair",
                "📝 Edit Dataset",
                "🎯 Annotate Results",
                "📊 Quality Analysis",
                "💾 Import/Export",
            ]
        )

        with tabs[0]:
            self._show_create_qa_interface()

        with tabs[1]:
            self._show_edit_dataset_interface()

        with tabs[2]:
            self._show_annotate_results_interface()

        with tabs[3]:
            self._show_quality_analysis()

        with tabs[4]:
            self._show_import_export_interface()

    def _show_create_qa_interface(self):
        """Interface for creating new QA pairs."""
        st.markdown("### ➕ Create New QA Pair")

        with st.form("create_qa_form", clear_on_submit=True):
            # Basic information
            st.markdown("#### 📋 Basic Information")

            col1, col2 = st.columns([2, 1])

            with col1:
                query = st.text_area(
                    "Question/Query *",
                    height=100,
                    help="The question users might ask",
                    placeholder="What is the purpose of vector embeddings in RAG?",
                )

                expected_behavior = st.text_area(
                    "Expected Behavior *",
                    height=80,
                    help="What the system should do",
                    placeholder="Provide clear definition and explain role in retrieval",
                )

                expected_answer_snippet = st.text_area(
                    "Expected Answer (Optional)",
                    height=120,
                    help="Sample answer or key points",
                    placeholder="Vector embeddings are dense numerical representations...",
                )

            with col2:
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
                )

                doc_category = st.selectbox(
                    "Document Category",
                    ["technical", "business", "legal", "medical", "general", "other"],
                )

                difficulty = st.selectbox(
                    "Difficulty Level", ["easy", "medium", "hard"]
                )

                priority = st.selectbox("Priority", ["high", "medium", "low"])

            # Advanced fields
            st.markdown("#### 🔬 Advanced Options")

            col1, col2 = st.columns(2)

            with col1:
                expected_citations = st.text_area(
                    "Expected Citations",
                    height=80,
                    help="List relevant documents (one per line)",
                    placeholder="rag_guide.pdf\nvector_database.md",
                )

                tags = st.text_input(
                    "Tags (comma-separated)", help="Add tags for organization"
                )

            with col2:
                doc_hints = st.text_area(
                    "Document Hints",
                    height=80,
                    help="Keywords to help retrieve docs",
                    placeholder="vector similarity\nsemantic search",
                )

                notes = st.text_area(
                    "Internal Notes", height=80, help="Notes for annotators"
                )

            # Quality criteria
            st.markdown("#### 🎯 Quality Criteria")

            col1, col2, col3 = st.columns(3)

            with col1:
                min_citations = st.number_input(
                    "Min Citations Required", min_value=0, max_value=10, value=1
                )

            with col2:
                max_response_time = st.number_input(
                    "Max Response Time (ms)", min_value=100, max_value=10000, value=3000
                )

            with col3:
                min_quality_score = st.slider("Min Quality Score", 0.0, 1.0, 0.7, 0.1)

            # Submit button
            submitted = st.form_submit_button("💾 Save QA Pair", type="primary")

        if submitted:
            if query.strip() and expected_behavior.strip():
                # Create QA pair
                qa_pair = {
                    "qa_id": str(uuid.uuid4()),
                    "query": query.strip(),
                    "intent": intent,
                    "expected_behavior": expected_behavior.strip(),
                    "expected_answer_snippet": expected_answer_snippet.strip()
                    if expected_answer_snippet
                    else None,
                    "doc_category": doc_category,
                    "difficulty": difficulty,
                    "priority": priority,
                    "expected_citations": [
                        c.strip() for c in expected_citations.split("\n") if c.strip()
                    ],
                    "doc_hints": [
                        h.strip() for h in doc_hints.split("\n") if h.strip()
                    ],
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "notes": notes.strip() if notes else None,
                    "quality_criteria": {
                        "min_citations": min_citations,
                        "max_response_time_ms": max_response_time,
                        "min_quality_score": min_quality_score,
                    },
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": "annotator",
                    "status": "pending",
                }

                # Save to dataset
                dataset = self.manager.load_qa_dataset()
                dataset.append(qa_pair)
                self.manager.save_qa_dataset(dataset)

                st.success(f"✅ QA pair saved! Dataset now has {len(dataset)} items.")
            else:
                st.error("❌ Please fill in required fields.")

    def _show_edit_dataset_interface(self):
        """Interface for editing existing QA dataset."""
        st.markdown("### 📝 Edit QA Dataset")

        dataset = self.manager.load_qa_dataset()

        if not dataset:
            st.info("No QA pairs in dataset. Create some first!")
            return

        # Dataset statistics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total QA Pairs", len(dataset))

        with col2:
            pending = sum(1 for qa in dataset if qa.get("status") == "pending")
            st.metric("Pending Review", pending)

        with col3:
            approved = sum(1 for qa in dataset if qa.get("status") == "approved")
            st.metric("Approved", approved)

        with col4:
            high_priority = sum(1 for qa in dataset if qa.get("priority") == "high")
            st.metric("High Priority", high_priority)

        # Filters
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            filter_intent = st.selectbox(
                "Filter by Intent",
                ["All"] + list(set(qa.get("intent", "unknown") for qa in dataset)),
            )

        with col2:
            filter_status = st.selectbox(
                "Filter by Status",
                ["All", "pending", "approved", "rejected", "needs_review"],
            )

        with col3:
            filter_priority = st.selectbox(
                "Filter by Priority", ["All", "high", "medium", "low"]
            )

        # Apply filters
        filtered_dataset = dataset

        if filter_intent != "All":
            filtered_dataset = [
                qa for qa in filtered_dataset if qa.get("intent") == filter_intent
            ]

        if filter_status != "All":
            filtered_dataset = [
                qa for qa in filtered_dataset if qa.get("status") == filter_status
            ]

        if filter_priority != "All":
            filtered_dataset = [
                qa for qa in filtered_dataset if qa.get("priority") == filter_priority
            ]

        st.markdown(f"**Showing {len(filtered_dataset)} of {len(dataset)} QA pairs**")

        # Display QA pairs
        for i, qa in enumerate(filtered_dataset[:20]):  # Show first 20
            with st.expander(f"📄 {qa.get('query', 'N/A')[:80]}..."):
                col1, col2 = st.columns([3, 1])

                with col1:
                    # Editable fields
                    new_query = st.text_area(
                        "Query", value=qa.get("query", ""), key=f"query_{i}"
                    )

                    new_behavior = st.text_area(
                        "Expected Behavior",
                        value=qa.get("expected_behavior", ""),
                        key=f"behavior_{i}",
                    )

                    new_answer = st.text_area(
                        "Expected Answer",
                        value=qa.get("expected_answer_snippet", "") or "",
                        key=f"answer_{i}",
                    )

                with col2:
                    new_status = st.selectbox(
                        "Status",
                        ["pending", "approved", "rejected", "needs_review"],
                        index=["pending", "approved", "rejected", "needs_review"].index(
                            qa.get("status", "pending")
                        ),
                        key=f"status_{i}",
                    )

                    new_priority = st.selectbox(
                        "Priority",
                        ["high", "medium", "low"],
                        index=["high", "medium", "low"].index(
                            qa.get("priority", "medium")
                        ),
                        key=f"priority_{i}",
                    )

                    quality_score = st.slider(
                        "Quality Score",
                        0.0,
                        1.0,
                        value=qa.get("quality_score", 0.5),
                        key=f"quality_{i}",
                    )

                    # Actions
                    col_a, col_b = st.columns(2)

                    with col_a:
                        if st.button("💾 Update", key=f"update_{i}"):
                            # Update QA pair
                            qa["query"] = new_query
                            qa["expected_behavior"] = new_behavior
                            qa["expected_answer_snippet"] = (
                                new_answer if new_answer else None
                            )
                            qa["status"] = new_status
                            qa["priority"] = new_priority
                            qa["quality_score"] = quality_score
                            qa["updated_at"] = datetime.now(timezone.utc).isoformat()

                            self.manager.save_qa_dataset(dataset)
                            st.success("✅ Updated!")
                            st.rerun()

                    with col_b:
                        if st.button("🗑️ Delete", key=f"delete_{i}"):
                            dataset.remove(qa)
                            self.manager.save_qa_dataset(dataset)
                            st.success("🗑️ Deleted!")
                            st.rerun()

    def _show_annotate_results_interface(self):
        """Interface for annotating evaluation results."""
        st.markdown("### 🎯 Annotate Evaluation Results")

        # Load evaluation results
        results_dir = project_root / "results" / "evaluation"
        result_files = list(results_dir.glob("*.json")) + list(
            results_dir.glob("*.jsonl")
        )

        if not result_files:
            st.info("No evaluation results found. Run evaluation first!")
            return

        # Select result file
        selected_file = st.selectbox(
            "Select evaluation result:", result_files, format_func=lambda x: x.name
        )

        if selected_file:
            # Load results
            if selected_file.suffix == ".json":
                with open(selected_file, "r", encoding="utf-8") as f:
                    eval_data = json.load(f)
            else:
                results = []
                with open(selected_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            results.append(json.loads(line))
                eval_data = {"results": results}

            results = eval_data.get("results", [])

            if not results:
                st.info("No results in file.")
                return

            # Load existing annotations
            annotations = self.manager.load_annotations()

            # Annotation interface
            st.markdown("---")
            st.markdown("#### 📝 Annotate Individual Results")

            # Filters
            col1, col2, col3 = st.columns(3)

            with col1:
                filter_unannotated = st.checkbox("Show only unannotated", value=True)

            with col2:
                filter_errors = st.checkbox("Show only errors", value=False)

            with col3:
                filter_low_quality = st.checkbox("Show low quality only", value=False)

            # Apply filters
            filtered_results = results

            if filter_unannotated:
                filtered_results = [
                    r for r in filtered_results if r.get("qa_id") not in annotations
                ]

            if filter_errors:
                filtered_results = [
                    r for r in filtered_results if r.get("error") is not None
                ]

            if filter_low_quality:
                filtered_results = [
                    r
                    for r in filtered_results
                    if r.get("e2e_metrics", {}).get("answer_quality", 0) < 0.5
                ]

            st.markdown(f"**Showing {len(filtered_results)} results to annotate**")

            # Annotation form
            for i, result in enumerate(filtered_results[:10]):  # Show first 10
                qa_id = result.get("qa_id", f"unknown_{i}")

                with st.expander(f"📄 {result.get('query', 'N/A')[:80]}..."):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown(f"**Query:** {result.get('query', 'N/A')}")
                        st.markdown(f"**Intent:** {result.get('intent', 'N/A')}")

                        if result.get("generated_answer"):
                            st.markdown("**Generated Answer:**")
                            st.write(result["generated_answer"])

                        if result.get("citations"):
                            st.markdown("**Citations:**")
                            for citation in result["citations"]:
                                st.write(f"- {citation}")

                    with col2:
                        # Annotation fields
                        st.markdown("**📝 Annotation**")

                        relevance = st.select_slider(
                            "Answer Relevance",
                            options=["Very Poor", "Poor", "Fair", "Good", "Excellent"],
                            value="Fair",
                            key=f"relevance_{qa_id}",
                        )

                        accuracy = st.select_slider(
                            "Answer Accuracy",
                            options=[
                                "Incorrect",
                                "Partially Correct",
                                "Mostly Correct",
                                "Correct",
                            ],
                            value="Mostly Correct",
                            key=f"accuracy_{qa_id}",
                        )

                        completeness = st.select_slider(
                            "Answer Completeness",
                            options=["Incomplete", "Partial", "Adequate", "Complete"],
                            value="Adequate",
                            key=f"completeness_{qa_id}",
                        )

                        citations_quality = st.select_slider(
                            "Citations Quality",
                            options=["Poor", "Fair", "Good", "Excellent"],
                            value="Good",
                            key=f"citations_{qa_id}",
                        )

                        feedback = st.text_area(
                            "Feedback/Notes", height=80, key=f"feedback_{qa_id}"
                        )

                        flags = st.multiselect(
                            "Flags",
                            [
                                "needs_improvement",
                                "wrong_intent",
                                "missing_citations",
                                "hallucination",
                                "timeout",
                                "off_topic",
                            ],
                            key=f"flags_{qa_id}",
                        )

                        if st.button("💾 Save Annotation", key=f"save_{qa_id}"):
                            # Save annotation
                            annotations[qa_id] = {
                                "qa_id": qa_id,
                                "relevance": relevance,
                                "accuracy": accuracy,
                                "completeness": completeness,
                                "citations_quality": citations_quality,
                                "feedback": feedback,
                                "flags": flags,
                                "annotated_at": datetime.now(timezone.utc).isoformat(),
                                "annotator": "user",
                            }

                            self.manager.save_annotations(annotations)
                            st.success("✅ Annotation saved!")

    def _show_quality_analysis(self):
        """Show quality analysis of annotations."""
        st.markdown("### 📊 Quality Analysis")

        # Load data
        dataset = self.manager.load_qa_dataset()
        annotations = self.manager.load_annotations()

        if not dataset and not annotations:
            st.info("No data available for analysis.")
            return

        # Dataset quality metrics
        if dataset:
            st.markdown("#### 📋 Dataset Quality")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total QA Pairs", len(dataset))

            with col2:
                approved = sum(1 for qa in dataset if qa.get("status") == "approved")
                approval_rate = approved / len(dataset) if dataset else 0
                st.metric("Approval Rate", f"{approval_rate:.1%}")

            with col3:
                avg_quality = sum(qa.get("quality_score", 0.5) for qa in dataset) / len(
                    dataset
                )
                st.metric("Avg Quality Score", f"{avg_quality:.2f}")

            with col4:
                with_answers = sum(
                    1 for qa in dataset if qa.get("expected_answer_snippet")
                )
                st.metric("With Expected Answers", f"{with_answers}/{len(dataset)}")

            # Intent distribution
            st.markdown("---")
            intent_counts = {}
            for qa in dataset:
                intent = qa.get("intent", "unknown")
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            intent_df = pd.DataFrame(
                list(intent_counts.items()), columns=["Intent", "Count"]
            )

            st.markdown("**Intent Distribution**")
            st.bar_chart(intent_df.set_index("Intent"))

        # Annotation quality metrics
        if annotations:
            st.markdown("---")
            st.markdown("#### 🎯 Annotation Quality")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Annotations", len(annotations))

            with col2:
                # Calculate average relevance
                relevance_map = {
                    "Very Poor": 0.2,
                    "Poor": 0.4,
                    "Fair": 0.6,
                    "Good": 0.8,
                    "Excellent": 1.0,
                }
                avg_relevance = sum(
                    relevance_map.get(ann.get("relevance", "Fair"), 0.6)
                    for ann in annotations.values()
                ) / len(annotations)
                st.metric("Avg Relevance", f"{avg_relevance:.2f}")

            with col3:
                # Count flags
                total_flags = sum(
                    len(ann.get("flags", [])) for ann in annotations.values()
                )
                st.metric("Total Flags", total_flags)

            # Flag distribution
            flag_counts = {}
            for ann in annotations.values():
                for flag in ann.get("flags", []):
                    flag_counts[flag] = flag_counts.get(flag, 0) + 1

            if flag_counts:
                st.markdown("**Common Issues (Flags)**")
                flag_df = pd.DataFrame(
                    list(flag_counts.items()), columns=["Flag", "Count"]
                )
                st.bar_chart(flag_df.set_index("Flag"))

    def _show_import_export_interface(self):
        """Interface for importing and exporting data."""
        st.markdown("### 💾 Import/Export Data")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📤 Export")

            # Export QA dataset
            dataset = self.manager.load_qa_dataset()
            if dataset:
                if st.button("📄 Export QA Dataset"):
                    jsonl_data = "\n".join(
                        [json.dumps(qa, ensure_ascii=False) for qa in dataset]
                    )
                    st.download_button(
                        label="⬇️ Download QA Dataset (JSONL)",
                        data=jsonl_data,
                        file_name=f"qa_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
                        mime="application/jsonl",
                    )

            # Export annotations
            annotations = self.manager.load_annotations()
            if annotations:
                if st.button("📝 Export Annotations"):
                    json_data = json.dumps(annotations, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="⬇️ Download Annotations (JSON)",
                        data=json_data,
                        file_name=f"annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                    )

            # Export combined report
            if dataset and annotations:
                if st.button("📊 Export Quality Report"):
                    report = self._generate_quality_report(dataset, annotations)
                    st.download_button(
                        label="⬇️ Download Report (Markdown)",
                        data=report,
                        file_name=f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown",
                    )

        with col2:
            st.markdown("#### 📥 Import")

            uploaded_file = st.file_uploader(
                "Upload data file",
                type=["json", "jsonl", "csv"],
                help="Upload QA dataset or annotations",
            )

            if uploaded_file:
                try:
                    if uploaded_file.name.endswith(".jsonl"):
                        # Import QA dataset
                        lines = uploaded_file.read().decode("utf-8").strip().split("\n")
                        imported_data = [json.loads(line) for line in lines if line]

                        if st.button("💾 Import as QA Dataset"):
                            dataset = self.manager.load_qa_dataset()
                            dataset.extend(imported_data)
                            self.manager.save_qa_dataset(dataset)
                            st.success(f"✅ Imported {len(imported_data)} QA pairs!")
                            st.rerun()

                    elif uploaded_file.name.endswith(".json"):
                        # Import annotations
                        imported_data = json.loads(uploaded_file.read())

                        if st.button("💾 Import as Annotations"):
                            annotations = self.manager.load_annotations()
                            annotations.update(imported_data)
                            self.manager.save_annotations(annotations)
                            st.success(f"✅ Imported {len(imported_data)} annotations!")
                            st.rerun()

                    # Preview imported data
                    st.markdown("**Preview:**")
                    if isinstance(imported_data, list):
                        st.json(imported_data[:3])  # Show first 3 items
                    else:
                        st.json(
                            dict(list(imported_data.items())[:3])
                        )  # Show first 3 items

                except Exception as e:
                    st.error(f"Error importing file: {e}")

    def _generate_quality_report(self, dataset: List[Dict], annotations: Dict) -> str:
        """Generate quality report."""
        report = f"""# QA Dataset Quality Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Dataset Statistics

- **Total QA Pairs**: {len(dataset)}
- **Approved**: {sum(1 for qa in dataset if qa.get('status') == 'approved')}
- **Pending Review**: {sum(1 for qa in dataset if qa.get('status') == 'pending')}
- **High Priority**: {sum(1 for qa in dataset if qa.get('priority') == 'high')}

## Annotation Statistics

- **Total Annotations**: {len(annotations)}
- **Flagged for Issues**: {sum(1 for ann in annotations.values() if ann.get('flags'))}

## Quality Metrics

### Dataset Quality
- **Average Quality Score**: {sum(qa.get('quality_score', 0.5) for qa in dataset) / len(dataset):.2f}
- **With Expected Answers**: {sum(1 for qa in dataset if qa.get('expected_answer_snippet'))}

### Annotation Quality
- **Average Relevance**: {self._calculate_avg_relevance(annotations):.2f}
- **Common Issues**: {self._get_top_flags(annotations)}

## Recommendations

1. Review and approve pending QA pairs
2. Add expected answers for better evaluation
3. Address flagged issues in annotations
4. Expand dataset for underrepresented intents
"""
        return report

    def _calculate_avg_relevance(self, annotations: Dict) -> float:
        """Calculate average relevance score."""
        if not annotations:
            return 0.0

        relevance_map = {
            "Very Poor": 0.2,
            "Poor": 0.4,
            "Fair": 0.6,
            "Good": 0.8,
            "Excellent": 1.0,
        }

        total = sum(
            relevance_map.get(ann.get("relevance", "Fair"), 0.6)
            for ann in annotations.values()
        )

        return total / len(annotations)

    def _get_top_flags(self, annotations: Dict) -> str:
        """Get top flags from annotations."""
        flag_counts = {}
        for ann in annotations.values():
            for flag in ann.get("flags", []):
                flag_counts[flag] = flag_counts.get(flag, 0) + 1

        if not flag_counts:
            return "None"

        sorted_flags = sorted(flag_counts.items(), key=lambda x: x[1], reverse=True)
        return ", ".join([f"{flag} ({count})" for flag, count in sorted_flags[:3]])


def show_annotation_page():
    """Main entry point for annotation interface."""
    interface = EnhancedAnnotationInterface()
    interface.show_main_interface()
