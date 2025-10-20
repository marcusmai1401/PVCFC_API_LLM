"""
Span Merger - Concatenate fragmented text spans (e.g., digits split by PyMuPDF)

Problem:
PyMuPDF sometimes extracts "2049" as four separate spans: "2", "0", "4", "9"

Solution:
Merge horizontally adjacent digit-only spans into single NUM tokens
"""

from typing import List

from loguru import logger

from app.ingestion.layout.page_layout_builder import TextSpan


def merge_adjacent_digits(
    spans: List[TextSpan], max_gap_ratio: float = 0.3
) -> List[TextSpan]:
    """
    Merge horizontally adjacent digit-only spans into complete numbers

    Args:
        spans: Input spans
        max_gap_ratio: Max horizontal gap as ratio of avg char width

    Returns:
        Merged spans (some replaced with concatenated versions)
    """
    if not spans:
        return []

    # Sort by y, then x (reading order)
    sorted_spans = sorted(spans, key=lambda s: ((s.bbox[1] + s.bbox[3]) / 2, s.bbox[0]))

    merged = []
    skip_ids = set()

    i = 0
    while i < len(sorted_spans):
        span = sorted_spans[i]

        if span.span_id in skip_ids:
            i += 1
            continue

        # Check if this is a digit-only span
        if not span.text.isdigit():
            merged.append(span)
            i += 1
            continue

        # Try to merge with following digit spans
        merge_group = [span]
        j = i + 1

        while j < len(sorted_spans):
            next_span = sorted_spans[j]

            if next_span.span_id in skip_ids:
                j += 1
                continue

            # Must be digit-only
            if not next_span.text.isdigit():
                break

            # Check vertical alignment (same line)
            prev_y = (merge_group[-1].bbox[1] + merge_group[-1].bbox[3]) / 2
            next_y = (next_span.bbox[1] + next_span.bbox[3]) / 2

            if abs(next_y - prev_y) > 5:  # Different line
                break

            # Check horizontal proximity
            prev_x_end = merge_group[-1].bbox[2]
            next_x_start = next_span.bbox[0]
            gap = next_x_start - prev_x_end

            # Estimate char width
            prev_width = merge_group[-1].bbox[2] - merge_group[-1].bbox[0]
            char_width = prev_width / max(len(merge_group[-1].text), 1)

            if gap < 0 or gap > max_gap_ratio * char_width:
                # Too far apart or overlapping wrong
                break

            # Merge!
            merge_group.append(next_span)
            skip_ids.add(next_span.span_id)
            j += 1

        # Create merged span if group has >1 members
        if len(merge_group) > 1:
            merged_text = "".join([s.text for s in merge_group])

            # Union bbox
            x0 = min(s.bbox[0] for s in merge_group)
            y0 = min(s.bbox[1] for s in merge_group)
            x1 = max(s.bbox[2] for s in merge_group)
            y1 = max(s.bbox[3] for s in merge_group)

            # Create new merged span
            merged_span = TextSpan(
                span_id=span.span_id,  # Keep first ID
                text=merged_text,
                bbox=[x0, y0, x1, y1],
                font_size=span.font_size,
                rotation_deg=span.rotation_deg,
            )

            merged.append(merged_span)
            logger.debug(
                f"Merged digits: {' + '.join(s.text for s in merge_group)} → '{merged_text}'"
            )
        else:
            # Single digit, keep as-is
            merged.append(span)

        i = j if j > i + 1 else i + 1

    logger.debug(f"Span merging: {len(spans)} → {len(merged)} spans")
    return merged
