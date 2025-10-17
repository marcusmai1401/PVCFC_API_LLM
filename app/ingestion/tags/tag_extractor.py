"""
Tag Extractor - Geometry-first extraction
Vertical triplet assembly (AREA + CODE + NUM) with suffix attachment

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


class TagExtractor:
    """
    Extract instrument tags from page layout using CODE-anchored vertical assembly

    Pipeline:
    1. ROI proposals (text-centric vertical columns)
    2. Token role classification (AREA/CODE/NUM/SUFFIX)
    3. CODE-anchored assembler (find AREA above, NUM below)
    4. Scoring and threshold filtering
    5. Suffix attachment within radius
    6. Exclusion zones (LEGEND/NOTES)
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

        # Compile regexes
        self.area_regex = re.compile(self.grammar["area_regex"])
        self.code_regex = re.compile(self.grammar["code_regex"])
        self.num_regex = re.compile(self.grammar["num_regex"])
        self.suffix_regexes = [re.compile(p) for p in self.grammar["suffix_patterns"]]

        # CODE whitelist
        self.code_whitelist = set(self.grammar["code_whitelist"])

        # Assembler config
        self.anchor = self.grammar["anchor"]  # "CODE"
        self.x_tolerance_ratio = self.grammar["x_center_tolerance_ratio"]
        self.y_gap_range = self.grammar["y_gap_ratio_range"]
        self.font_delta_pt = self.grammar["font_size_delta_pt"]
        self.rotation_tolerance = self.grammar["rotation_tolerance_deg"]
        self.score_weights = self.grammar["score_weights"]
        self.pass_threshold = self.grammar["pass_threshold"]
        self.suffix_radius_em = self.grammar["suffix_radius_em"]

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

        # Step 1: Classify token roles
        roles = self._classify_token_roles(layout.spans)

        # Step 2: Filter exclusion zones
        valid_spans = self._filter_exclusion_zones(layout, layout.spans)
        logger.debug(f"After exclusion filter: {len(valid_spans)} spans remain")

        # Step 3: Find CODE anchors (from whitelist)
        code_anchors = [s for s in valid_spans if s.text in self.code_whitelist]
        logger.debug(f"Found {len(code_anchors)} CODE anchor candidates")

        if not code_anchors:
            return []

        # Step 4: Assemble triplets (CODE-anchored)
        triplets = []
        for code_span in code_anchors:
            triplet = self._assemble_triplet(code_span, valid_spans, layout)
            if triplet:
                triplets.append(triplet)

        logger.debug(f"Assembled {len(triplets)} triplets")

        # Step 5: Attach suffixes
        tags = []
        for triplet_data in triplets:
            tag_entity = self._attach_suffix_and_build_entity(
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
        Classify each span as AREA/CODE/NUM/SUFFIX/OTHER

        Args:
            spans: List of text spans

        Returns:
            Dict mapping span_id → role
        """
        roles = {}

        for span in spans:
            text = span.text.strip()

            if self.area_regex.match(text):
                roles[span.span_id] = "AREA"
            elif text in self.code_whitelist:
                roles[span.span_id] = "CODE"
            elif self.num_regex.match(text):
                roles[span.span_id] = "NUM"
            else:
                # Check suffix patterns
                is_suffix = any(p.match(text) for p in self.suffix_regexes)
                if is_suffix:
                    roles[span.span_id] = "SUFFIX"
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
        code_span: TextSpan,
        all_spans: List[TextSpan],
        layout: PageLayout,
    ) -> Optional[Dict]:
        """
        Assemble vertical triplet with CODE as anchor

        Find AREA above and NUM below within tolerances

        Args:
            code_span: CODE span (anchor)
            all_spans: All valid spans on page
            layout: Page layout

        Returns:
            Dict with triplet info if accepted, None otherwise
        """
        code_bbox = code_span.bbox
        code_x_center = (code_bbox[0] + code_bbox[2]) / 2
        code_y_center = (code_bbox[1] + code_bbox[3]) / 2
        code_font = code_span.font_size

        # Find nearest AREA above
        area_candidates = [
            s
            for s in all_spans
            if self.area_regex.match(s.text)
            and (s.bbox[1] + s.bbox[3]) / 2 < code_y_center  # Above CODE
        ]

        # Find nearest NUM below
        num_candidates = [
            s
            for s in all_spans
            if self.num_regex.match(s.text)
            and (s.bbox[1] + s.bbox[3]) / 2 > code_y_center  # Below CODE
        ]

        if not num_candidates:
            # NUM is required; AREA is optional
            return None

        # Find best AREA (closest above, x-aligned)
        best_area = None
        best_area_score = -1

        for area_span in area_candidates:
            score = self._score_alignment(code_span, area_span, "above", code_font)
            if score > best_area_score:
                best_area_score = score
                best_area = area_span

        # Find best NUM (closest below, x-aligned)
        best_num = None
        best_num_score = -1

        for num_span in num_candidates:
            score = self._score_alignment(code_span, num_span, "below", code_font)
            if score > best_num_score:
                best_num_score = score
                best_num = num_span

        # Must have NUM; AREA is optional
        if best_num is None:
            return None

        # Compute triplet score
        triplet_score = self._score_triplet(best_area, code_span, best_num, layout)

        # Pass threshold check
        if triplet_score < self.pass_threshold:
            logger.debug(
                f"Triplet rejected (score {triplet_score:.1f} < {self.pass_threshold}): "
                f"{best_area.text if best_area else ''} {code_span.text} {best_num.text}"
            )
            return None

        # Build triplet data
        triplet = {
            "area_span": best_area,
            "code_span": code_span,
            "num_span": best_num,
            "score": triplet_score,
        }

        logger.debug(
            f"Accepted triplet (score {triplet_score:.1f}): "
            f"{best_area.text if best_area else ''} {code_span.text} {best_num.text}"
        )

        return triplet

    def _score_alignment(
        self, anchor: TextSpan, candidate: TextSpan, direction: str, anchor_font: float
    ) -> float:
        """
        Score alignment between anchor and candidate span

        Args:
            anchor: Anchor span (CODE)
            candidate: Candidate span (AREA or NUM)
            direction: "above" or "below"
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

        # X-center alignment
        anchor_width = anchor_bbox[2] - anchor_bbox[0]
        cand_width = cand_bbox[2] - cand_bbox[0]
        min_width = min(anchor_width, cand_width)

        x_delta = abs(anchor_x_center - cand_x_center)
        x_tolerance = self.x_tolerance_ratio * min_width

        if x_delta > x_tolerance:
            return 0.0  # Not aligned

        # Y-spacing check
        y_delta = abs(cand_y_center - anchor_y_center)

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
        area_span: Optional[TextSpan],
        code_span: TextSpan,
        num_span: TextSpan,
        layout: PageLayout,
    ) -> float:
        """
        Score complete triplet using weighted features

        Args:
            area_span: AREA span (optional)
            code_span: CODE span
            num_span: NUM span
            layout: Page layout

        Returns:
            Total score
        """
        score = 0.0

        # +4: Regex triplet match (AREA+CODE+NUM in correct order)
        if area_span:
            area_text = area_span.text
            code_text = code_span.text
            num_text = num_span.text

            # Check regex match
            if self.area_regex.match(area_text) and code_text in self.code_whitelist:
                if self.num_regex.match(num_text):
                    score += self.score_weights["triplet_regex"]
        else:
            # CODE + NUM only (no AREA) - give partial score
            if code_span.text in self.code_whitelist and self.num_regex.match(
                num_span.text
            ):
                score += self.score_weights["triplet_regex"] * 0.75

        # +2: X-center alignment quality
        code_bbox = code_span.bbox
        num_bbox = num_span.bbox

        code_x_center = (code_bbox[0] + code_bbox[2]) / 2
        num_x_center = (num_bbox[0] + num_bbox[2]) / 2

        x_delta = abs(code_x_center - num_x_center)
        min_width = min(code_bbox[2] - code_bbox[0], num_bbox[2] - num_bbox[0])

        if min_width > 0:
            x_alignment = 1.0 - min(x_delta / (self.x_tolerance_ratio * min_width), 1.0)
            score += self.score_weights["x_align"] * x_alignment

        # +2: Vertical spacing uniformity
        code_y = (code_bbox[1] + code_bbox[3]) / 2
        num_y = (num_bbox[1] + num_bbox[3]) / 2

        if area_span:
            area_y = (area_span.bbox[1] + area_span.bbox[3]) / 2
            gap1 = abs(code_y - area_y)
            gap2 = abs(num_y - code_y)

            # Uniform if gaps are similar
            gap_diff = abs(gap1 - gap2)
            avg_gap = (gap1 + gap2) / 2
            if avg_gap > 0:
                uniformity = 1.0 - min(gap_diff / avg_gap, 1.0)
                score += self.score_weights["y_uniform"] * uniformity
        else:
            # No AREA, give partial score if CODE-NUM gap is reasonable
            score += self.score_weights["y_uniform"] * 0.5

        # +2: Font size similarity
        fonts = [code_span.font_size, num_span.font_size]
        if area_span:
            fonts.append(area_span.font_size)

        font_variance = max(fonts) - min(fonts)
        font_similarity = 1.0 - min(font_variance / self.font_delta_pt, 1.0)
        score += self.score_weights["font_sim"] * font_similarity

        # +1: Alarm hint (optional bonus)
        # Check if CODE is alarm type (PAL, PSAL, PSAH) and alarm triangle near ROI
        # Simplified: just check CODE type
        if code_span.text in {"PAL", "PSAL", "PSAH", "PALL"}:
            score += self.score_weights["alarm_hint"] * 0.5  # Partial bonus

        return score

    def _attach_suffix_and_build_entity(
        self,
        triplet: Dict,
        all_spans: List[TextSpan],
        layout: PageLayout,
    ) -> Optional[TagEntity]:
        """
        Attach suffix to triplet and build TagEntity

        Args:
            triplet: Dict with area_span, code_span, num_span, score
            all_spans: All spans on page
            layout: Page layout

        Returns:
            TagEntity if valid, None otherwise
        """
        area_span = triplet["area_span"]
        code_span = triplet["code_span"]
        num_span = triplet["num_span"]
        score = triplet["score"]

        # Compute union bbox
        bboxes = [code_span.bbox, num_span.bbox]
        if area_span:
            bboxes.append(area_span.bbox)

        union_bbox = self._union_bbox(bboxes)

        # Expand by suffix radius to search for suffixes
        median_font = code_span.font_size  # Simplified
        radius = self.suffix_radius_em * median_font

        expanded_bbox = [
            union_bbox[0] - radius,
            union_bbox[1] - radius,
            union_bbox[2] + radius,
            union_bbox[3] + radius,
        ]

        # Find suffix candidates within radius
        suffix_candidates = []
        for span in all_spans:
            if span.span_id in [code_span.span_id, num_span.span_id]:
                continue
            if area_span and span.span_id == area_span.span_id:
                continue

            # Check if any suffix pattern matches
            is_suffix = any(p.match(span.text) for p in self.suffix_regexes)
            if not is_suffix:
                continue

            # Check if within expanded bbox
            span_center = [
                (span.bbox[0] + span.bbox[2]) / 2,
                (span.bbox[1] + span.bbox[3]) / 2,
            ]

            if self._point_in_bbox(span_center, expanded_bbox):
                suffix_candidates.append(span)

        # Take first suffix if multiple
        suffix_span = suffix_candidates[0] if suffix_candidates else None
        suffix_text = suffix_span.text if suffix_span else None

        # Update union bbox if suffix found
        if suffix_span:
            union_bbox = self._union_bbox(bboxes + [suffix_span.bbox])

        # Build tag text
        parts = []
        if area_span:
            parts.append(area_span.text)
        parts.append(code_span.text)
        parts.append(num_span.text)

        tag_text = " ".join(parts)
        if suffix_text:
            tag_text += f" {suffix_text}"

        # Build TagEntity
        evidence_ids = [code_span.span_id, num_span.span_id]
        if area_span:
            evidence_ids.append(area_span.span_id)
        if suffix_span:
            evidence_ids.append(suffix_span.span_id)

        # Normalize confidence from score (pass_threshold=6, max reasonable ~11)
        confidence = min(score / 11.0, 1.0)

        tag_entity = TagEntity(
            doc_id=layout.doc_id,
            page=layout.page,
            tag=tag_text,
            parts=TagParts(
                area=area_span.text if area_span else None,
                code=code_span.text,
                num=num_span.text,
                suffix=suffix_text,
            ),
            bbox=union_bbox,
            rotation=code_span.rotation_deg,
            confidence=confidence,
            evidence_span_ids=evidence_ids,
            has_suffix=suffix_span is not None,
        )

        return tag_entity

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
