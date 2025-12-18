"""
Hybrid Extraction Orchestrator.

This module coordinates the hybrid layout extraction pipeline, combining
LayoutDetector, HybridMapper, TableReconstructor, and MarkdownBuilder
to produce structured Markdown from PDF pages.

Requirements: 5.1, 5.2, 5.3
"""

from typing import List, Optional, Tuple

from loguru import logger

from app.ingestion.layout.detector import LayoutDetector
from app.ingestion.layout.hybrid_mapper import HybridMapper
from app.ingestion.layout.models import GCVWord, HybridExtractionResult, MappedRegion
from app.ingestion.markdown_builder import MarkdownBuilder
from app.ingestion.table_reconstructor import TableReconstructor


class HybridExtractionOrchestrator:
    """
    Orchestrates the hybrid layout extraction pipeline.

    This class coordinates:
    1. LayoutDetector - Surya layout detection
    2. HybridMapper - GCV word to region mapping
    3. TableReconstructor - Table reconstruction
    4. MarkdownBuilder - Markdown assembly

    Requirements: 5.1
    """

    def __init__(
        self,
        iou_threshold: float = 0.6,
        row_tolerance: float = 0.02,
        min_table_rows: int = 2,
    ):
        """
        Initialize the orchestrator.

        Args:
            iou_threshold: IoU threshold for word-to-region mapping (default 0.6)
            row_tolerance: Y-tolerance for table row grouping (default 0.02)
            min_table_rows: Minimum rows for table output (default 2)
        """
        self.layout_detector = LayoutDetector.get_instance()
        self.hybrid_mapper = HybridMapper(iou_threshold=iou_threshold)
        self.table_reconstructor = TableReconstructor(
            row_tolerance=row_tolerance, min_rows=min_table_rows
        )
        self.markdown_builder = MarkdownBuilder(
            table_reconstructor=self.table_reconstructor
        )

    def extract_hybrid_markdown(
        self,
        page_image: bytes,
        gcv_words: List[dict],
        page_num: int,
        page_width: int,
        page_height: int,
        fallback_text: str = "",
    ) -> HybridExtractionResult:
        """
        Extract structured Markdown from a page using hybrid layout extraction.

        Args:
            page_image: Page image as bytes (PNG format)
            gcv_words: List of word dicts from PDFProcessor.extract_gcv_words()
                      Each dict has 'text' and 'bbox' (x0, y0, x1, y1)
            page_num: Page number (1-based)
            page_width: Page width in pixels
            page_height: Page height in pixels
            fallback_text: Text to use if layout detection fails

        Returns:
            HybridExtractionResult with markdown and metadata

        Requirements: 5.1, 5.2
        """
        # Step 1: Layout Detection
        regions = self.layout_detector.detect_layout(page_image)

        # Check for fallback condition
        if not regions:
            logger.warning(
                f"Page {page_num}: Layout detection returned no regions, using fallback"
            )
            return HybridExtractionResult(
                page_num=page_num,
                regions=[],
                markdown=f"<!-- Page {page_num} -->\n{fallback_text}",
                heading_count=0,
                table_count=0,
                fallback_used=True,
            )

        # Step 2: Convert GCV word dicts to GCVWord objects
        gcv_word_objects = [GCVWord(text=w["text"], bbox=w["bbox"]) for w in gcv_words]

        # Step 3: Hybrid Mapping
        mapped_regions = self.hybrid_mapper.map_words_to_regions(
            words=gcv_word_objects,
            regions=regions,
            page_width=page_width,
            page_height=page_height,
        )

        # Step 4: Build Markdown
        markdown = self.markdown_builder.build(
            mapped_regions=mapped_regions, page_num=page_num
        )

        # Count headings and tables
        heading_count = 0
        table_count = 0
        for region in mapped_regions:
            if region.label in ("Section_Header", "Title"):
                heading_count += 1
            elif region.label == "Table":
                table_count += 1

        return HybridExtractionResult(
            page_num=page_num,
            regions=mapped_regions,
            markdown=markdown,
            heading_count=heading_count,
            table_count=table_count,
            fallback_used=False,
        )

    def extract_document_markdown(self, pages_data: List[dict]) -> Tuple[str, dict]:
        """
        Extract Markdown for an entire document.

        Args:
            pages_data: List of page data dicts, each containing:
                - page_image: bytes
                - gcv_words: List[dict]
                - page_num: int
                - page_width: int
                - page_height: int
                - fallback_text: str

        Returns:
            Tuple of (full_markdown, stats_dict)
            stats_dict contains: total_headings, total_tables, pages_with_fallback

        Requirements: 5.1, 5.3
        """
        markdown_parts = []
        total_headings = 0
        total_tables = 0
        pages_with_fallback = 0

        for page_data in pages_data:
            result = self.extract_hybrid_markdown(
                page_image=page_data["page_image"],
                gcv_words=page_data["gcv_words"],
                page_num=page_data["page_num"],
                page_width=page_data["page_width"],
                page_height=page_data["page_height"],
                fallback_text=page_data.get("fallback_text", ""),
            )

            markdown_parts.append(result.markdown)
            total_headings += result.heading_count
            total_tables += result.table_count
            if result.fallback_used:
                pages_with_fallback += 1

            logger.debug(
                f"Page {result.page_num}: {result.heading_count} headings, "
                f"{result.table_count} tables, fallback={result.fallback_used}"
            )

        full_markdown = "\n\n".join(markdown_parts)

        stats = {
            "total_headings": total_headings,
            "total_tables": total_tables,
            "pages_with_fallback": pages_with_fallback,
            "total_pages": len(pages_data),
        }

        return full_markdown, stats

    def cleanup(self):
        """Release GPU resources."""
        self.layout_detector.cleanup()


# Singleton instance for reuse
_orchestrator_instance: Optional[HybridExtractionOrchestrator] = None


def get_hybrid_orchestrator() -> HybridExtractionOrchestrator:
    """
    Get the singleton HybridExtractionOrchestrator instance.

    Returns:
        HybridExtractionOrchestrator instance
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = HybridExtractionOrchestrator()
    return _orchestrator_instance
