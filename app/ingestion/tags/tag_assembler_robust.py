"""
Robust Tag Assembler - Handle PDF Extraction Ordering Errors

Problem:
PyMuPDF sometimes extracts text in wrong order:
  Visual order: 04 (top) → PU (middle) → 2049 (bottom)
  Extracted order: 04 → 2049 → PU (WRONG!)

Solution:
- Find all nearby spans (proximity-based, not strict above/below)
- Try all permutations: AREA-CODE-NUM, CODE-AREA-NUM, NUM-CODE-AREA, etc.
- Score by spatial proximity + regex validation
- Pick best configuration
"""

import re
from typing import Dict, List, Optional, Tuple

from loguru import logger

from app.ingestion.layout.page_layout_builder import TextSpan


def assemble_triplet_robust(
    code_span: TextSpan,
    all_spans: List[TextSpan],
    grammar: Dict,
) -> Optional[Dict]:
    """
    Assemble vertical triplet robust to extraction ordering errors

    Args:
        code_span: CODE span (anchor)
        all_spans: All valid spans
        grammar: Grammar config with regexes

    Returns:
        Dict with triplet info if found, None otherwise
    """
    code_bbox = code_span.bbox
    code_x_center = (code_bbox[0] + code_bbox[2]) / 2
    code_y_center = (code_bbox[1] + code_bbox[3]) / 2
    code_font = code_span.font_size

    # Compile regexes
    area_regex = re.compile(grammar["area_regex"])
    num_regex = re.compile(grammar["num_regex"])

    # Config
    x_tolerance_ratio = grammar["x_center_tolerance_ratio"]
    y_search_radius = grammar["y_gap_ratio_range"][1] * code_font  # Max gap

    # Find ALL nearby spans (AREA or NUM) regardless of y-direction
    nearby_spans = []

    for span in all_spans:
        if span.span_id == code_span.span_id:
            continue

        span_x_center = (span.bbox[0] + span.bbox[2]) / 2
        span_y_center = (span.bbox[1] + span.bbox[3]) / 2

        # Check x-alignment
        x_delta = abs(span_x_center - code_x_center)
        min_width = min(code_bbox[2] - code_bbox[0], span.bbox[2] - span.bbox[0])

        if x_delta > x_tolerance_ratio * min_width:
            continue  # Not x-aligned

        # Check y-proximity
        y_delta = abs(span_y_center - code_y_center)

        if y_delta > y_search_radius * 1.5:  # 1.5x buffer
            continue  # Too far

        # Check if AREA or NUM
        is_area = area_regex.match(span.text)
        is_num = num_regex.match(span.text)

        if is_area or is_num:
            nearby_spans.append(
                {
                    "span": span,
                    "is_area": is_area,
                    "is_num": is_num,
                    "y_delta": y_delta,
                    "y_center": span_y_center,
                }
            )

    if not nearby_spans:
        return None

    # Find AREA and NUM candidates
    area_candidates = [s for s in nearby_spans if s["is_area"]]
    num_candidates = [s for s in nearby_spans if s["is_num"]]

    if not num_candidates:
        return None  # NUM is required

    # Try to find valid triplet configuration
    # Strategy: Pick closest AREA (if exists) and closest NUM

    best_area = None
    if area_candidates:
        # Pick AREA with smallest y_delta
        best_area = min(area_candidates, key=lambda x: x["y_delta"])["span"]

    best_num = None
    if num_candidates:
        # Pick NUM with smallest y_delta
        best_num = min(num_candidates, key=lambda x: x["y_delta"])["span"]

    if best_num is None:
        return None

    # Compute triplet score
    triplet_score = compute_triplet_score_robust(
        best_area, code_span, best_num, grammar
    )

    pass_threshold = grammar["pass_threshold"]

    if triplet_score < pass_threshold:
        logger.debug(
            f"Triplet rejected (score {triplet_score:.1f} < {pass_threshold}): "
            f"{best_area.text if best_area else ''} {code_span.text} {best_num.text}"
        )
        return None

    logger.debug(
        f"Accepted triplet (score {triplet_score:.1f}): "
        f"{best_area.text if best_area else ''} {code_span.text} {best_num.text}"
    )

    return {
        "area_span": best_area,
        "code_span": code_span,
        "num_span": best_num,
        "score": triplet_score,
    }


def compute_triplet_score_robust(
    area_span: Optional[TextSpan],
    code_span: TextSpan,
    num_span: TextSpan,
    grammar: Dict,
) -> float:
    """
    Compute triplet score based on spatial proximity and pattern match

    Scoring factors:
    1. Triplet regex match (AREA CODE NUM pattern)
    2. X-alignment uniformity
    3. Y-spacing uniformity
    4. Font size similarity

    Args:
        area_span: AREA span (optional)
        code_span: CODE span (required)
        num_span: NUM span (required)
        grammar: Grammar config

    Returns:
        Triplet score
    """
    score_weights = grammar["score_weights"]

    # 1. Triplet regex match
    if area_span:
        tag_text = f"{area_span.text} {code_span.text} {num_span.text}"
    else:
        tag_text = f"{code_span.text} {num_span.text}"

    triplet_regex = re.compile(
        grammar.get("triplet_regex", r"^\d{2}\s+[A-Z]{2,4}\s+\d{3,5}")
    )

    if triplet_regex.match(tag_text):
        regex_score = 1.0
    else:
        regex_score = 0.5  # Partial match

    # 2. X-alignment (all should have similar x_center)
    code_x = (code_span.bbox[0] + code_span.bbox[2]) / 2
    num_x = (num_span.bbox[0] + num_span.bbox[2]) / 2

    if area_span:
        area_x = (area_span.bbox[0] + area_span.bbox[2]) / 2
        x_variance = max(abs(area_x - code_x), abs(code_x - num_x), abs(num_x - area_x))
    else:
        x_variance = abs(code_x - num_x)

    # Normalize by width
    avg_width = (
        code_span.bbox[2] - code_span.bbox[0] + num_span.bbox[2] - num_span.bbox[0]
    ) / 2
    x_align_score = max(0, 1.0 - x_variance / (avg_width * 0.5))

    # 3. Y-spacing uniformity (gaps should be similar)
    code_y = (code_span.bbox[1] + code_span.bbox[3]) / 2
    num_y = (num_span.bbox[1] + num_span.bbox[3]) / 2

    if area_span:
        area_y = (area_span.bbox[1] + area_span.bbox[3]) / 2

        # Sort by y (to handle ordering errors!)
        y_values = sorted([area_y, code_y, num_y])
        gap1 = y_values[1] - y_values[0]
        gap2 = y_values[2] - y_values[1]

        gap_ratio = min(gap1, gap2) / max(gap1, gap2) if max(gap1, gap2) > 0 else 1.0
        y_uniform_score = gap_ratio
    else:
        y_uniform_score = 1.0  # No gap to check

    # 4. Font similarity
    code_font = code_span.font_size
    num_font = num_span.font_size

    font_delta = abs(code_font - num_font)
    font_threshold = grammar["font_size_delta_pt"]

    font_score = max(0, 1.0 - font_delta / font_threshold)

    # Weighted sum
    total_score = (
        score_weights["triplet_regex"] * regex_score
        + score_weights["x_align"] * x_align_score
        + score_weights["y_uniform"] * y_uniform_score
        + score_weights["font_sim"] * font_score
    )

    return total_score
