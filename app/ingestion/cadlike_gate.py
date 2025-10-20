"""
CAD-like Gate Module
Auto-detect CAD-like PDFs (P&ID/PFD/ISO/Loop/Schematic) via multi-feature scoring

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 3
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import yaml
from loguru import logger

from app.config import get_config


@dataclass
class GateDecision:
    """Result of CAD-like gate evaluation"""

    is_cadlike: bool
    score: float
    pages_sampled: List[int]
    taggy_pages: List[int]
    features: Dict[str, float]
    boosted_by_filename: bool = False


class CADLikeGate:
    """
    Auto-detect CAD-like documents using multi-feature scoring

    Features:
    - Producer/Creator metadata keywords
    - Geometry density (vector paths/lines)
    - Short CAPS tokens rate
    - 3-piece tag regex hits
    - Technical suffix presence
    - Non-A4 large page
    - Multiple rotations
    - Leader-like lines (optional)
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize CAD-like gate with configuration

        Args:
            config_path: Path to cadlike_gate.yaml (default from PipelineConfig)
        """
        self.config = get_config()

        # Load gate config
        if config_path is None:
            config_path = self.config.CADLIKE_GATE_CONFIG

        with open(config_path, "r", encoding="utf-8") as f:
            self.gate_config = yaml.safe_load(f)

        self.weights = self.gate_config["weights"]
        self.producer_keywords = self.gate_config["producer_keywords"]
        self.regex_3piece = self.gate_config["regex_3piece"]
        self.thresholds = self.gate_config["thresholds"]
        self.sample_config = self.gate_config["sample_pages"]
        self.gray_zone_keywords = self.gate_config.get("gray_zone_keywords", [])

        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(
                f"Gate weights sum to {weight_sum:.3f}, not 1.0. "
                "Scores may be out of range."
            )

    def evaluate(
        self, pdf_path: Path, doc_metadata: Optional[Dict] = None
    ) -> GateDecision:
        """
        Evaluate if a PDF is CAD-like

        Args:
            pdf_path: Path to PDF file
            doc_metadata: Optional pre-extracted metadata

        Returns:
            GateDecision with score and classification
        """
        logger.debug(f"Evaluating CAD-like score for: {pdf_path.name}")

        try:
            doc = fitz.open(str(pdf_path))

            # Sample pages
            pages_to_sample = self._select_sample_pages(doc)
            logger.debug(f"Sampling pages: {pages_to_sample}")

            # Compute features
            features = {}
            features["producer_keyword"] = self._check_producer_keywords(
                doc, doc_metadata
            )
            features["geometry_density"] = self._compute_geometry_density(
                doc, pages_to_sample
            )
            features["short_caps_rate"] = self._compute_short_caps_rate(
                doc, pages_to_sample
            )
            features["regex_3piece_hits"] = self._compute_3piece_hits(
                doc, pages_to_sample
            )
            features["technical_suffix"] = self._check_technical_suffixes(
                doc, pages_to_sample
            )
            features["non_a4_page"] = self._check_large_page(doc)
            features["multi_rotation"] = self._check_rotations(doc, pages_to_sample)
            features["leader_pattern"] = self._check_leader_patterns(
                doc, pages_to_sample
            )

            # Compute weighted score
            score = sum(self.weights[k] * features[k] for k in self.weights.keys())

            # Classify
            is_cadlike = score >= self.thresholds["cadlike"]
            boosted = False

            # Gray zone boost by filename
            if (
                self.thresholds["gray_zone_low"] <= score < self.thresholds["cadlike"]
                and self.thresholds["gray_zone_boost_keywords"]
            ):
                if self._check_filename_keywords(pdf_path):
                    is_cadlike = True
                    boosted = True
                    logger.info(
                        f"Gray zone score {score:.2f} boosted to CAD-like "
                        f"by filename: {pdf_path.name}"
                    )

            # Select taggy pages if CAD-like
            taggy_pages = []
            if is_cadlike:
                taggy_pages = self._select_taggy_pages(doc)

            doc.close()

            return GateDecision(
                is_cadlike=is_cadlike,
                score=score,
                pages_sampled=pages_to_sample,
                taggy_pages=taggy_pages,
                features=features,
                boosted_by_filename=boosted,
            )

        except Exception as e:
            logger.error(f"Gate evaluation failed for {pdf_path.name}: {e}")
            # Default to not CAD-like on error
            return GateDecision(
                is_cadlike=False,
                score=0.0,
                pages_sampled=[],
                taggy_pages=[],
                features={},
            )

    def _select_sample_pages(self, doc: fitz.Document) -> List[int]:
        """Select pages to sample for gate evaluation"""
        total_pages = len(doc)

        if total_pages <= 5:
            # Sample all pages for small docs
            return list(range(total_pages))

        # Strategy: [1, 2, 3, mid, last]
        mid = total_pages // 2
        last = total_pages - 1

        sample = [0, 1, 2, mid, last]  # 0-indexed

        # Remove duplicates and sort
        sample = sorted(set(p for p in sample if 0 <= p < total_pages))

        return sample

    def _check_producer_keywords(
        self, doc: fitz.Document, doc_metadata: Optional[Dict]
    ) -> float:
        """
        Check if PDF metadata contains CAD software keywords

        Returns:
            1.0 if match found, 0.0 otherwise
        """
        # Check PyMuPDF metadata
        metadata = doc.metadata
        producer = (metadata.get("producer", "") or "").upper()
        creator = (metadata.get("creator", "") or "").upper()

        combined = f"{producer} {creator}"

        for keyword in self.producer_keywords:
            if keyword.upper() in combined:
                logger.debug(f"Producer keyword match: {keyword}")
                return 1.0

        return 0.0

    def _compute_geometry_density(self, doc: fitz.Document, pages: List[int]) -> float:
        """
        Compute normalized geometry density (vector paths + lines per area)

        Returns:
            Normalized score [0, 1]
        """
        total_paths = 0
        total_area = 0

        for page_idx in pages:
            page = doc[page_idx]
            page_area = page.rect.width * page.rect.height
            total_area += page_area

            # Count vector paths
            try:
                drawings = page.get_drawings()
                total_paths += len(drawings)
            except Exception:
                # get_drawings() not available or failed
                pass

        if total_area == 0:
            return 0.0

        # Normalize density
        density = total_paths / total_area

        # Cap at reasonable max (e.g., 0.001 paths per point^2)
        max_density = 0.001
        normalized = min(density / max_density, 1.0)

        return normalized

    def _compute_short_caps_rate(self, doc: fitz.Document, pages: List[int]) -> float:
        """
        Compute ratio of short CAPS tokens (2-4 letters) to all tokens

        Returns:
            Ratio [0, 1]
        """
        caps_pattern = re.compile(r"\b[A-Z]{2,4}\b")
        total_spans = 0
        caps_spans = 0

        for page_idx in pages:
            page = doc[page_idx]
            text = page.get_text()

            tokens = text.split()
            total_spans += len(tokens)

            for token in tokens:
                if caps_pattern.match(token):
                    caps_spans += 1

        if total_spans == 0:
            return 0.0

        ratio = caps_spans / total_spans

        # Normalize: typical CAD drawings have ~10-30% CAPS tokens
        # Cap at 0.30 (30%) for normalization
        normalized = min(ratio / 0.30, 1.0)

        return normalized

    def _compute_3piece_hits(self, doc: fitz.Document, pages: List[int]) -> float:
        """
        Count 3-piece tag regex hits and normalize

        Returns:
            Normalized score [0, 1]
        """
        pattern = re.compile(self.regex_3piece["pattern"])
        per_page_cap = self.regex_3piece["per_page_cap"]

        total_hits = 0

        for page_idx in pages:
            page = doc[page_idx]
            text = page.get_text()

            matches = pattern.findall(text)
            page_hits = min(len(matches), per_page_cap)
            total_hits += page_hits

        # Normalize: expect ~5-15 hits per sampled page for typical P&ID
        # Cap at 5 pages * 15 hits = 75
        max_expected = len(pages) * 15
        normalized = min(total_hits / max_expected, 1.0) if max_expected > 0 else 0.0

        return normalized

    def _check_technical_suffixes(self, doc: fitz.Document, pages: List[int]) -> float:
        """
        Check for technical suffix patterns (A/B/C, 2oo3, -201B)

        Returns:
            Normalized presence [0, 1]
        """
        suffix_patterns = [
            r"\b[A-Z]/[A-Z](?:/[A-Z])?\b",  # A/B, A/B/C
            r"\b[1-3]oo[2-4]\b",  # 1oo2, 2oo3
            r"\b-?\d{3,5}[A-Z]\b",  # -201B, 2208A
        ]

        total_hits = 0

        for page_idx in pages:
            page = doc[page_idx]
            text = page.get_text()

            for pattern_str in suffix_patterns:
                pattern = re.compile(pattern_str)
                hits = len(pattern.findall(text))
                total_hits += hits

        # Normalize: expect ~2-10 suffix hits per sampled page
        max_expected = len(pages) * 10
        normalized = min(total_hits / max_expected, 1.0) if max_expected > 0 else 0.0

        return normalized

    def _check_large_page(self, doc: fitz.Document) -> float:
        """
        Check if page size is unusually large (A1/A0)

        Returns:
            1.0 if large, 0.0 if standard
        """
        # Check first page
        if len(doc) == 0:
            return 0.0

        page = doc[0]
        rect = page.rect

        # A4: ~595 x 842 points (portrait)
        # A3: ~842 x 1191
        # A1: ~1684 x 2384
        # A0: ~2384 x 3370

        width = rect.width
        height = rect.height
        max_dim = max(width, height)

        # Large if max dimension > 1500 points (between A3 and A1)
        if max_dim > 1500:
            return 1.0
        else:
            return 0.0

    def _check_rotations(self, doc: fitz.Document, pages: List[int]) -> float:
        """
        Check for presence of rotated text spans

        Returns:
            Normalized ratio of rotated spans [0, 1]
        """
        total_spans = 0
        rotated_spans = 0
        rotation_threshold = 5  # degrees

        for page_idx in pages:
            page = doc[page_idx]

            # Get text with details (dict format includes rotation)
            text_dict = page.get_text("dict")

            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            total_spans += 1
                            # Check rotation (dir field or transform matrix)
                            # PyMuPDF doesn't directly expose rotation, use heuristic
                            # For now, check if line has non-horizontal direction
                            bbox = span.get("bbox", [])
                            if len(bbox) == 4:
                                x0, y0, x1, y1 = bbox
                                # Rough heuristic: if height > width, might be rotated
                                if abs(y1 - y0) > abs(x1 - x0):
                                    rotated_spans += 1

        if total_spans == 0:
            return 0.0

        ratio = rotated_spans / total_spans

        # Normalize: typical CAD has ~5-20% rotated text
        normalized = min(ratio / 0.20, 1.0)

        return normalized

    def _check_leader_patterns(self, doc: fitz.Document, pages: List[int]) -> float:
        """
        Check for leader-like lines (thin lines ending near text)

        Returns:
            1.0 if leader pattern detected, 0.0 otherwise
        """
        # This is a simplified heuristic
        # Full implementation would analyze line endpoints vs text bbox proximity

        for page_idx in pages:
            page = doc[page_idx]

            try:
                drawings = page.get_drawings()

                # Count thin lines (potential leaders)
                thin_lines = 0
                for drawing in drawings:
                    items = drawing.get("items", [])
                    for item in items:
                        # Check if it's a line (simple path)
                        if item[0] == "l":  # line command
                            thin_lines += 1

                # If many thin lines, likely has leader patterns
                if thin_lines > 10:
                    return 1.0

            except Exception:
                pass

        return 0.0

    def _check_filename_keywords(self, pdf_path: Path) -> bool:
        """
        Check if filename contains gray zone boost keywords

        Args:
            pdf_path: PDF file path

        Returns:
            True if keyword found
        """
        filename_upper = pdf_path.name.upper()

        for keyword in self.gray_zone_keywords:
            if keyword.upper() in filename_upper:
                logger.debug(f"Filename keyword match: {keyword}")
                return True

        return False

    def _select_taggy_pages(self, doc: fitz.Document) -> List[int]:
        """
        Select pages likely to contain tags (taggy pages)

        A page is taggy if EITHER:
        - regex_3piece_hits >= min threshold
        - CODE whitelist token count >= min threshold

        Args:
            doc: PyMuPDF document

        Returns:
            List of page indices (0-based)
        """
        # Load tag grammar config for CODE whitelist
        with open(self.config.TAG_GRAMMAR_CONFIG, "r", encoding="utf-8") as f:
            grammar_config = yaml.safe_load(f)

        # Use prefix_whitelist (renamed from code_whitelist)
        prefix_whitelist = set(
            grammar_config.get(
                "prefix_whitelist", grammar_config.get("code_whitelist", [])
            )
        )

        # Load page filters
        with open(self.config.PAGE_FILTERS_CONFIG, "r", encoding="utf-8") as f:
            page_filters = yaml.safe_load(f)

        taggy_rules = page_filters["taggy_page_rules"]
        min_regex_hits = taggy_rules["min_regex_hits_3piece"]
        min_code_tokens = taggy_rules["min_code_tokens"]

        taggy_pages = []
        pattern = re.compile(self.regex_3piece["pattern"])

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text()

            # Check condition 1: regex hits
            regex_hits = len(pattern.findall(text))

            # Check condition 2: CODE whitelist tokens
            tokens = text.split()
            code_count = sum(1 for t in tokens if t in prefix_whitelist)

            # Accept if either condition met
            if regex_hits >= min_regex_hits or code_count >= min_code_tokens:
                taggy_pages.append(page_idx)

        logger.debug(f"Selected {len(taggy_pages)} taggy pages out of {len(doc)}")

        return taggy_pages


# Singleton instance
_gate_instance = None


def get_cadlike_gate() -> CADLikeGate:
    """Get singleton CADLikeGate instance"""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = CADLikeGate()
    return _gate_instance
