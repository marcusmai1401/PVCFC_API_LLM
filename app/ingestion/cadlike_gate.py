"""
CAD-like Gate Module
Auto-detect CAD-like PDFs (P&ID/PFD/ISO/Loop/Schematic) via multi-feature scoring

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 3
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
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

    # Enhanced fields for hybrid detection
    confidence: str = "UNKNOWN"  # HIGH, MEDIUM, LOW
    detection_method: str = "VECTOR"  # VECTOR, IMAGE, HYBRID
    image_features: Dict[str, float] = field(default_factory=dict)


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
        Evaluate if a PDF is CAD-like using hybrid vector + image analysis

        Args:
            pdf_path: Path to PDF file
            doc_metadata: Optional pre-extracted metadata

        Returns:
            GateDecision with score, classification, and detection method
        """
        logger.debug(f"Evaluating CAD-like score for: {pdf_path.name}")

        try:
            doc = fitz.open(str(pdf_path))

            # Sample pages
            pages_to_sample = self._select_sample_pages(doc)
            logger.debug(f"Sampling pages: {pages_to_sample}")

            # ========== STEP 1: Compute vector features (existing) ==========
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

            # Compute weighted vector score
            vector_score = sum(
                self.weights[k] * features[k] for k in self.weights.keys()
            )
            logger.debug(f"Vector score: {vector_score:.3f}")

            # ========== STEP 2: Conditional image analysis ==========
            image_score = None
            image_features_dict = {}

            # Trigger image analysis if vector score is uncertain (< 0.55)
            if vector_score < self.thresholds.get("vector_confident", 0.55):
                logger.info(
                    f"Vector score {vector_score:.3f} < 0.55, running image analysis..."
                )
                try:
                    image_features_dict = self._compute_image_features(
                        doc, pages_to_sample
                    )
                    if image_features_dict:  # Valid results
                        image_score = image_features_dict.get("image_score", 0.0)
                        logger.info(f"Image score: {image_score:.3f}")
                    else:
                        logger.warning("Image analysis returned no valid results")
                except Exception as e:
                    logger.warning(f"Image analysis failed: {e}")
            else:
                logger.debug(
                    f"Vector score {vector_score:.3f} >= 0.55, skipping image analysis"
                )

            # ========== STEP 3: Hybrid classification ==========
            decision = self._classify_hybrid(
                vector_score=vector_score,
                image_score=image_score,
                image_features=image_features_dict,
                filename=pdf_path.name,
            )

            is_cadlike = decision["is_cadlike"]
            confidence = decision["confidence"]
            detection_method = decision["detection_method"]
            final_score = decision["final_score"]
            boosted = decision.get("boosted_by_filename", False)

            logger.info(
                f"Final decision: CAD-like={is_cadlike}, Score={final_score:.3f}, "
                f"Confidence={confidence}, Method={detection_method}"
            )

            # ========== STEP 4: Select taggy pages if CAD-like ==========
            taggy_pages = []
            if is_cadlike:
                taggy_pages = self._select_taggy_pages(doc)

            doc.close()

            return GateDecision(
                is_cadlike=is_cadlike,
                score=final_score,
                pages_sampled=pages_to_sample,
                taggy_pages=taggy_pages,
                features=features,
                boosted_by_filename=boosted,
                confidence=confidence,
                detection_method=detection_method,
                image_features=image_features_dict,
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
                confidence="UNKNOWN",
                detection_method="ERROR",
                image_features={},
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

    # ============================================================================
    # IMAGE-BASED FEATURE DETECTION (for scanned PDFs)
    # ============================================================================

    def _pixmap_to_numpy(self, pixmap: fitz.Pixmap) -> np.ndarray:
        """
        Convert PyMuPDF pixmap to numpy array for OpenCV processing

        Args:
            pixmap: PyMuPDF pixmap object

        Returns:
            RGB numpy array (height x width x 3)
        """
        img = np.frombuffer(pixmap.samples, dtype=np.uint8)
        img = img.reshape(pixmap.height, pixmap.width, pixmap.n)

        # Convert RGBA to RGB if needed
        if pixmap.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pixmap.n == 1:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        return img

    def _check_page_quality(self, img: np.ndarray) -> Tuple[bool, Optional[str]]:
        """
        Check if page image is suitable for analysis

        Args:
            img: Numpy array image

        Returns:
            (is_valid, reason) tuple
        """
        mean_brightness = np.mean(img)
        std_dev = np.std(img)

        # Check 1: Not blank page (too bright)
        if mean_brightness > 250:
            return False, "blank_page"

        # Check 2: Not corrupted (too dark)
        if mean_brightness < 10:
            return False, "corrupted_page"

        # Check 3: Has variation (not solid color)
        if std_dev < 5:
            return False, "no_variation"

        return True, None

    def _detect_shapes(self, img: np.ndarray) -> float:
        """
        Detect circles and rectangles using OpenCV

        Args:
            img: RGB numpy array

        Returns:
            Normalized shape score [0, 1]
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

            # Detect circles (valves, instruments, connection points)
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=20,
                param1=50,
                param2=30,
                minRadius=5,
                maxRadius=100,
            )
            circle_count = len(circles[0]) if circles is not None else 0

            # Detect rectangles (equipment boxes, frames)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(
                edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            rectangles = 0
            for contour in contours:
                approx = cv2.approxPolyDP(
                    contour, 0.02 * cv2.arcLength(contour, True), True
                )

                if len(approx) == 4:  # Rectangle has 4 corners
                    # Additional validation
                    area = cv2.contourArea(contour)
                    if 100 < area < 10000:  # Size filter
                        x, y, w, h = cv2.boundingRect(approx)
                        aspect_ratio = float(w) / h if h > 0 else 0
                        if 0.2 < aspect_ratio < 5.0:  # Not too elongated
                            rectangles += 1

            # Normalize scores
            circle_score = min(circle_count / 100, 1.0)  # Cap at 100 circles
            rectangle_score = min(rectangles / 300, 1.0)  # Cap at 300 rectangles

            # Combined score
            combined = (circle_score + rectangle_score) / 2

            logger.debug(
                f"Shape detection: {circle_count} circles, {rectangles} rectangles → score={combined:.3f}"
            )

            return combined

        except Exception as e:
            logger.warning(f"Shape detection failed: {e}")
            return 0.0

    def _detect_lines(self, img: np.ndarray) -> float:
        """
        Detect long straight lines using Hough Transform

        Args:
            img: RGB numpy array

        Returns:
            Normalized line score [0, 1]
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            # Detect lines
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=50,
                minLineLength=30,
                maxLineGap=10,
            )

            if lines is None:
                return 0.0

            # Count long lines (>100 pixels)
            long_lines = 0
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                if length > 100:
                    long_lines += 1

            # Normalize
            score = min(long_lines / 500, 1.0)  # Cap at 500 long lines

            logger.debug(f"Line detection: {long_lines} long lines → score={score:.3f}")

            return score

        except Exception as e:
            logger.warning(f"Line detection failed: {e}")
            return 0.0

    def _compute_edge_density(self, img: np.ndarray) -> float:
        """
        Compute Canny edge density

        Args:
            img: RGB numpy array

        Returns:
            Normalized edge density [0, 1]
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, threshold1=50, threshold2=150)

            edge_pixels = np.sum(edges > 0)
            total_pixels = edges.shape[0] * edges.shape[1]

            density = edge_pixels / total_pixels if total_pixels > 0 else 0.0

            # Normalize to 25% cap (CAD drawings typically 15-30%)
            normalized = min(density / 0.25, 1.0)

            logger.debug(f"Edge density: {density*100:.1f}% → score={normalized:.3f}")

            return normalized

        except Exception as e:
            logger.warning(f"Edge density computation failed: {e}")
            return 0.0

    def _compute_image_features(
        self, doc: fitz.Document, pages_to_sample: List[int]
    ) -> Dict[str, float]:
        """
        Compute image-based features for scanned PDFs

        Args:
            doc: PyMuPDF document
            pages_to_sample: List of page indices to sample

        Returns:
            Dict with shape_detection, line_detection, edge_density scores
        """
        shape_scores = []
        line_scores = []
        edge_scores = []

        logger.info(
            f"Computing image features on {len(pages_to_sample)} pages (300 DPI)..."
        )

        for page_idx in pages_to_sample:
            page = doc[page_idx]

            try:
                # Render page to image at 300 DPI for accuracy
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                img = self._pixmap_to_numpy(pix)

                # Quality check
                is_valid, reason = self._check_page_quality(img)
                if not is_valid:
                    logger.debug(f"Skipping page {page_idx}: {reason}")
                    continue

                # Compute features
                shape_score = self._detect_shapes(img)
                line_score = self._detect_lines(img)
                edge_score = self._compute_edge_density(img)

                shape_scores.append(shape_score)
                line_scores.append(line_score)
                edge_scores.append(edge_score)

            except Exception as e:
                logger.warning(
                    f"Image feature extraction failed for page {page_idx}: {e}"
                )
                continue

        # Average across valid pages
        result = {
            "shape_detection": np.mean(shape_scores) if shape_scores else 0.0,
            "line_detection": np.mean(line_scores) if line_scores else 0.0,
            "edge_density": np.mean(edge_scores) if edge_scores else 0.0,
        }

        # Calculate weighted image_score using config weights
        image_weights = self.gate_config.get(
            "image_weights",
            {"shape_density": 0.40, "line_density": 0.30, "edge_density": 0.30},
        )

        image_score = (
            image_weights["shape_density"] * result["shape_detection"]
            + image_weights["line_density"] * result["line_detection"]
            + image_weights["edge_density"] * result["edge_density"]
        )

        result["image_score"] = image_score

        logger.info(
            f"Image features: shape={result['shape_detection']:.3f}, "
            f"lines={result['line_detection']:.3f}, edges={result['edge_density']:.3f}, "
            f"score={image_score:.3f}"
        )

        return result

    def _classify_hybrid(
        self,
        vector_score: float,
        image_score: Optional[float],
        image_features: Dict[str, float],
        filename: str,
    ) -> Dict[str, Any]:
        """
        Classify document using hybrid vector + image logic

        Args:
            vector_score: Score from vector-based features [0-1]
            image_score: Score from image-based features [0-1] or None if not computed
            image_features: Dict of individual image feature scores
            filename: PDF filename (for keyword checking)

        Returns:
            Dict with keys: is_cadlike, confidence, detection_method, final_score, boosted_by_filename
        """
        # ========== PATH 1: High confidence vector detection ==========
        if vector_score >= self.thresholds["cadlike"]:
            logger.debug(
                f"Path 1: Vector score {vector_score:.3f} >= 0.55 → CAD-like (VECTOR)"
            )
            return {
                "is_cadlike": True,
                "confidence": "HIGH",
                "detection_method": "VECTOR",
                "final_score": vector_score,
                "boosted_by_filename": False,
            }

        # If image_score is None (not computed), fall back to vector only
        if image_score is None:
            logger.debug(
                f"Path 2: Vector only (no image) score {vector_score:.3f} < 0.55 → Not CAD-like"
            )
            return {
                "is_cadlike": False,
                "confidence": "HIGH",
                "detection_method": "VECTOR",
                "final_score": vector_score,
                "boosted_by_filename": False,
            }

        # ========== PATH 3: Low vector score - likely scanned PDF ==========
        vector_low = self.thresholds.get("vector_low", 0.20)

        if vector_score < vector_low:
            logger.debug(
                f"Path 3: Low vector score {vector_score:.3f} < 0.20, relying on image"
            )

            image_high = self.thresholds.get("image_high_confidence", 0.80)
            image_gray = self.thresholds.get("image_gray_zone", 0.65)

            if image_score >= image_high:
                logger.debug(
                    f"  → Image score {image_score:.3f} >= 0.80 → CAD-like (IMAGE, HIGH)"
                )
                return {
                    "is_cadlike": True,
                    "confidence": "HIGH",
                    "detection_method": "IMAGE",
                    "final_score": image_score,
                    "boosted_by_filename": False,
                }
            elif image_gray <= image_score < image_high:
                # Gray zone [0.55, 0.80) - default to CAD-like with MEDIUM confidence
                # Rationale: scanned drawings with shapes/lines are highly likely CAD-like
                logger.debug(
                    f"  → Image score {image_score:.3f} in gray zone [0.55, 0.80)"
                )
                has_filename_boost = self._check_filename_keywords(Path(filename))

                if has_filename_boost:
                    logger.debug("  → Filename boost → CAD-like (HYBRID, MEDIUM+)")
                    confidence = "HIGH"  # Upgrade to HIGH with filename support
                    method = "HYBRID"
                else:
                    logger.debug(
                        "  → No filename boost, defaulting to CAD-like (IMAGE, MEDIUM)"
                    )
                    confidence = "MEDIUM"  # MEDIUM confidence without filename
                    method = "IMAGE"

                return {
                    "is_cadlike": True,  # Changed: default to CAD-like in gray zone
                    "confidence": confidence,
                    "detection_method": method,
                    "final_score": image_score,
                    "boosted_by_filename": has_filename_boost,
                }
            else:
                logger.debug(
                    f"  → Image score {image_score:.3f} < 0.55 → Not CAD-like (IMAGE, HIGH)"
                )
                return {
                    "is_cadlike": False,
                    "confidence": "HIGH",
                    "detection_method": "IMAGE",
                    "final_score": image_score,
                    "boosted_by_filename": False,
                }

        # ========== PATH 4: Mixed score - combine both (0.20 <= vector_score < 0.55) ==========
        logger.debug(
            f"Path 4: Mixed scores - vector={vector_score:.3f}, image={image_score:.3f}"
        )
        combined = 0.60 * vector_score + 0.40 * image_score
        logger.debug(
            f"  → Combined score: 0.6*{vector_score:.3f} + 0.4*{image_score:.3f} = {combined:.3f}"
        )

        if combined >= self.thresholds["cadlike"]:
            logger.debug(
                f"  → Combined {combined:.3f} >= 0.55 → CAD-like (HYBRID, MEDIUM)"
            )
            return {
                "is_cadlike": True,
                "confidence": "MEDIUM",
                "detection_method": "HYBRID",
                "final_score": combined,
                "boosted_by_filename": False,
            }
        else:
            logger.debug(
                f"  → Combined {combined:.3f} < 0.55 → Not CAD-like (HYBRID, MEDIUM)"
            )
            return {
                "is_cadlike": False,
                "confidence": "MEDIUM",
                "detection_method": "HYBRID",
                "final_score": combined,
                "boosted_by_filename": False,
            }


# Singleton instance
_gate_instance = None


def get_cadlike_gate() -> CADLikeGate:
    """Get singleton CADLikeGate instance"""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = CADLikeGate()
    return _gate_instance
