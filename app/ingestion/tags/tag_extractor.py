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

        # Find UNIT and SUFFIX candidates near PREFIX (flexible vertical order)
        unit_candidates = [
            s
            for s in all_spans
            if s.span_id != prefix_span.span_id and self.unit_regex.match(s.text)
        ]

        suffix_candidates = [
            s
            for s in all_spans
            if s.span_id != prefix_span.span_id and self.suffix_regex.match(s.text)
        ]

        if not suffix_candidates:
            # SUFFIX is required; UNIT is optional
            return None

        # Find best UNIT (x-aligned and within y-gap tolerance), regardless of above/below
        best_unit = None
        best_unit_score = -1.0

        for unit_span in unit_candidates:
            score = self._score_alignment(prefix_span, unit_span, "near", prefix_font)
            if score > best_unit_score:
                best_unit_score = score
                best_unit = unit_span

        # Find best SUFFIX (x-aligned and within y-gap tolerance), regardless of above/below
        best_suffix = None
        best_suffix_score = -1.0

        for suffix_span in suffix_candidates:
            score = self._score_alignment(prefix_span, suffix_span, "near", prefix_font)
            if score > best_suffix_score:
                best_suffix_score = score
                best_suffix = suffix_span

        # Must have SUFFIX; UNIT is optional
        if best_suffix is None or best_suffix_score <= 0:
            return None

        # Compute triplet score
        triplet_score = self._score_triplet(best_unit, prefix_span, best_suffix, layout)

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

        # If candidate rotated ~90° relative to anchor, swap axes
        # (vertical text appears horizontal in PDF coords)
        if 75 <= abs(delta_rot) <= 105:  # ~90° rotation
            # Swap: what appears as Y-distance is actually X-distance
            x_delta = abs(dy_raw)  # Cross-axis alignment
            y_delta = abs(dx_raw)  # Along-axis distance
        else:
            # Normal case: same orientation
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

    def _score_triplet(
        self,
        unit_span: Optional[TextSpan],
        prefix_span: TextSpan,
        suffix_span: TextSpan,
        layout: PageLayout,
    ) -> float:
        """
        Score complete triplet using weighted features

        Args:
            unit_span: UNIT span (optional)
            prefix_span: PREFIX span
            suffix_span: SUFFIX span
            layout: Page layout

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
                score += self.score_weights["y_uniform"] * uniformity
        else:
            # No UNIT, give partial score if PREFIX-SUFFIX gap is reasonable
            score += self.score_weights["y_uniform"] * 0.5

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
