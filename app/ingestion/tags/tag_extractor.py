"""
Tag Extractor - Geometry-first extraction
Vertical triplet assembly (UNIT + PREFIX + SUFFIX) with variant/annotation attachment

Updated schema: UNIT (1-3 digits), PREFIX (2-6 letters), SUFFIX (digits only),
                VARIANT (single letter), ANNOTATION (A/B/C, 1oo2 patterns)

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 6
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml
from loguru import logger

from app.config import get_config
from app.ingestion.layout.page_layout_builder import PageLayout, TextSpan

from .schemas import TagEntity, TagParts
from .span_merger import merge_adjacent_digits


class TagExtractor:
    """
    Extract instrument tags from page layout using PREFIX-anchored vertical assembly

    Pipeline:
    1. ROI proposals (text-centric vertical columns)
    2. Token role classification (UNIT/PREFIX/SUFFIX/VARIANT/ANNOTATION)
    3. PREFIX-anchored assembler (find UNIT and SUFFIX near PREFIX)
    4. Scoring and threshold filtering
    5. Variant and annotation attachment within radius
    6. Exclusion zones (LEGEND/NOTES)

    Updated schema:
    - UNIT: 1-3 digits (was AREA with 2 digits only)
    - PREFIX: 2-6 letters (was CODE with 2-4 letters)
    - SUFFIX: 3-5 digits only (was NUM with optional letter)
    - VARIANT: Single letter (A/B/C) - NEW
    - ANNOTATION: A/B/C, 1oo2 patterns - NEW
    """

    def __init__(self):
        """Initialize tag extractor with grammar and filter configs"""
        self.config = get_config()

        # Load tag grammar
        with open(self.config.TAG_GRAMMAR_CONFIG, "r", encoding="utf-8") as f:
            self.grammar = yaml.safe_load(f)

        # Load page filters
        with open(self.config.PAGE_FILTERS_CONFIG, "r", encoding="utf-8") as f:
            self.filters = yaml.safe_load(f)

        # Compile regexes (updated names)
        self.unit_regex = re.compile(self.grammar["unit_regex"])
        self.prefix_regex = re.compile(self.grammar["prefix_regex"])
        self.suffix_regex = re.compile(self.grammar["suffix_regex"])
        self.variant_regex = re.compile(self.grammar["variant_regex"])
        self.annotation_regexes = [
            re.compile(p) for p in self.grammar["annotation_patterns"]
        ]

        # PREFIX whitelist (was code_whitelist)
        self.prefix_whitelist = set(self.grammar["prefix_whitelist"])

        # Assembler config
        self.anchor = self.grammar["anchor"]  # "PREFIX"
        self.x_tolerance_ratio = self.grammar["x_center_tolerance_ratio"]
        self.y_gap_range = self.grammar["y_gap_ratio_range"]
        self.font_delta_pt = self.grammar["font_size_delta_pt"]
        self.rotation_tolerance = self.grammar["rotation_tolerance_deg"]
        self.score_weights = self.grammar["score_weights"]
        self.pass_threshold = self.grammar["pass_threshold"]
        self.variant_radius_em = self.grammar["variant_radius_em"]
        self.annotation_radius_em = self.grammar["annotation_radius_em"]

        # Exclusion patterns
        self.exclude_titles = [re.compile(p) for p in self.filters["exclude_titles"]]

        # Divider line handling (NEW)
        self.ignore_divider_lines = self.grammar.get(
            "ignore_divider_lines_in_bubbles", True
        )

    def extract_tags(self, layout: PageLayout) -> List[TagEntity]:
        """
        Extract tags from page layout

        Args:
            layout: PageLayout with spans

        Returns:
            List of extracted TagEntity objects
        """
        logger.debug(
            f"Extracting tags from {layout.doc_id} page {layout.page} "
            f"({len(layout.spans)} spans)"
        )

        if not layout.spans:
            return []

        # Step 0: Merge fragmented digit spans (e.g., "2" "0" "4" "9" → "2049")
        merged_spans = merge_adjacent_digits(layout.spans)
        logger.debug(f"After digit merging: {len(merged_spans)} spans")

        # Step 1: Classify token roles
        roles = self._classify_token_roles(merged_spans)

        # Step 2: Filter exclusion zones
        valid_spans = self._filter_exclusion_zones(layout, merged_spans)
        logger.debug(f"After exclusion filter: {len(valid_spans)} spans remain")

        # Step 3: Find PREFIX anchors (from whitelist)
        prefix_anchors = [s for s in valid_spans if s.text in self.prefix_whitelist]
        logger.debug(f"Found {len(prefix_anchors)} PREFIX anchor candidates")

        if not prefix_anchors:
            return []

        # Step 4: Assemble triplets (PREFIX-anchored)
        triplets = []
        for prefix_span in prefix_anchors:
            triplet = self._assemble_triplet(prefix_span, valid_spans, layout)
            if triplet:
                triplets.append(triplet)

        logger.debug(f"Assembled {len(triplets)} triplets")

        # Step 5: Attach variant and annotation, then build entities
        tags = []
        for triplet_data in triplets:
            tag_entity = self._attach_variant_annotation_and_build_entity(
                triplet_data, valid_spans, layout
            )
            if tag_entity:
                tags.append(tag_entity)

        logger.info(
            f"Extracted {len(tags)} tags from {layout.doc_id} page {layout.page}"
        )

        return tags

    def _classify_token_roles(self, spans: List[TextSpan]) -> Dict[int, str]:
        """
        Classify each span as UNIT/PREFIX/SUFFIX/VARIANT/ANNOTATION/OTHER

        Args:
            spans: List of text spans

        Returns:
            Dict mapping span_id → role
        """
        roles = {}

        for span in spans:
            text = span.text.strip()

            # Check UNIT (was AREA) - 1-3 digits
            if self.unit_regex.match(text):
                roles[span.span_id] = "UNIT"

            # Check PREFIX (was CODE) - from whitelist
            elif text in self.prefix_whitelist:
                roles[span.span_id] = "PREFIX"

            # Check SUFFIX (was NUM) - 3-5 digits only, no letters!
            elif self.suffix_regex.match(text):
                roles[span.span_id] = "SUFFIX"

            # Check VARIANT - single letter (A/B/C)
            elif self.variant_regex.match(text):
                roles[span.span_id] = "VARIANT"

            # Check ANNOTATION - A/B/C, 1oo2 patterns
            elif any(p.match(text) for p in self.annotation_regexes):
                roles[span.span_id] = "ANNOTATION"

            else:
                roles[span.span_id] = "OTHER"

        return roles

    def _filter_exclusion_zones(
        self, layout: PageLayout, spans: List[TextSpan]
    ) -> List[TextSpan]:
        """
        Filter out spans in exclusion zones (LEGEND/NOTES/headers/footers)

        Args:
            layout: Page layout
            spans: List of spans

        Returns:
            Filtered spans
        """
        valid_spans = []

        # Header/footer margin
        if self.filters["exclude_layout"]["header_footer"]:
            margin_ratio = self.filters["exclude_layout"]["header_footer_margin_ratio"]
            header_y = layout.page_height * margin_ratio
            footer_y = layout.page_height * (1 - margin_ratio)
        else:
            header_y = 0
            footer_y = layout.page_height

        for span in spans:
            bbox = span.bbox
            if len(bbox) != 4:
                continue

            x0, y0, x1, y1 = bbox
            y_center = (y0 + y1) / 2

            # Check header/footer exclusion
            if y_center < header_y or y_center > footer_y:
                logger.debug(f"Excluded (header/footer): {span.text}")
                continue

            # Check title patterns (LEGEND, NOTES, etc.)
            is_excluded = False
            for pattern in self.exclude_titles:
                if pattern.match(span.text):
                    logger.debug(f"Excluded (title pattern): {span.text}")
                    is_excluded = True
                    break

            if not is_excluded:
                valid_spans.append(span)

        return valid_spans

    def _assemble_triplet(
        self,
        prefix_span: TextSpan,
        all_spans: List[TextSpan],
        layout: PageLayout,
    ) -> Optional[Dict]:
        """
        Assemble vertical triplet with PREFIX as anchor

        Find UNIT and SUFFIX near PREFIX with x-alignment and y-gap tolerance (order-agnostic)

        Args:
            prefix_span: PREFIX span (anchor)
            all_spans: All valid spans on page
            layout: Page layout

        Returns:
            Dict with triplet info if accepted, None otherwise
        """
        prefix_bbox = prefix_span.bbox
        prefix_x_center = (prefix_bbox[0] + prefix_bbox[2]) / 2
        prefix_y_center = (prefix_bbox[1] + prefix_bbox[3]) / 2
        prefix_font = prefix_span.font_size

        # Define search radius for candidates (font-based, ~100pt max)
        # This prevents picking up distant noise like legend/note numbers
        search_radius = max(100, 20 * prefix_font)  # At least 100pt or 20x font height

        # Find UNIT and SUFFIX candidates near PREFIX (flexible vertical order)
        # NEW: Pre-filter by spatial proximity before scoring
        unit_candidates = []
        for s in all_spans:
            if s.span_id == prefix_span.span_id or not self.unit_regex.match(s.text):
                continue
            # Check if within search radius
            s_x = (s.bbox[0] + s.bbox[2]) / 2
            s_y = (s.bbox[1] + s.bbox[3]) / 2
            dist = ((s_x - prefix_x_center) ** 2 + (s_y - prefix_y_center) ** 2) ** 0.5
            if dist <= search_radius:
                unit_candidates.append(s)

        suffix_candidates = []
        for s in all_spans:
            if s.span_id == prefix_span.span_id or not self.suffix_regex.match(s.text):
                continue
            # Check if within search radius
            s_x = (s.bbox[0] + s.bbox[2]) / 2
            s_y = (s.bbox[1] + s.bbox[3]) / 2
            dist = ((s_x - prefix_x_center) ** 2 + (s_y - prefix_y_center) ** 2) ** 0.5
            if dist <= search_radius:
                suffix_candidates.append(s)

        if not suffix_candidates:
            # SUFFIX is required; UNIT is optional
            return None

        # Find best UNIT (x-aligned and within y-gap tolerance), regardless of above/below
        best_unit = None
        best_unit_score = -1.0
        unit_has_divider = False

        for unit_span in unit_candidates:
            score = self._score_alignment(prefix_span, unit_span, "near", prefix_font)
            if score > best_unit_score:
                best_unit_score = score
                best_unit = unit_span

        # If UNIT score is low/zero but divider exists, retry with relaxed constraints
        if best_unit_score <= 0 and best_unit is not None:
            if self._has_horizontal_divider_between(prefix_span, best_unit, layout):
                logger.debug(
                    f"Horizontal divider detected between UNIT '{best_unit.text}' and PREFIX '{prefix_span.text}'"
                )
                best_unit_score = self._score_alignment_with_divider(
                    prefix_span, best_unit, prefix_font
                )
                unit_has_divider = True

        # Find best SUFFIX (x-aligned and within y-gap tolerance), regardless of above/below
        best_suffix = None
        best_suffix_score = -1.0
        suffix_has_divider = False

        for suffix_span in suffix_candidates:
            score = self._score_alignment(prefix_span, suffix_span, "near", prefix_font)
            if score > best_suffix_score:
                best_suffix_score = score
                best_suffix = suffix_span

        # Must have SUFFIX; UNIT is optional
        if best_suffix is None:
            return None  # No valid SUFFIX found

        if best_suffix_score <= 0:
            # Check if there's a horizontal divider (instrument bubble case)
            # If divider exists, relax y-gap constraint and retry scoring
            if self._has_horizontal_divider_between(prefix_span, best_suffix, layout):
                logger.debug(
                    f"Horizontal divider detected between PREFIX '{prefix_span.text}' and SUFFIX '{best_suffix.text}'"
                )
                # Recompute score with relaxed y-gap tolerance for divider case
                best_suffix_score = self._score_alignment_with_divider(
                    prefix_span, best_suffix, prefix_font
                )
                suffix_has_divider = True
                if best_suffix_score <= 0:
                    return None
            else:
                return None  # SUFFIX exists but failed alignment, no divider

        # Compute triplet score (pass divider flag to adjust y_uniform penalty)
        has_divider = unit_has_divider or suffix_has_divider
        triplet_score = self._score_triplet(
            best_unit, prefix_span, best_suffix, layout, has_divider
        )

        # Pass threshold check
        if triplet_score < self.pass_threshold:
            logger.debug(
                f"Triplet rejected (score {triplet_score:.1f} < {self.pass_threshold}): "
                f"{best_unit.text if best_unit else ''} {prefix_span.text} {best_suffix.text}"
            )
            return None

        # Build triplet data
        triplet = {
            "unit_span": best_unit,
            "prefix_span": prefix_span,
            "suffix_span": best_suffix,
            "score": triplet_score,
            "has_divider": has_divider,
        }

        logger.debug(
            f"Accepted triplet (score {triplet_score:.1f}): "
            f"{best_unit.text if best_unit else ''} {prefix_span.text} {best_suffix.text}"
        )

        return triplet

    def _score_alignment(
        self, anchor: TextSpan, candidate: TextSpan, direction: str, anchor_font: float
    ) -> float:
        """
        Score alignment between anchor and candidate span (rotation-aware)

        Args:
            anchor: Anchor span (PREFIX)
            candidate: Candidate span (UNIT or SUFFIX)
            direction: "near" (order-agnostic proximity check)
            anchor_font: Anchor font size

        Returns:
            Alignment score (higher is better)
        """
        anchor_bbox = anchor.bbox
        cand_bbox = candidate.bbox

        anchor_x_center = (anchor_bbox[0] + anchor_bbox[2]) / 2
        cand_x_center = (cand_bbox[0] + cand_bbox[2]) / 2

        anchor_y_center = (anchor_bbox[1] + anchor_bbox[3]) / 2
        cand_y_center = (cand_bbox[1] + cand_bbox[3]) / 2

        # Compute rotation delta
        anchor_rot = anchor.rotation_deg
        cand_rot = candidate.rotation_deg
        delta_rot = (cand_rot - anchor_rot) % 360
        if delta_rot > 180:
            delta_rot -= 360

        # Transform to anchor's reference frame
        dx_raw = cand_x_center - anchor_x_center
        dy_raw = cand_y_center - anchor_y_center

        # Determine if we need to swap axes based on anchor's absolute rotation
        # If anchor is rotated ~90° (vertical text), swap axes regardless of delta
        # Otherwise, only swap if candidate is rotated ~90° relative to anchor
        # Check if rotation is near 90° or 270° (within 15° tolerance)
        rot_normalized = anchor_rot % 360
        anchor_is_vertical = (75 <= rot_normalized <= 105) or (
            255 <= rot_normalized <= 285
        )

        if anchor_is_vertical or (75 <= abs(delta_rot) <= 105):
            # Swap: what appears as Y-distance is actually X-distance for vertical text
            x_delta = abs(dy_raw)  # Cross-axis alignment
            y_delta = abs(dx_raw)  # Along-axis distance
        else:
            # Normal case: horizontal orientation
            x_delta = abs(dx_raw)
            y_delta = abs(dy_raw)

        # X-center alignment (cross-axis in anchor's frame)
        anchor_width = anchor_bbox[2] - anchor_bbox[0]
        cand_width = cand_bbox[2] - cand_bbox[0]
        min_width = min(anchor_width, cand_width)

        x_tolerance = self.x_tolerance_ratio * min_width

        if x_delta > x_tolerance:
            return 0.0  # Not aligned

        # Y-spacing check (along-axis distance in anchor's frame)

        # Font-based spacing tolerance
        median_font = anchor_font  # Simplified; should use ROI median
        y_min = self.y_gap_range[0] * median_font
        y_max = self.y_gap_range[1] * median_font

        if not (y_min <= y_delta <= y_max):
            return 0.0  # Spacing out of range

        # Font size similarity
        font_delta = abs(candidate.font_size - anchor_font)
        if font_delta > self.font_delta_pt:
            return 0.0  # Font too different

        # Scoring: inversely proportional to distance
        # Closer is better
        distance = (x_delta / x_tolerance) + (y_delta / y_max)
        alignment_score = 1.0 / (1.0 + distance)

        return alignment_score

    def _score_alignment_with_divider(
        self, anchor: TextSpan, candidate: TextSpan, anchor_font: float
    ) -> float:
        """
        Score alignment with relaxed y-gap constraint for divider cases

        When a horizontal divider line separates spans (e.g., instrument bubble),
        the y-gap can be larger than normal while still being a valid triplet.

        Args:
            anchor: Anchor span (PREFIX)
            candidate: Candidate span (SUFFIX)
            anchor_font: Anchor font size

        Returns:
            Alignment score with relaxed y-gap tolerance
        """
        anchor_bbox = anchor.bbox
        cand_bbox = candidate.bbox

        anchor_x_center = (anchor_bbox[0] + anchor_bbox[2]) / 2
        cand_x_center = (cand_bbox[0] + cand_bbox[2]) / 2

        anchor_y_center = (anchor_bbox[1] + anchor_bbox[3]) / 2
        cand_y_center = (cand_bbox[1] + cand_bbox[3]) / 2

        # Compute rotation delta
        anchor_rot = anchor.rotation_deg
        cand_rot = candidate.rotation_deg
        delta_rot = (cand_rot - anchor_rot) % 360
        if delta_rot > 180:
            delta_rot -= 360

        # Transform to anchor's reference frame
        dx_raw = cand_x_center - anchor_x_center
        dy_raw = cand_y_center - anchor_y_center

        # Same logic as _score_alignment
        rot_normalized = anchor_rot % 360
        anchor_is_vertical = (75 <= rot_normalized <= 105) or (
            255 <= rot_normalized <= 285
        )

        if anchor_is_vertical or (75 <= abs(delta_rot) <= 105):
            x_delta = abs(dy_raw)
            y_delta = abs(dx_raw)
        else:
            x_delta = abs(dx_raw)
            y_delta = abs(dy_raw)

        # X-center alignment (same as normal)
        anchor_width = anchor_bbox[2] - anchor_bbox[0]
        cand_width = cand_bbox[2] - cand_bbox[0]
        min_width = min(anchor_width, cand_width)

        x_tolerance = self.x_tolerance_ratio * min_width

        if x_delta > x_tolerance:
            return 0.0  # Not aligned

        # RELAXED Y-spacing for divider case
        # Allow up to 3x the normal max gap (to account for divider line thickness + padding)
        median_font = anchor_font
        y_min = self.y_gap_range[0] * median_font
        y_max = self.y_gap_range[1] * median_font * 3.0  # 3x relaxation

        if not (y_min <= y_delta <= y_max):
            return 0.0  # Still too far even with relaxation

        # Font size similarity (same as normal)
        font_delta = abs(candidate.font_size - anchor_font)
        if font_delta > self.font_delta_pt:
            return 0.0

        # Scoring with relaxed distance
        distance = (x_delta / x_tolerance) + (y_delta / y_max)
        alignment_score = 1.0 / (1.0 + distance)

        return alignment_score

    def _score_triplet(
        self,
        unit_span: Optional[TextSpan],
        prefix_span: TextSpan,
        suffix_span: TextSpan,
        layout: PageLayout,
        has_divider: bool = False,
    ) -> float:
        """
        Score complete triplet using weighted features

        Args:
            unit_span: UNIT span (optional)
            prefix_span: PREFIX span
            suffix_span: SUFFIX span
            layout: Page layout
            has_divider: Whether a divider line exists between components

        Returns:
            Total score
        """
        score = 0.0

        # +4: Regex triplet match (UNIT+PREFIX+SUFFIX in correct order)
        if unit_span:
            unit_text = unit_span.text
            prefix_text = prefix_span.text
            suffix_text = suffix_span.text

            # Check regex match
            if (
                self.unit_regex.match(unit_text)
                and prefix_text in self.prefix_whitelist
            ):
                if self.suffix_regex.match(suffix_text):
                    score += self.score_weights["triplet_regex"]
        else:
            # PREFIX + SUFFIX only (no UNIT) - give partial score
            if prefix_span.text in self.prefix_whitelist and self.suffix_regex.match(
                suffix_span.text
            ):
                score += self.score_weights["triplet_regex"] * 0.75

        # +2: X-center alignment quality
        prefix_bbox = prefix_span.bbox
        suffix_bbox = suffix_span.bbox

        prefix_x_center = (prefix_bbox[0] + prefix_bbox[2]) / 2
        suffix_x_center = (suffix_bbox[0] + suffix_bbox[2]) / 2

        x_delta = abs(prefix_x_center - suffix_x_center)
        min_width = min(
            prefix_bbox[2] - prefix_bbox[0], suffix_bbox[2] - suffix_bbox[0]
        )

        if min_width > 0:
            x_alignment = 1.0 - min(x_delta / (self.x_tolerance_ratio * min_width), 1.0)
            score += self.score_weights["x_align"] * x_alignment

        # +2: Vertical spacing uniformity
        # If divider exists, reduce penalty for non-uniform spacing (expected due to divider)
        prefix_y = (prefix_bbox[1] + prefix_bbox[3]) / 2
        suffix_y = (suffix_bbox[1] + suffix_bbox[3]) / 2

        if unit_span:
            unit_y = (unit_span.bbox[1] + unit_span.bbox[3]) / 2
            gap1 = abs(prefix_y - unit_y)
            gap2 = abs(suffix_y - prefix_y)

            # Uniform if gaps are similar
            gap_diff = abs(gap1 - gap2)
            avg_gap = (gap1 + gap2) / 2
            if avg_gap > 0:
                uniformity = 1.0 - min(gap_diff / avg_gap, 1.0)
                # Reduce weight if divider exists (spacing non-uniformity is expected)
                weight = self.score_weights["y_uniform"] * (0.5 if has_divider else 1.0)
                score += weight * uniformity
        else:
            # No UNIT, give partial score if PREFIX-SUFFIX gap is reasonable
            # Reduce weight if divider exists
            weight = self.score_weights["y_uniform"] * (0.5 if has_divider else 1.0)
            score += weight * 0.5

        # +2: Font size similarity
        fonts = [prefix_span.font_size, suffix_span.font_size]
        if unit_span:
            fonts.append(unit_span.font_size)

        font_variance = max(fonts) - min(fonts)
        font_similarity = 1.0 - min(font_variance / self.font_delta_pt, 1.0)
        score += self.score_weights["font_sim"] * font_similarity

        # +1: Alarm hint (optional bonus)
        # Check if PREFIX is alarm type (PAL, PSAL, PSAH, PAHH, PALL) and alarm triangle near ROI
        # Simplified: just check PREFIX type
        if prefix_span.text in {"PAL", "PSAL", "PSAH", "PAHH", "PALL"}:
            score += self.score_weights["alarm_hint"] * 0.5  # Partial bonus

        return score

    def _attach_variant_annotation_and_build_entity(
        self,
        triplet: Dict,
        all_spans: List[TextSpan],
        layout: PageLayout,
    ) -> Optional[TagEntity]:
        """
        Attach variant and annotation to triplet and build TagEntity

        Args:
            triplet: Dict with unit_span, prefix_span, suffix_span, score
            all_spans: All spans on page
            layout: Page layout

        Returns:
            TagEntity if valid, None otherwise
        """
        unit_span = triplet["unit_span"]
        prefix_span = triplet["prefix_span"]
        suffix_span = triplet["suffix_span"]
        score = triplet["score"]

        # Extract suffix text (digits only)
        suffix_text = suffix_span.text

        # Check if suffix_span contains a variant letter at the end (e.g., "2207A")
        # This handles cases where the digit+letter are in a single span
        variant_from_suffix = None
        if re.match(r"^\d{3,5}[A-Z]$", suffix_text):
            # Extract variant letter and clean suffix
            variant_from_suffix = suffix_text[-1]
            suffix_text = suffix_text[:-1]
            logger.debug(
                f"Extracted variant '{variant_from_suffix}' from suffix span '{suffix_span.text}'"
            )

        # Compute union bbox
        bboxes = [prefix_span.bbox, suffix_span.bbox]
        if unit_span:
            bboxes.append(unit_span.bbox)

        union_bbox = self._union_bbox(bboxes)

        # Search for VARIANT (single letter, very close)
        median_font = prefix_span.font_size  # Simplified
        variant_radius = self.variant_radius_em * median_font

        variant_bbox = [
            union_bbox[0] - variant_radius,
            union_bbox[1] - variant_radius,
            union_bbox[2] + variant_radius,
            union_bbox[3] + variant_radius,
        ]

        variant_span = self._find_nearby_span_by_role(
            all_spans,
            variant_bbox,
            "VARIANT",
            exclude_ids=[prefix_span.span_id, suffix_span.span_id]
            + ([unit_span.span_id] if unit_span else []),
            reference_rotation=prefix_span.rotation_deg,  # NEW: pass rotation for checking
            strict_alignment=True,  # NEW: require strict spatial alignment
        )

        # Use variant from suffix if found, otherwise use nearby span
        variant_text = (
            variant_from_suffix
            if variant_from_suffix
            else (variant_span.text if variant_span else None)
        )

        # Search for ANNOTATION (patterns, farther)
        annotation_radius = self.annotation_radius_em * median_font

        annotation_bbox = [
            union_bbox[0] - annotation_radius,
            union_bbox[1] - annotation_radius,
            union_bbox[2] + annotation_radius,
            union_bbox[3] + annotation_radius,
        ]

        annotation_span = self._find_nearby_span_by_role(
            all_spans,
            annotation_bbox,
            "ANNOTATION",
            exclude_ids=[prefix_span.span_id, suffix_span.span_id]
            + ([unit_span.span_id] if unit_span else [])
            + ([variant_span.span_id] if variant_span else []),
        )

        annotation_text = annotation_span.text if annotation_span else None

        # Update union bbox if variant/annotation found
        bbox_components = bboxes.copy()
        if variant_span:
            bbox_components.append(variant_span.bbox)
        if annotation_span:
            bbox_components.append(annotation_span.bbox)
        union_bbox = self._union_bbox(bbox_components)

        # Build tag text (core tag only, without annotation)
        parts = []
        if unit_span:
            parts.append(unit_span.text)
        parts.append(prefix_span.text)
        parts.append(suffix_text)  # Clean suffix (digits only)
        if variant_text:
            parts[-1] += variant_text  # Append variant to suffix

        tag_text = " ".join(parts)

        # Build TagEntity with new schema
        evidence_ids = [prefix_span.span_id, suffix_span.span_id]
        if unit_span:
            evidence_ids.append(unit_span.span_id)
        if variant_span:
            evidence_ids.append(variant_span.span_id)
        if annotation_span:
            evidence_ids.append(annotation_span.span_id)

        # Normalize confidence from score (pass_threshold=6, max reasonable ~11)
        confidence = min(score / 11.0, 1.0)

        tag_entity = TagEntity(
            doc_id=layout.doc_id,
            page=layout.page,
            tag=tag_text,
            parts=TagParts(
                unit=unit_span.text if unit_span else None,
                prefix=prefix_span.text,
                suffix=suffix_text,  # Digits only!
                variant=variant_text,
                annotation=annotation_text,
            ),
            bbox=union_bbox,
            rotation=prefix_span.rotation_deg,
            confidence=confidence,
            evidence_span_ids=evidence_ids,
            has_variant=variant_text is not None,
            has_annotation=annotation_text is not None,
        )

        return tag_entity

    def _find_nearby_span_by_role(
        self,
        all_spans: List[TextSpan],
        search_bbox: List[float],
        role: str,
        exclude_ids: List[int] = None,
        reference_rotation: float = 0.0,
        strict_alignment: bool = False,
    ) -> Optional[TextSpan]:
        """
        Find a span of specific role within search bbox

        Args:
            all_spans: All spans to search
            search_bbox: Bounding box to search within
            role: Role to match (VARIANT or ANNOTATION)
            exclude_ids: Span IDs to exclude

        Returns:
            First matching span or None
        """
        exclude_ids = exclude_ids or []

        candidates = []
        for span in all_spans:
            if span.span_id in exclude_ids:
                continue

            # Check role
            text = span.text.strip()
            is_match = False

            if role == "VARIANT":
                is_match = self.variant_regex.match(text) is not None
            elif role == "ANNOTATION":
                is_match = any(p.match(text) for p in self.annotation_regexes)

            if not is_match:
                continue

            # NEW: Check rotation alignment if strict mode enabled
            if strict_alignment:
                delta_rot = abs((span.rotation_deg - reference_rotation) % 360)
                if delta_rot > 180:
                    delta_rot = 360 - delta_rot
                if delta_rot > self.rotation_tolerance:
                    # Rotation mismatch - skip this candidate
                    continue

            # Check if within search bbox
            span_center = [
                (span.bbox[0] + span.bbox[2]) / 2,
                (span.bbox[1] + span.bbox[3]) / 2,
            ]

            if self._point_in_bbox(span_center, search_bbox):
                candidates.append(span)

        # Return first candidate (closest to triplet)
        return candidates[0] if candidates else None

    def _union_bbox(self, bboxes: List[List[float]]) -> List[float]:
        """Compute union bounding box"""
        if not bboxes:
            return [0, 0, 0, 0]

        x0 = min(b[0] for b in bboxes)
        y0 = min(b[1] for b in bboxes)
        x1 = max(b[2] for b in bboxes)
        y1 = max(b[3] for b in bboxes)

        return [x0, y0, x1, y1]

    def _point_in_bbox(self, point: List[float], bbox: List[float]) -> bool:
        """Check if point is inside bbox"""
        x, y = point
        x0, y0, x1, y1 = bbox
        return x0 <= x <= x1 and y0 <= y <= y1

    def _has_horizontal_divider_between(
        self, span1: TextSpan, span2: TextSpan, layout: PageLayout
    ) -> bool:
        """
        Check if there's a divider line between two spans (rotation-aware)

        Used for instrument bubbles with internal dividers:
        ┌─────┐
        │ 04  │
        │ PI  │
        ├─────┤  ← Divider line (horizontal for 0°, vertical for 90°)
        │3200 │
        └─────┘

        Handles rotated pages:
        - 0°/180°: horizontal divider (Y constant)
        - 90°/270°: vertical divider (X constant)

        Args:
            span1: First span (e.g., PREFIX)
            span2: Second span (e.g., SUFFIX)
            layout: Page layout with drawings

        Returns:
            True if divider line found between spans
        """
        # Check config flag
        if not self.ignore_divider_lines:
            return False

        if not layout.drawings:
            return False

        # Define the region between the two spans
        bbox1 = span1.bbox
        bbox2 = span2.bbox

        # Determine orientation based on span rotation
        # Assume both spans have similar rotation (they're in the same bubble)
        rotation = span1.rotation_deg
        is_rotated_90 = (
            75 <= abs(rotation % 360 - 90) <= 15
            or 75 <= abs(rotation % 360 - 270) <= 15
        )

        # Use median font size for scaling
        median_font = (span1.font_size + span2.font_size) / 2
        margin = max(5, 0.3 * median_font)  # At least 5pt or 30% of font height

        if is_rotated_90:
            # 90°/270° rotation: divider is vertical, spans separated horizontally
            # X-range: between the two spans
            x_min = min(bbox1[2], bbox2[2])  # Right edge of left span
            x_max = max(bbox1[0], bbox2[0])  # Left edge of right span

            if x_min >= x_max:  # Spans don't have horizontal gap
                return False

            # Y-range: union of both spans (with margin)
            y_min = min(bbox1[1], bbox2[1]) - margin
            y_max = max(bbox1[3], bbox2[3]) + margin
            span_height = y_max - y_min

            # Gap must be small (divider in tight bubble)
            gap_width = x_max - x_min
            max_gap = (
                max(bbox1[2] - bbox1[0], bbox2[2] - bbox2[0]) * 1.5
            )  # 1.5x span width
            if gap_width > max_gap:
                return False  # Gap too large, not a bubble divider
        else:
            # 0°/180° rotation: divider is horizontal, spans separated vertically
            # Y-range: between the two spans
            y_min = min(bbox1[3], bbox2[3])  # Bottom of upper span
            y_max = max(bbox1[1], bbox2[1])  # Top of lower span

            if y_min >= y_max:  # Spans don't have vertical gap
                return False

            # X-range: union of both spans (with margin)
            x_min = min(bbox1[0], bbox2[0]) - margin
            x_max = max(bbox1[2], bbox2[2]) + margin
            span_width = x_max - x_min

            # Gap must be small (divider in tight bubble)
            gap_height = y_max - y_min
            max_gap = (
                max(bbox1[3] - bbox1[1], bbox2[3] - bbox2[1]) * 1.5
            )  # 1.5x span height
            if gap_height > max_gap:
                return False  # Gap too large, not a bubble divider

        # Check for divider lines in this region (horizontal or vertical based on rotation)
        for drawing in layout.drawings:
            if drawing.type != "line":
                continue

            # Line coords: [x0, y0, x1, y1]
            coords = drawing.coords
            if len(coords) < 4:
                continue

            line_x0, line_y0, line_x1, line_y1 = coords[:4]

            # Scale tolerance by page dimensions
            orientation_tolerance = max(
                2, 0.002 * max(layout.page_width, layout.page_height)
            )

            if is_rotated_90:
                # Check for VERTICAL divider (X constant, Y varies)
                if abs(line_x0 - line_x1) > orientation_tolerance:  # Not vertical
                    continue

                line_x = (line_x0 + line_x1) / 2

                # Check if line X is within the gap
                if not (x_min <= line_x <= x_max):
                    continue

                # Check if line Y overlaps with span Y range
                line_y_min = min(line_y0, line_y1)
                line_y_max = max(line_y0, line_y1)
                line_length = abs(line_y_max - line_y_min)

                # Line must be substantial portion of span height (not just tiny segment)
                if line_length < span_height * 0.4:  # At least 40% of span height
                    continue

                # Check if line is too long (crossing multiple bubbles)
                if line_length > span_height * 2.0:  # No more than 2x span height
                    continue

                # Check overlap
                if line_y_max >= y_min and line_y_min <= y_max:
                    logger.debug(
                        f"Found vertical divider (rotated 90°) between spans: "
                        f"line X={line_x:.1f}, gap=[{x_min:.1f}, {x_max:.1f}], "
                        f"line_len={line_length:.1f}, span_height={span_height:.1f}"
                    )
                    return True
            else:
                # Check for HORIZONTAL divider (Y constant, X varies)
                if abs(line_y0 - line_y1) > orientation_tolerance:  # Not horizontal
                    continue

                line_y = (line_y0 + line_y1) / 2

                # Check if line Y is within the gap
                if not (y_min <= line_y <= y_max):
                    continue

                # Check if line X overlaps with span X range
                line_x_min = min(line_x0, line_x1)
                line_x_max = max(line_x0, line_x1)
                line_length = abs(line_x_max - line_x_min)

                # Line must be substantial portion of span width (not just tiny segment)
                if line_length < span_width * 0.4:  # At least 40% of span width
                    continue

                # Check if line is too long (crossing multiple bubbles)
                if line_length > span_width * 2.0:  # No more than 2x span width
                    continue

                # Check overlap
                if line_x_max >= x_min and line_x_min <= x_max:
                    logger.debug(
                        f"Found horizontal divider between spans: "
                        f"line Y={line_y:.1f}, gap=[{y_min:.1f}, {y_max:.1f}], "
                        f"line_len={line_length:.1f}, span_width={span_width:.1f}"
                    )
                    return True

        return False

    def save_tags(self, tags: List[TagEntity], output_file: Path):
        """
        Save extracted tags to JSONL file

        Args:
            tags: List of TagEntity objects
            output_file: Output file path (typically entities/tags.jsonl)
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "a", encoding="utf-8") as f:
            for tag in tags:
                json_line = tag.model_dump_json()
                f.write(json_line + "\n")

        logger.debug(f"Saved {len(tags)} tags to {output_file.name}")
