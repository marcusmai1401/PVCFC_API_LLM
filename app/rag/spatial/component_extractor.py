"""
Spatial Component Extractor
Extract individual tag components (unit/prefix/suffix) from PDF page layout
"""
import re
from typing import List

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayout
from app.rag.spatial.schemas import Component


class SpatialComponentExtractor:
    """Extract tag components with spatial information from PDF pages"""

    def __init__(self):
        # Component patterns
        self.unit_pattern = re.compile(r"^\d{1,2}$")
        self.prefix_pattern = re.compile(
            r"^[A-Z]{1,6}$"
        )  # Changed: 1-6 letters (was 2-6)
        self.suffix_pattern = re.compile(r"^\d{3,5}[A-Z]?$")

        # Common Vietnamese words to exclude
        self.vietnamese_words = {
            "TRONG",
            "NGOAI",
            "GIUA",
            "TREN",
            "DUOI",
            "BEN",
            "CANH",
            "PHIA",
            "DAU",
            "CUOI",
            "TAH",
            "TAL",
            "TAHH",
            "TAHL",  # Common P&ID labels
        }

    def extract_components(self, page_layout: PageLayout) -> List[Component]:
        """
        Extract all valid tag components from a page

        Args:
            page_layout: PageLayout with spans from PDF

        Returns:
            List of Component objects with bbox and type classification
        """
        components = []

        for span in page_layout.spans:
            text = span.text.strip()

            if not text:
                continue

            # Classify component type
            comp_type = self._classify_component(text)

            if comp_type:
                component = Component(
                    text=text,
                    component_type=comp_type,
                    bbox=span.bbox,
                    page=page_layout.page,
                    doc_id=page_layout.doc_id,
                    span_id=span.span_id,
                )
                components.append(component)

        logger.info(
            f"Extracted {len(components)} components from page {page_layout.page}: "
            f"units={sum(1 for c in components if c.component_type == 'unit')}, "
            f"prefixes={sum(1 for c in components if c.component_type == 'prefix')}, "
            f"suffixes={sum(1 for c in components if c.component_type == 'suffix')}"
        )

        return components

    def _classify_component(self, text: str) -> str:
        """
        Classify text as unit, prefix, or suffix

        Returns:
            "unit", "prefix", "suffix", or None
        """
        text_upper = text.upper()

        # Check unit (1-2 digits)
        if self.unit_pattern.match(text):
            return "unit"

        # Check prefix (2-6 letters, not Vietnamese words)
        if self.prefix_pattern.match(text_upper):
            if text_upper not in self.vietnamese_words:
                return "prefix"

        # Check suffix (3-5 digits, optional letter)
        if self.suffix_pattern.match(text):
            return "suffix"

        return None

    def is_unit(self, text: str) -> bool:
        """Check if text is a valid unit number"""
        return bool(self.unit_pattern.match(text))

    def is_prefix(self, text: str) -> bool:
        """Check if text is a valid prefix"""
        text_upper = text.upper()
        return (
            bool(self.prefix_pattern.match(text_upper))
            and text_upper not in self.vietnamese_words
        )

    def is_suffix(self, text: str) -> bool:
        """Check if text is a valid suffix"""
        return bool(self.suffix_pattern.match(text))

    def get_components_by_type(
        self, components: List[Component], comp_type: str
    ) -> List[Component]:
        """Filter components by type"""
        return [c for c in components if c.component_type == comp_type]
