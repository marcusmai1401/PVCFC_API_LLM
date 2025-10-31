"""
Query Expansion Helper - Improve retrieval accuracy
Expands queries with synonyms and related terms to match document content better
"""
import re
from typing import List

from loguru import logger


class QueryExpander:
    """Expand queries to improve retrieval coverage"""

    def __init__(self):
        # Equipment type synonyms
        self.equipment_synonyms = {
            "gear": ["gear unit", "gearbox", "reducer", "transmission"],
            "compressor": ["compression", "compressing"],
            "turbine": ["steam turbine", "gas turbine"],
            "pump": ["pumping"],
            "valve": ["valves"],
        }

        # Technical term synonyms (EN <-> VI)
        self.technical_terms = {
            # Vietnamese -> English
            "áp suất": ["pressure"],
            "nhiệt độ": ["temperature"],
            "tốc độ": ["speed", "rpm"],
            "hiệu suất": ["performance", "efficiency"],
            "biểu đồ": ["curve", "chart", "diagram"],
            "máy nén": ["compressor"],
            "vận hành": ["operation", "operating"],
            "bình thường": ["normal"],
            "cảnh báo": ["alarm"],
            "dừng máy": ["trip", "shutdown"],
            # English -> Vietnamese
            "alarm": ["cảnh báo"],
            "trip": ["dừng máy", "shutdown"],
            "normal": ["bình thường"],
            "setpoint": ["giá trị đặt", "thiết lập"],
        }

        # Document type keywords
        self.doc_type_keywords = {
            "manual": ["operation", "maintenance", "O&M", "operating manual"],
            "datasheet": ["data sheet", "specification", "spec"],
            "drawing": ["P&ID", "diagram", "schematic"],
            "curve": ["performance curve", "characteristic"],
            "list": ["instrument list", "equipment list", "parts list"],
        }

    def expand_query(self, query: str, detected_tags: List[str] = None) -> str:
        """
        Expand query with synonyms and related terms

        Args:
            query: Original user query
            detected_tags: Optional list of equipment tags

        Returns:
            Expanded query string
        """
        expanded_terms = [query]  # Always keep original

        query_lower = query.lower()

        # 1. Add equipment synonyms
        for base_term, synonyms in self.equipment_synonyms.items():
            if base_term in query_lower:
                expanded_terms.extend(synonyms)

        # 2. Add technical term translations
        for term, translations in self.technical_terms.items():
            if term in query_lower:
                expanded_terms.extend(translations)

        # 3. Add document type keywords if query mentions doc type
        for doc_type, keywords in self.doc_type_keywords.items():
            if doc_type in query_lower:
                expanded_terms.extend(keywords)

        # 4. Extract equipment model numbers (e.g., HCD025, KT06101)
        model_patterns = re.findall(r"\b[A-Z]{2,}[\d]{3,}\b", query)
        if model_patterns:
            expanded_terms.extend(model_patterns)
            logger.info(f"Extracted equipment models: {model_patterns}")

        # 5. Add detected tags if provided
        if detected_tags:
            expanded_terms.extend(detected_tags)

        # Remove duplicates and join
        unique_terms = list(dict.fromkeys(expanded_terms))
        expanded_query = " ".join(unique_terms)

        logger.info(f"Query expansion: {len(unique_terms)} terms (from {len([query])})")
        return expanded_query
