"""
CAD-like Tag Extraction Orchestrator
Main pipeline coordinating gate, layout, extraction, crops, and telemetry

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 2
"""

import time
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.config import get_config
from app.ingestion.cadlike_gate import get_cadlike_gate
from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.crops import CropGenerator
from app.ingestion.tags.schemas import TagEntity
from app.ingestion.tags.tag_extractor import TagExtractor
from app.ingestion.tags.telemetry import TelemetryLogger


class TagExtractionOrchestrator:
    """
    Orchestrate complete tag extraction pipeline

    Pipeline:
    1. CAD-like gate (auto-detect)
    2. Select taggy pages
    3. Build page layouts (vector-first)
    4. Extract tags (CODE-anchored assembler)
    5. Generate crops (optional, lazy)
    6. Log telemetry + warnings
    """

    def __init__(
        self,
        enable_crops: bool = True,
        lazy_crops: bool = True,
    ):
        """
        Initialize orchestrator

        Args:
            enable_crops: Generate bbox crops
            lazy_crops: Only generate crops on demand (not during ingestion)
        """
        self.config = get_config()

        # Check if feature enabled
        if not self.config.ENABLE_PID_TAGS:
            logger.warning("PID tags extraction is disabled (ENABLE_PID_TAGS=false)")
            self.enabled = False
            return

        self.enabled = True

        # Initialize components
        self.gate = get_cadlike_gate()
        self.layout_builder = PageLayoutBuilder(
            enable_ocr=True,
            enable_drawings=True,
            enable_shape_aware=self.config.ENABLE_SHAPE_AWARE_ROI,
        )
        self.tag_extractor = TagExtractor()

        self.enable_crops = enable_crops and not lazy_crops
        if self.enable_crops:
            self.crop_generator = CropGenerator(dpi=200)
        else:
            self.crop_generator = None

        self.telemetry = TelemetryLogger()

        # Ensure output directories exist
        self.config.ensure_pid_tags_dirs()

        logger.info("Tag Extraction Orchestrator initialized")
        logger.info(f"  Enabled: {self.enabled}")
        logger.info(f"  Gate mode: {self.config.GATE_MODE}")
        logger.info(f"  Crops: {self.enable_crops} (lazy: {lazy_crops})")

    def process_document(self, pdf_path: Path, doc_id: str) -> Optional[Dict]:
        """
        Process a single document through tag extraction pipeline

        Args:
            pdf_path: Path to PDF file
            doc_id: Document ID

        Returns:
            Dict with extraction results, or None if not CAD-like
        """
        if not self.enabled:
            return None

        start_time = time.time()

        logger.info(f"Processing document for tags: {pdf_path.name}")

        # Step 1: CAD-like gate
        gate_decision = self.gate.evaluate(pdf_path)

        logger.info(
            f"Gate decision: is_cadlike={gate_decision.is_cadlike}, "
            f"score={gate_decision.score:.2f}, "
            f"taggy_pages={len(gate_decision.taggy_pages)}"
        )

        # Early exit if not CAD-like
        if not gate_decision.is_cadlike:
            logger.info(
                f"Document is not CAD-like (score={gate_decision.score:.2f}), skipping tag extraction"
            )
            return None

        # Step 2: Process taggy pages
        all_tags = []
        tags_by_page = {}
        ocr_page_count = 0
        legend_excluded = 0
        triplet_scores = []

        for page_num in gate_decision.taggy_pages:
            page_idx = page_num + 1  # Convert 0-based to 1-based

            # Build layout
            layout = self.layout_builder.build_layout(pdf_path, page_idx, doc_id)

            if layout.is_raster:
                ocr_page_count += 1

            # Save layout
            self.layout_builder.save_layout(layout, self.config.LAYOUT_DIR)

            # Extract tags
            page_tags = self.tag_extractor.extract_tags(layout)

            if page_tags:
                all_tags.extend(page_tags)
                tags_by_page[page_idx] = len(page_tags)

                # Collect triplet scores for stats
                for tag in page_tags:
                    # Score encoded in confidence (approx)
                    score = tag.confidence * 11.0  # Reverse normalization
                    triplet_scores.append(score)

        logger.info(f"Extracted {len(all_tags)} tags from {len(tags_by_page)} pages")

        # Step 3: Save tags
        if all_tags:
            tags_file = self.config.ENTITIES_DIR / "tags.jsonl"
            self.tag_extractor.save_tags(all_tags, tags_file)

        # Step 4: Generate crops (if enabled and not lazy)
        crop_paths = {}
        if all_tags and self.enable_crops and self.crop_generator:
            logger.info("Generating crops...")
            crop_paths = self.crop_generator.generate_crops_batch(
                pdf_path, all_tags, self.config.CROPS_DIR
            )

            # Update tag entities with crop paths
            for tag in all_tags:
                if tag.tag in crop_paths:
                    tag.crop_path = crop_paths[tag.tag]

        # Step 5: Compute telemetry
        avg_score = sum(triplet_scores) / len(triplet_scores) if triplet_scores else 0.0
        total_pages = len(gate_decision.taggy_pages)

        elapsed = time.time() - start_time

        # Log telemetry
        self.telemetry.log_extraction(
            doc_id=doc_id,
            cadlike_score=gate_decision.score,
            pages_sampled=[p + 1 for p in gate_decision.pages_sampled],  # 1-based
            is_cadlike=gate_decision.is_cadlike,
            taggy_pages=[p + 1 for p in gate_decision.taggy_pages],
            tags_by_page=tags_by_page,
            ocr_page_count=ocr_page_count,
            total_page_count=total_pages,
            legend_excluded=legend_excluded,
            avg_triplet_score=avg_score,
            elapsed_sec=elapsed,
        )

        # Return results summary
        return {
            "doc_id": doc_id,
            "is_cadlike": True,
            "tags_extracted": len(all_tags),
            "pages_processed": total_pages,
            "crops_generated": len(crop_paths),
            "elapsed_sec": elapsed,
        }
