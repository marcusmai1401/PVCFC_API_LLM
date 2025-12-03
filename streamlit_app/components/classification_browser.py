"""
Document Classification Browser - 4-Category Taxonomy
======================================================

Tree-view UI for browsing documents classified into 4 main categories:
- ENGINEERING_DESIGN: P&ID, Drawing, Technical Data
- VENDOR_EQUIPMENT: Datasheet, Material Partlist, Vendor Manual
- OPERATIONS_MAINTENANCE: Operation Instruction, Maintenance Instruction, etc.
- SAFETY_MANAGEMENT: MOC, RCA, Pictures
- UNCATEGORIZED: Documents pending review

Requirements: 9.1, 9.2, 9.3, 9.5
"""
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.classification.taxonomy import (
    ClassificationStatus,
    DocumentCategory,
    DocumentTaxonomy,
    get_doc_type_display_name,
    get_taxonomy,
)


# Category icons for visual distinction
CATEGORY_ICONS = {
    "ENGINEERING_DESIGN": "🔧",
    "VENDOR_EQUIPMENT": "📦",
    "OPERATIONS_MAINTENANCE": "⚙️",
    "SAFETY_MANAGEMENT": "🛡️",
    "UNCATEGORIZED": "❓",
}

# Status badges
STATUS_BADGES = {
    "classified": ("✅", "#34c759", "Classified"),
    "needs_review": ("⚠️", "#ff9500", "Needs Review"),
    "pending": ("⏳", "#8e8e93", "Pending"),
}


