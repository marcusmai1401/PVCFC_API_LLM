"""
Document Classification Module
Provides 12-type document classification functionality
"""

from app.classification.document_type_12 import (
    PARENT_CATEGORIES,
    TECHNICAL_DATA_SUB_CATEGORIES,
    DocumentType12,
    DocumentType12Result,
    get_doc_type_display_name,
    get_parent_category,
    is_technical_data_sub_category,
    map_llm_label_to_code,
)

__all__ = [
    "DocumentType12",
    "DocumentType12Result",
    "PARENT_CATEGORIES",
    "TECHNICAL_DATA_SUB_CATEGORIES",
    "map_llm_label_to_code",
    "get_doc_type_display_name",
    "get_parent_category",
    "is_technical_data_sub_category",
]
