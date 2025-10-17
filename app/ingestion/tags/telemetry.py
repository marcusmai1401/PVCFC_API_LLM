"""
Telemetry & Runtime Logging for Tag Extraction
No-build validation with JSONL logs and auto-warnings

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 9
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.config import get_config


@dataclass
class TagExtractionTelemetry:
    """Telemetry data for one file's tag extraction"""

    doc_id: str
    cadlike_score: float
    pages_sampled: List[int]
    is_cadlike: bool
    pages_taggy: List[int]
    tags_found_total: int
    tags_found_per_page_p50: float
    tags_found_per_page_p90: float
    ocr_fallback_ratio: float
    legend_excluded_hits: int
    avg_triplet_score: float
    elapsed_sec: float
    timestamp: str
    warnings: List[str]


class TelemetryLogger:
    """
    Log telemetry and generate auto-warnings

    Writes one JSONL line per file to artifacts/logs/tag_extraction_telemetry.jsonl
    """

    def __init__(self):
        """Initialize telemetry logger"""
        self.config = get_config()
        self.log_file = self.config.LOGS_DIR / "tag_extraction_telemetry.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Warning thresholds
        self.thresholds = {
            "min_avg_triplet_score": 6.0,
            "max_ocr_fallback_ratio": 0.20,
            "min_tag_density_p50": 2,
        }

    def log_extraction(
        self,
        doc_id: str,
        cadlike_score: float,
        pages_sampled: List[int],
        is_cadlike: bool,
        taggy_pages: List[int],
        tags_by_page: Dict[int, int],
        ocr_page_count: int,
        total_page_count: int,
        legend_excluded: int,
        avg_triplet_score: float,
        elapsed_sec: float,
    ):
        """
        Log telemetry for one document and generate warnings

        Args:
            doc_id: Document ID
            cadlike_score: Gate score
            pages_sampled: Pages used for gate evaluation
            is_cadlike: Gate decision
            taggy_pages: Pages selected as taggy
            tags_by_page: Dict mapping page → tag count
            ocr_page_count: Number of pages that used OCR
            total_page_count: Total pages processed
            legend_excluded: Number of legend/notes exclusions
            avg_triplet_score: Average score of accepted triplets
            elapsed_sec: Processing time
        """
        # Compute per-page stats
        tag_counts = list(tags_by_page.values())
        tags_total = sum(tag_counts)

        if tag_counts:
            import numpy as np

            p50 = float(np.percentile(tag_counts, 50))
            p90 = float(np.percentile(tag_counts, 90))
        else:
            p50 = 0.0
            p90 = 0.0

        # OCR fallback ratio
        ocr_ratio = ocr_page_count / total_page_count if total_page_count > 0 else 0.0

        # Generate warnings
        warnings = self._generate_warnings(
            is_cadlike=is_cadlike,
            tags_total=tags_total,
            cadlike_score=cadlike_score,
            ocr_ratio=ocr_ratio,
            avg_triplet_score=avg_triplet_score,
            p50=p50,
        )

        # Build telemetry object
        telemetry = TagExtractionTelemetry(
            doc_id=doc_id,
            cadlike_score=round(cadlike_score, 3),
            pages_sampled=pages_sampled,
            is_cadlike=is_cadlike,
            pages_taggy=taggy_pages,
            tags_found_total=tags_total,
            tags_found_per_page_p50=round(p50, 1),
            tags_found_per_page_p90=round(p90, 1),
            ocr_fallback_ratio=round(ocr_ratio, 3),
            legend_excluded_hits=legend_excluded,
            avg_triplet_score=round(avg_triplet_score, 2),
            elapsed_sec=round(elapsed_sec, 2),
            timestamp=datetime.utcnow().isoformat(),
            warnings=warnings,
        )

        # Write to log file
        with open(self.log_file, "a", encoding="utf-8") as f:
            json_line = json.dumps(asdict(telemetry), ensure_ascii=False)
            f.write(json_line + "\n")

        # Log warnings
        if warnings:
            logger.warning(
                f"Tag extraction warnings for {doc_id}: {'; '.join(warnings)}"
            )
        else:
            logger.info(
                f"Tag extraction telemetry for {doc_id}: "
                f"{tags_total} tags, score={cadlike_score:.2f}, "
                f"p50={p50:.1f}, elapsed={elapsed_sec:.1f}s"
            )

    def _generate_warnings(
        self,
        is_cadlike: bool,
        tags_total: int,
        cadlike_score: float,
        ocr_ratio: float,
        avg_triplet_score: float,
        p50: float,
    ) -> List[str]:
        """
        Generate auto-warnings based on heuristics

        Spec Section 9 thresholds:
        - CAD-like but zero tags → warn
        - OCR ratio > 0.20 → warn (expect mostly vector)
        - Avg triplet score < 6.0 → warn (tolerances too strict)
        - Low p50 (<2) with high CAD score (>=0.70) → warn

        Returns:
            List of warning messages
        """
        warnings = []

        # Warning 1: CAD-like but zero tags
        if is_cadlike and tags_total == 0:
            warnings.append(
                "CAD-like doc (score={:.2f}) but zero tags extracted - "
                "check if tags exist or tolerances too strict".format(cadlike_score)
            )

        # Warning 2: High OCR ratio
        if ocr_ratio > self.thresholds["max_ocr_fallback_ratio"]:
            warnings.append(
                "High OCR fallback ratio ({:.1f}%) - "
                "expect mostly vector PDFs in corpus".format(ocr_ratio * 100)
            )

        # Warning 3: Low triplet scores
        if avg_triplet_score < self.thresholds["min_avg_triplet_score"]:
            warnings.append(
                "Low avg triplet score ({:.1f}) - "
                "assembler tolerances might be too strict".format(avg_triplet_score)
            )

        # Warning 4: Low tag density despite high CAD score
        if p50 < self.thresholds["min_tag_density_p50"] and cadlike_score >= 0.70:
            warnings.append(
                "Low tag density (p50={:.1f}) despite high CAD score ({:.2f}) - "
                "check taggy page selection".format(p50, cadlike_score)
            )

        return warnings