class DocumentExplorer:
    """
    Tree-view browser for documents classified into 4-category taxonomy
    
    Features:
    - Hierarchical tree: Category → Doc Type → Files
    - Classification status badges
    - Document preview on click
    - Re-classification trigger button
    """

    def __init__(self, api_base_url: str = "http://localhost:8000/api"):
        """
        Initialize Document Explorer
        
        Args:
            api_base_url: Base URL for classification API
        """
        self.api_base_url = api_base_url
        self.taxonomy = get_taxonomy()
        self._documents_cache = None
        self._taxonomy_cache = None

    def fetch_taxonomy(self) -> Optional[Dict]:
        """Fetch taxonomy from API"""
        if self._taxonomy_cache is not None:
            return self._taxonomy_cache
        
        try:
            response = requests.get(
                f"{self.api_base_url}/classification/taxonomy",
                timeout=10
            )
            if response.status_code == 200:
                self._taxonomy_cache = response.json()
                return self._taxonomy_cache
        except requests.RequestException as e:
            st.warning(f"Could not fetch taxonomy from API: {e}")
        
        # Fallback to local taxonomy
        return self.taxonomy.to_dict()

    def fetch_documents_by_category(
        self,
        category: Optional[str] = None,
        doc_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch documents grouped by category from API
        
        Args:
            category: Optional category filter
            doc_type: Optional doc_type filter
            status: Optional status filter
            
        Returns:
            List of category groups with documents
        """
        try:
            params = {}
            if category:
                params["category"] = category
            if doc_type:
                params["doc_type"] = doc_type
            if status:
                params["status"] = status
            
            response = requests.get(
                f"{self.api_base_url}/classification/documents/by-category",
                params=params,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            st.warning(f"Could not fetch documents from API: {e}")
        
        return []

    def trigger_classification(self, doc_id: str, pdf_path: str) -> Optional[Dict]:
        """
        Trigger re-classification for a document
        
        Args:
            doc_id: Document ID
            pdf_path: Path to PDF file
            
        Returns:
            Classification result or None
        """
        try:
            response = requests.post(
                f"{self.api_base_url}/classification/classify",
                json={
                    "doc_id": doc_id,
                    "pdf_path": pdf_path,
                    "force_reclassify": True
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Classification failed: {response.text}")
        except requests.RequestException as e:
            st.error(f"Classification request failed: {e}")
        
        return None

    def get_mock_documents(self) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Get mock documents for demo when API is not available
        
        Returns:
            Nested dict: category -> doc_type -> list of documents
        """
        # Demo data structure
        return {
            "ENGINEERING_DESIGN": {
                "P&ID": [
                    {
                        "doc_id": "pid_001",
                        "filename": "K06101_PID_Sheet1.pdf",
                        "category": "ENGINEERING_DESIGN",
                        "doc_type": "P&ID",
                        "classification_status": "classified",
                        "classification_confidence": 0.95,
                        "pdf_path": "D:/Data_Raw/K06101/PID/K06101_PID_Sheet1.pdf"
                    },
                    {
                        "doc_id": "pid_002",
                        "filename": "K06101_PID_Sheet2.pdf",
                        "category": "ENGINEERING_DESIGN",
                        "doc_type": "P&ID",
                        "classification_status": "classified",
                        "classification_confidence": 0.92,
                        "pdf_path": "D:/Data_Raw/K06101/PID/K06101_PID_Sheet2.pdf"
                    },
                ],
                "Drawing": [
                    {
                        "doc_id": "drw_001",
                        "filename": "K06101_GA_Drawing.pdf",
                        "category": "ENGINEERING_DESIGN",
                        "doc_type": "Drawing",
                        "classification_status": "classified",
                        "classification_confidence": 0.88,
                        "pdf_path": "D:/Data_Raw/K06101/Drawings/K06101_GA_Drawing.pdf"
                    },
                ],
                "Technical Data": [],
            },
            "VENDOR_EQUIPMENT": {
                "Datasheet": [
                    {
                        "doc_id": "ds_001",
                        "filename": "Hitachi_Compressor_Datasheet.pdf",
                        "category": "VENDOR_EQUIPMENT",
                        "doc_type": "Datasheet",
                        "classification_status": "classified",
                        "classification_confidence": 0.91,
                        "pdf_path": "D:/Data_Raw/K06101/Vendor/Hitachi_Compressor_Datasheet.pdf"
                    },
                ],
                "Material Partlist": [],
                "Vendor Manual": [
                    {
                        "doc_id": "vm_001",
                        "filename": "Hitachi_Operation_Manual.pdf",
                        "category": "VENDOR_EQUIPMENT",
                        "doc_type": "Vendor Manual",
                        "classification_status": "needs_review",
                        "classification_confidence": 0.45,
                        "pdf_path": "D:/Data_Raw/K06101/Vendor/Hitachi_Operation_Manual.pdf"
                    },
                ],
            },
            "OPERATIONS_MAINTENANCE": {
                "Operation Instruction": [
                    {
                        "doc_id": "op_001",
                        "filename": "K06101_SOP_Startup.pdf",
                        "category": "OPERATIONS_MAINTENANCE",
                        "doc_type": "Operation Instruction",
                        "classification_status": "classified",
                        "classification_confidence": 0.87,
                        "pdf_path": "D:/Data_Raw/K06101/Operations/K06101_SOP_Startup.pdf"
                    },
                ],
                "Maintenance Instruction": [],
                "Maintenance History": [],
                "Inventory": [],
            },
            "SAFETY_MANAGEMENT": {
                "MOC": [],
                "RCA": [],
                "Pictures": [],
            },
            "UNCATEGORIZED": {
                "Unknown": [
                    {
                        "doc_id": "unk_001",
                        "filename": "Misc_Document.pdf",
                        "category": "UNCATEGORIZED",
                        "doc_type": "Unknown",
                        "classification_status": "pending",
                        "classification_confidence": 0.0,
                        "pdf_path": "D:/Data_Raw/K06101/Misc/Misc_Document.pdf"
                    },
                ],
            },
        }

    def render_status_badge(self, status: str) -> str:
        """
        Render HTML for status badge
        
        Args:
            status: Classification status
            
        Returns:
            HTML string for badge
        """
        icon, color, label = STATUS_BADGES.get(
            status, ("❓", "#8e8e93", "Unknown")
        )
        return f'<span style="background: {color}20; color: {color}; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 500;">{icon} {label}</span>'

    def render_confidence_bar(self, confidence: float) -> str:
        """
        Render HTML for confidence bar
        
        Args:
            confidence: Confidence score 0.0-1.0
            
        Returns:
            HTML string for confidence bar
        """
        percentage = int(confidence * 100)
        color = "#34c759" if confidence >= 0.7 else "#ff9500" if confidence >= 0.5 else "#ff3b30"
        
        return f'''
        <div style="display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; height: 4px; background: #e5e5ea; border-radius: 2px; overflow: hidden;">
                <div style="width: {percentage}%; height: 100%; background: {color};"></div>
            </div>
            <span style="font-size: 12px; color: #86868b; min-width: 36px;">{percentage}%</span>
        </div>
        '''

    def render_category_header(self, category: str, doc_count: int) -> None:
        """
        Render category header with icon and count
        
        Args:
            category: Category name
            doc_count: Total documents in category
        """
        icon = CATEGORY_ICONS.get(category, "📁")
        display_name = self.taxonomy.get_display_name(category)
        
        st.markdown(
            f'''
            <div style="display: flex; align-items: center; gap: 12px; padding: 12px 0;">
                <span style="font-size: 24px;">{icon}</span>
                <div style="flex: 1;">
                    <h3 style="margin: 0; font-size: 18px; font-weight: 600;">{display_name}</h3>
                    <p style="margin: 0; font-size: 13px; color: #86868b;">{doc_count} documents</p>
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )

    def render_doc_type_section(
        self,
        category: str,
        doc_type: str,
        documents: List[Dict]
    ) -> None:
        """
        Render doc_type section with expandable document list
        
        Args:
            category: Parent category
            doc_type: Document type
            documents: List of documents
        """
        doc_type_display = get_doc_type_display_name(doc_type)
        doc_count = len(documents)
        
        # Create unique key for expander
        expander_key = f"{category}_{doc_type}".replace(" ", "_").replace("&", "and")
        
        with st.expander(f"📄 {doc_type_display} ({doc_count})", expanded=False):
            if not documents:
                st.info("No documents in this category")
                return
            
            for doc in documents:
                self.render_document_row(doc)

    def render_document_row(self, doc: Dict) -> None:
        """
        Render single document row with metadata and actions
        
        Args:
            doc: Document metadata dict
        """
        doc_id = doc.get("doc_id", "unknown")
        filename = doc.get("filename", "Unknown file")
        status = doc.get("classification_status", "pending")
        confidence = doc.get("classification_confidence", 0.0)
        pdf_path = doc.get("pdf_path", "")
        
        # Create unique key for this document
        row_key = f"doc_{doc_id}"
        
        # Document row container
        st.markdown(
            f'''
            <div style="padding: 12px; margin: 8px 0; background: #f5f5f7; border-radius: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div style="flex: 1;">
                        <p style="margin: 0 0 4px 0; font-weight: 600; font-size: 14px;">{filename}</p>
                        {self.render_status_badge(status)}
                    </div>
                </div>
                <div style="margin-top: 8px;">
                    <p style="margin: 0 0 4px 0; font-size: 12px; color: #86868b;">Confidence</p>
                    {self.render_confidence_bar(confidence)}
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        
        # Action buttons
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("👁️ View", key=f"view_{row_key}", use_container_width=True):
                st.session_state["selected_document"] = doc
                st.session_state["show_document_preview"] = True
        
        with col2:
            if st.button("🔄 Re-classify", key=f"reclassify_{row_key}", use_container_width=True):
                with st.spinner("Classifying..."):
                    result = self.trigger_classification(doc_id, pdf_path)
                    if result:
                        st.success(f"Classified as: {result.get('category')} / {result.get('doc_type')}")
                        st.rerun()

    def render_document_preview(self) -> None:
        """
        Render document preview panel with metadata and PDF viewer
        
        Requirements: 9.4, 9.6
        """
        if not st.session_state.get("show_document_preview"):
            return
        
        doc = st.session_state.get("selected_document")
        if not doc:
            return
        
        st.markdown("---")
        
        # Preview header
        st.markdown(
            '''
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        border-radius: 16px 16px 0 0; padding: 20px; color: white;">
                <h3 style="margin: 0; font-size: 20px; font-weight: 600;">📄 Document Preview</h3>
            </div>
            ''',
            unsafe_allow_html=True
        )
        
        # Preview container
        with st.container():
            # Close button row
            col_close, col_spacer = st.columns([1, 4])
            with col_close:
                if st.button("✕ Close Preview", key="close_preview", use_container_width=True):
                    st.session_state["show_document_preview"] = False
                    st.session_state["selected_document"] = None
                    st.rerun()
            
            st.markdown("")
            
            # Document metadata in two columns
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### 📋 Document Information")
                
                st.markdown("**Filename:**")
                st.write(doc.get("filename", "Unknown"))
                
                st.markdown("**Category:**")
                category = doc.get("category", "UNCATEGORIZED")
                icon = CATEGORY_ICONS.get(category, "📁")
                st.write(f"{icon} {self.taxonomy.get_display_name(category)}")
                
                st.markdown("**Document Type:**")
                st.write(get_doc_type_display_name(doc.get("doc_type", "Unknown")))
            
            with col2:
                st.markdown("##### 📊 Classification Details")
                
                st.markdown("**Status:**")
                status = doc.get("classification_status", "pending")
                st.markdown(self.render_status_badge(status), unsafe_allow_html=True)
                
                st.markdown("**Confidence:**")
                confidence = doc.get("classification_confidence", 0.0)
                st.markdown(self.render_confidence_bar(confidence), unsafe_allow_html=True)
                
                st.markdown("**Classification Method:**")
                method = doc.get("classification_method", "unknown")
                method_display = {
                    "cadlike_gate": "🔧 CADLike Gate (P&ID Detection)",
                    "ai_classifier": "🤖 AI Classifier (Gemini)",
                    "manual": "👤 Manual Classification",
                    "unknown": "❓ Unknown"
                }
                st.write(method_display.get(method, method))
            
            # File path
            st.markdown("**File Path:**")
            st.code(doc.get("pdf_path", "N/A"), language=None)
            
            st.markdown("---")
            
            # Action buttons
            st.markdown("##### 🎯 Actions")
            col_view, col_reclassify, col_download = st.columns(3)
            
            with col_view:
                pdf_path = doc.get("pdf_path", "")
                if st.button("👁️ Open PDF Viewer", key="preview_open_pdf", use_container_width=True):
                    if pdf_path and Path(pdf_path).exists():
                        # Import and use PDF modal
                        from streamlit_app.components.pdf_viewer_modal import open_pdf_modal
                        open_pdf_modal(
                            pdf_path=pdf_path,
                            page=1,
                            title=doc.get("filename", "Document")
                        )
                        st.rerun()
                    else:
                        st.warning("PDF file not found")
            
            with col_reclassify:
                if st.button("🔄 Re-classify", key="preview_reclassify", use_container_width=True):
                    with st.spinner("Running classification pipeline..."):
                        result = self.trigger_classification(
                            doc.get("doc_id", ""),
                            doc.get("pdf_path", "")
                        )
                        if result:
                            st.success(
                                f"✅ Classified as: {result.get('category')} / {result.get('doc_type')} "
                                f"(confidence: {result.get('confidence', 0):.2%})"
                            )
                            # Update the document in session state
                            st.session_state["selected_document"].update({
                                "category": result.get("category"),
                                "doc_type": result.get("doc_type"),
                                "classification_status": result.get("status"),
                                "classification_confidence": result.get("confidence"),
                                "classification_method": result.get("method")
                            })
                            st.rerun()
            
            with col_download:
                pdf_path = doc.get("pdf_path", "")
                if pdf_path and Path(pdf_path).exists():
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="📥 Download",
                            data=f.read(),
                            file_name=doc.get("filename", "document.pdf"),
                            mime="application/pdf",
                            key="preview_download",
                            use_container_width=True
                        )
                else:
                    st.button("📥 Download", key="preview_download_disabled", disabled=True, use_container_width=True)
            
            # Show needs_review warning if applicable
            if status == "needs_review":
                st.warning(
                    "⚠️ This document requires manual review. "
                    "The AI classifier had low confidence or could not determine the document type. "
                    "Please review and re-classify if needed."
                )

    def render_tree_view(self, documents_by_category: Dict[str, Dict[str, List[Dict]]]) -> None:
        """
        Render hierarchical tree view of documents
        
        Structure:
        - Category (expandable)
          - Doc Type (expandable)
            - Document files
        
        Args:
            documents_by_category: Nested dict of documents
        """
        # Calculate totals for each category
        for category in self.taxonomy.get_all_categories():
            if category not in documents_by_category:
                continue
            
            doc_types = documents_by_category[category]
            total_docs = sum(len(docs) for docs in doc_types.values())
            
            # Skip empty categories (optional - can show all)
            # if total_docs == 0:
            #     continue
            
            # Category header
            self.render_category_header(category, total_docs)
            
            # Doc types under this category
            for doc_type in self.taxonomy.get_doc_types_for_category(category):
                documents = doc_types.get(doc_type, [])
                self.render_doc_type_section(category, doc_type, documents)
            
            st.markdown("---")

    def render_filter_sidebar(self) -> Dict:
        """
        Render filter controls in sidebar
        
        Returns:
            Dict with filter values
        """
        st.sidebar.markdown("### 🔍 Filters")
        
        # Category filter
        categories = ["All"] + self.taxonomy.get_all_categories()
        selected_category = st.sidebar.selectbox(
            "Category",
            categories,
            key="filter_category"
        )
        
        # Doc type filter (depends on category)
        if selected_category and selected_category != "All":
            doc_types = ["All"] + self.taxonomy.get_doc_types_for_category(selected_category)
        else:
            doc_types = ["All"] + self.taxonomy.get_all_doc_types()
        
        selected_doc_type = st.sidebar.selectbox(
            "Document Type",
            doc_types,
            key="filter_doc_type"
        )
        
        # Status filter
        statuses = ["All", "classified", "needs_review", "pending"]
        selected_status = st.sidebar.selectbox(
            "Status",
            statuses,
            key="filter_status"
        )
        
        return {
            "category": None if selected_category == "All" else selected_category,
            "doc_type": None if selected_doc_type == "All" else selected_doc_type,
            "status": None if selected_status == "All" else selected_status,
        }

    def render_stats_summary(self, documents_by_category: Dict[str, Dict[str, List[Dict]]]) -> None:
        """
        Render statistics summary cards
        
        Args:
            documents_by_category: Nested dict of documents
        """
        # Calculate stats
        total_docs = 0
        classified_count = 0
        needs_review_count = 0
        pending_count = 0
        
        for category, doc_types in documents_by_category.items():
            for doc_type, docs in doc_types.items():
                total_docs += len(docs)
                for doc in docs:
                    status = doc.get("classification_status", "pending")
                    if status == "classified":
                        classified_count += 1
                    elif status == "needs_review":
                        needs_review_count += 1
                    else:
                        pending_count += 1
        
        # Render stats cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📚 Total Documents", total_docs)
        
        with col2:
            st.metric("✅ Classified", classified_count)
        
        with col3:
            st.metric("⚠️ Needs Review", needs_review_count)
        
        with col4:
            st.metric("⏳ Pending", pending_count)

    def render(self) -> None:
        """Main render function for Document Explorer"""
        # Page header
        st.markdown(
            """
            <div style="margin-bottom: 32px;">
                <h1 style="font-size: 34px; font-weight: 700; margin: 0;">📂 Document Explorer</h1>
                <p style="color: #86868b; margin: 8px 0 0 0;">
                    Browse documents by category using the 4-category taxonomy
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Filters in sidebar
        filters = self.render_filter_sidebar()
        
        # Try to fetch from API, fallback to mock data
        api_data = self.fetch_documents_by_category(
            category=filters.get("category"),
            doc_type=filters.get("doc_type"),
            status=filters.get("status")
        )
        
        if api_data:
            # Convert API response to nested dict format
            documents_by_category = {}
            for cat_data in api_data:
                category = cat_data.get("category")
                doc_types = cat_data.get("doc_types", {})
                documents_by_category[category] = doc_types
        else:
            # Use mock data for demo
            st.info("📡 API not available. Showing demo data.")
            documents_by_category = self.get_mock_documents()
            
            # Apply filters to mock data
            if filters.get("category"):
                documents_by_category = {
                    k: v for k, v in documents_by_category.items()
                    if k == filters["category"]
                }
            
            if filters.get("status"):
                for category in documents_by_category:
                    for doc_type in documents_by_category[category]:
                        documents_by_category[category][doc_type] = [
                            doc for doc in documents_by_category[category][doc_type]
                            if doc.get("classification_status") == filters["status"]
                        ]
        
        # Stats summary
        self.render_stats_summary(documents_by_category)
        
        st.markdown("---")
        
        # Tree view
        self.render_tree_view(documents_by_category)
        
        # Document preview panel
        self.render_document_preview()


def render():
    """Main render function for classification browser component"""
    explorer = DocumentExplorer()
    explorer.render()
