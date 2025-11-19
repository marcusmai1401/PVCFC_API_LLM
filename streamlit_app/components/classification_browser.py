"""
Document Classification Browser
================================

Device-centric UI for browsing documents classified into 12 types.
Allows users to select equipment and view documents by category.
"""
import json

# Import classification utilities
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.classification.document_type_12 import (
    PARENT_CATEGORIES,
    TECHNICAL_DATA_SUB_CATEGORIES,
    get_doc_type_display_name,
    get_parent_category,
)


class ClassificationBrowser:
    """Browser for classified documents by equipment and category"""

    def __init__(
        self,
        classification_manifest_path: Path = None,
        equipment_metadata_dir: Path = None,
    ):
        """
        Initialize classification browser

        Args:
            classification_manifest_path: Path to document_types_12.jsonl
            equipment_metadata_dir: Path to equipment metadata directory
        """
        if classification_manifest_path is None:
            classification_manifest_path = Path(
                "artifacts/classification/document_types_12.jsonl"
            )

        if equipment_metadata_dir is None:
            equipment_metadata_dir = Path("artifacts/equipment")

        self.classification_manifest_path = classification_manifest_path
        self.equipment_metadata_dir = equipment_metadata_dir

        self._classifications = None
        self._equipment_metadata = {}

    def load_classifications(self) -> List[Dict]:
        """Load classification results from JSONL manifest"""
        if self._classifications is not None:
            return self._classifications

        classifications = []

        if not self.classification_manifest_path.exists():
            st.error(
                f"Classification manifest not found: {self.classification_manifest_path}"
            )
            return []

        with open(self.classification_manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    classifications.append(json.loads(line))

        self._classifications = classifications
        return classifications

    def load_equipment_metadata(self, equipment_id: str) -> Optional[Dict]:
        """Load metadata for a specific equipment"""
        if equipment_id in self._equipment_metadata:
            return self._equipment_metadata[equipment_id]

        metadata_file = self.equipment_metadata_dir / f"{equipment_id}.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        self._equipment_metadata[equipment_id] = metadata
        return metadata

    def get_available_equipment(self) -> List[str]:
        """Get list of equipment IDs with documents"""
        classifications = self.load_classifications()

        # Extract unique equipment IDs from pdf paths
        equipment_ids = set()

        for doc in classifications:
            pdf_path = doc.get("pdf_path", "")

            # Try to extract equipment ID from path
            # Format: D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\...
            # or: D:\Data_Raw\KT06101_TURBINE_HTC\...
            if "K06101" in pdf_path:
                equipment_ids.add("K06101")
            elif "KT06101" in pdf_path:
                equipment_ids.add("KT06101")

        return sorted(list(equipment_ids))

    def get_documents_by_equipment(self, equipment_id: str) -> List[Dict]:
        """Get all documents for a specific equipment"""
        classifications = self.load_classifications()

        equipment_docs = []
        for doc in classifications:
            pdf_path = doc.get("pdf_path", "")
            if equipment_id in pdf_path:
                equipment_docs.append(doc)

        return equipment_docs

    def get_documents_by_category(
        self, equipment_id: str, doc_type_code: str
    ) -> List[Dict]:
        """Get documents for a specific equipment and category"""
        equipment_docs = self.get_documents_by_equipment(equipment_id)

        category_docs = [
            doc for doc in equipment_docs if doc.get("doc_type_12") == doc_type_code
        ]

        return category_docs

    def get_documents_by_parent_category(
        self, equipment_id: str, parent_category: str
    ) -> List[Dict]:
        """Get documents for a specific equipment and parent category"""
        equipment_docs = self.get_documents_by_equipment(equipment_id)

        parent_docs = [
            doc
            for doc in equipment_docs
            if doc.get("parent_category") == parent_category
        ]

        return parent_docs

    def get_documents_by_sub_category(
        self, equipment_id: str, sub_category: str
    ) -> List[Dict]:
        """Get documents for a specific equipment and sub-category"""
        equipment_docs = self.get_documents_by_equipment(equipment_id)

        sub_docs = [
            doc for doc in equipment_docs if doc.get("sub_category") == sub_category
        ]

        return sub_docs

    def get_category_counts(self, equipment_id: str) -> Dict[str, int]:
        """Get document counts per category for an equipment"""
        equipment_docs = self.get_documents_by_equipment(equipment_id)

        counts = Counter(doc.get("doc_type_12") for doc in equipment_docs)

        return dict(counts)

    def get_hierarchical_counts(self, equipment_id: str) -> Dict:
        """Get hierarchical document counts (parent + sub breakdown)"""
        equipment_docs = self.get_documents_by_equipment(equipment_id)

        # Count by parent category
        parent_counts = Counter(doc.get("parent_category") for doc in equipment_docs)

        # For TECHNICAL_DATA, breakdown by sub-category
        technical_data_breakdown = {}
        for doc in equipment_docs:
            if doc.get("parent_category") == "TECHNICAL_DATA":
                sub = doc.get("sub_category")
                if sub:
                    technical_data_breakdown[sub] = (
                        technical_data_breakdown.get(sub, 0) + 1
                    )
                else:
                    # Generic technical data (no sub-category)
                    technical_data_breakdown["TECHNICAL_DATA"] = (
                        technical_data_breakdown.get("TECHNICAL_DATA", 0) + 1
                    )

        return {
            "parent_counts": dict(parent_counts),
            "technical_data_breakdown": technical_data_breakdown,
        }

    def render_device_selector(self) -> Optional[str]:
        """
        Render device selector dropdown

        Returns:
            Selected equipment ID or None
        """
        equipment_ids = self.get_available_equipment()

        if not equipment_ids:
            st.warning("No equipment found in classification data")
            return None

        # Create display names
        display_options = []
        for eq_id in equipment_ids:
            metadata = self.load_equipment_metadata(eq_id)
            if metadata:
                display_name = f"{eq_id} - {metadata.get('name', 'Unknown')}"
            else:
                display_name = eq_id
            display_options.append(display_name)

        # Selector
        st.markdown(
            '<p class="ios-caption" style="margin-bottom: 8px; text-transform: uppercase; font-weight: 600;">Select Equipment</p>',
            unsafe_allow_html=True,
        )

        selected_display = st.selectbox(
            "Equipment",
            display_options,
            key="equipment_selector",
            label_visibility="collapsed",
        )

        # Extract equipment ID from display name
        selected_id = selected_display.split(" - ")[0] if selected_display else None

        return selected_id

    def render_device_metadata(self, equipment_id: str):
        """Render device metadata panel"""
        metadata = self.load_equipment_metadata(equipment_id)

        if not metadata:
            st.info(f"No metadata available for {equipment_id}")
            return

        # Get document counts
        category_counts = self.get_category_counts(equipment_id)
        total_docs = sum(category_counts.values())

        # iOS-style metadata card
        st.markdown(
            f"""
        <div class="ios-card" style="margin: 24px 0;">
            <div style="display: flex; align-items: start; gap: 16px;">
                <div style="flex-shrink: 0; width: 56px; height: 56px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 24px;">🏭</span>
                </div>
                <div style="flex: 1;">
                    <h2 class="ios-title" style="margin: 0 0 4px 0;">{metadata.get('name', 'Unknown')}</h2>
                    <p class="ios-caption" style="margin: 0; color: #86868b;">{equipment_id} · {metadata.get('vendor', 'Unknown Vendor')}</p>
                </div>
            </div>

            <hr style="margin: 16px 0;">

            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
                <div>
                    <p class="ios-caption" style="margin: 0 0 4px 0; color: #86868b;">Type</p>
                    <p class="ios-body" style="margin: 0; font-weight: 500;">{metadata.get('equipment_type', 'N/A').title()}</p>
                </div>
                <div>
                    <p class="ios-caption" style="margin: 0 0 4px 0; color: #86868b;">Status</p>
                    <p class="ios-body" style="margin: 0; font-weight: 500;">{metadata.get('status', 'N/A').title()}</p>
                </div>
                <div>
                    <p class="ios-caption" style="margin: 0 0 4px 0; color: #86868b;">Location</p>
                    <p class="ios-body" style="margin: 0; font-weight: 500;">{metadata.get('location', 'N/A')}</p>
                </div>
                <div>
                    <p class="ios-caption" style="margin: 0 0 4px 0; color: #86868b;">Documents</p>
                    <p class="ios-body" style="margin: 0; font-weight: 500;">{total_docs} files</p>
                </div>
            </div>

            {f'<p class="ios-body" style="margin: 16px 0 0 0; color: #86868b;">{metadata.get("description", "")}</p>' if metadata.get("description") else ""}
        </div>
        """,
            unsafe_allow_html=True,
        )

    def render_category_folders(self, equipment_id: str):
        """Render hierarchical category folders with document counts"""
        hierarchical_counts = self.get_hierarchical_counts(equipment_id)
        parent_counts = hierarchical_counts["parent_counts"]
        technical_data_breakdown = hierarchical_counts["technical_data_breakdown"]

        if not parent_counts:
            st.info("No documents found for this equipment")
            return

        st.markdown(
            '<h3 class="ios-title" style="margin: 32px 0 16px 0;">Document Categories</h3>',
            unsafe_allow_html=True,
        )

        # Render non-Technical Data parent categories first
        non_tech_parents = ["P_ID", "MANAGEMENT_OF_CHANGE", "ROOT_CAUSE_ANALYSIS"]
        for parent_code in non_tech_parents:
            if parent_code not in parent_counts:
                continue

            parent_count = parent_counts[parent_code]
            parent_display = get_doc_type_display_name(parent_code)

            with st.expander(f"📁 {parent_display} ({parent_count})", expanded=False):
                self.render_document_list_by_parent(equipment_id, parent_code)

        # Render Technical Data as section header + sub-categories
        if "TECHNICAL_DATA" in parent_counts and technical_data_breakdown:
            parent_count = parent_counts["TECHNICAL_DATA"]
            st.markdown(
                f'<h4 class="ios-title" style="margin: 24px 0 12px 0; color: #007aff;">📁 Technical Data ({parent_count})</h4>',
                unsafe_allow_html=True,
            )

            # Render each sub-category as separate expander
            for sub_code, sub_count in sorted(
                technical_data_breakdown.items(), key=lambda x: x[1], reverse=True
            ):
                sub_display = get_doc_type_display_name(sub_code)

                with st.expander(f"   📄 {sub_display} ({sub_count})", expanded=False):
                    if sub_code == "TECHNICAL_DATA":
                        # Generic technical data (no sub-category)
                        self.render_document_list_by_parent_no_sub(
                            equipment_id, "TECHNICAL_DATA"
                        )
                    else:
                        # Specific sub-category
                        self.render_document_list_by_sub(equipment_id, sub_code)

    def render_document_list(self, equipment_id: str, doc_type_code: str):
        """Render list of documents for a category"""
        docs = self.get_documents_by_category(equipment_id, doc_type_code)

        if not docs:
            st.info("No documents in this category")
            return

        self._render_doc_rows(docs)

    def render_document_list_by_parent(self, equipment_id: str, parent_category: str):
        """Render list of documents for a parent category"""
        docs = self.get_documents_by_parent_category(equipment_id, parent_category)

        if not docs:
            st.info("No documents in this category")
            return

        self._render_doc_rows(docs)

    def render_document_list_by_sub(self, equipment_id: str, sub_category: str):
        """Render list of documents for a sub-category"""
        docs = self.get_documents_by_sub_category(equipment_id, sub_category)

        if not docs:
            st.info("No documents in this sub-category")
            return

        self._render_doc_rows(docs)

    def render_document_list_by_parent_no_sub(
        self, equipment_id: str, parent_category: str
    ):
        """Render documents that have parent category but no sub-category"""
        equipment_docs = self.get_documents_by_equipment(equipment_id)

        docs = [
            doc
            for doc in equipment_docs
            if doc.get("parent_category") == parent_category
            and not doc.get("sub_category")
        ]

        if not docs:
            st.info("No documents in this category")
            return

        self._render_doc_rows(docs)

    def _render_doc_rows(self, docs: List[Dict]):
        """Helper to render document rows"""
        for i, doc in enumerate(docs):
            filename = Path(doc.get("pdf_path", "")).name

            # iOS-style document row (filename + View button only)
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(
                    f'<p class="ios-body" style="margin: 0; font-weight: 500;">{filename}</p>',
                    unsafe_allow_html=True,
                )

            with col2:
                # View button (placeholder - actual PDF viewing would need backend support)
                if st.button(
                    "View", key=f"view_{doc.get('doc_id')}", use_container_width=True
                ):
                    st.info(f"PDF viewer for {filename} (feature to be implemented)")

            if i < len(docs) - 1:
                st.markdown('<hr style="margin: 8px 0;">', unsafe_allow_html=True)


def render():
    """Main render function for classification browser"""
    st.markdown(
        """
    <div style="margin-bottom: 32px;">
        <h1 class="ios-title-large">Document Classification</h1>
        <p class="ios-body" style="color: #86868b;">
            Browse technical documents by equipment and category
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Initialize browser
    browser = ClassificationBrowser()

    # Device selector
    selected_equipment = browser.render_device_selector()

    if not selected_equipment:
        st.info("👆 Select an equipment to view its documents")
        return

    # Device metadata
    browser.render_device_metadata(selected_equipment)

    # Category folders
    browser.render_category_folders(selected_equipment)
