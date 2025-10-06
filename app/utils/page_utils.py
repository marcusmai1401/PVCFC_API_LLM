"""
Page metadata utilities for consistent page number handling across indices.
Ensures all chunks have a valid 'page' field for citations and page jump.
"""
from typing import Any, Dict, List, Optional, Union

from loguru import logger


def extract_page_number(metadata: Dict[str, Any]) -> int:
    """
    Extract page number from chunk metadata with multiple fallback strategies.

    Priority order:
    1. Direct 'page' field
    2. 'page_start' field
    3. First element of 'page_nums' list
    4. 'page_num' field (alternative naming)
    5. Try to parse from 'chunk_id' if it contains page info
    6. Default to 1

    Args:
        metadata: Chunk metadata dictionary

    Returns:
        Page number (1-based integer)
    """
    if not metadata:
        return 1

    # Strategy 1: Direct page field
    if "page" in metadata:
        return validate_page_number(metadata["page"])

    # Strategy 2: page_start field (from BM25 index)
    if "page_start" in metadata:
        return validate_page_number(metadata["page_start"])

    # Strategy 3: page_nums list (from TextChunk)
    if "page_nums" in metadata:
        page_nums = metadata["page_nums"]
        if isinstance(page_nums, list) and len(page_nums) > 0:
            return validate_page_number(page_nums[0])

    # Strategy 4: page_num field (alternative naming)
    if "page_num" in metadata:
        return validate_page_number(metadata["page_num"])

    # Strategy 5: Try to extract from chunk_id
    # Example: "doc_chunk_5_page_12_abc123" -> extract 12
    if "chunk_id" in metadata:
        chunk_id = str(metadata["chunk_id"])
        import re

        page_match = re.search(r"page[_\-]?(\d+)", chunk_id, re.IGNORECASE)
        if page_match:
            try:
                page = int(page_match.group(1))
                if page > 0:
                    return page
            except (ValueError, TypeError):
                pass

    # Default: return 1 (first page)
    logger.debug(f"No page information found in metadata, defaulting to 1")
    return 1


def validate_page_number(page: Any) -> int:
    """
    Validate and normalize page number to ensure it's a positive integer.

    Args:
        page: Page value (could be int, float, str, None)

    Returns:
        Valid page number (minimum 1)
    """
    if page is None:
        return 1

    try:
        # Convert to integer
        if isinstance(page, str):
            # Try direct conversion first (handles negative strings)
            try:
                page_int = int(float(page))
                return max(1, page_int)
            except (ValueError, TypeError):
                # If that fails, remove non-numeric characters
                page = "".join(filter(str.isdigit, page))
                if not page:
                    return 1

        page_int = int(float(page))  # Handle floats like 1.0

        # Ensure positive and 1-based
        return max(1, page_int)
    except (ValueError, TypeError):
        logger.warning(f"Invalid page number: {page}, defaulting to 1")
        return 1


def normalize_page_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize metadata to ensure 'page' field exists with valid value.
    Modifies metadata in-place and returns it.

    Args:
        metadata: Chunk metadata dictionary

    Returns:
        Updated metadata with 'page' field
    """
    if metadata is None:
        metadata = {}

    # Extract page using fallback strategies
    page = extract_page_number(metadata)

    # Set the page field
    metadata["page"] = page

    # Also preserve original fields for backward compatibility
    # But ensure they're consistent
    if "page_start" in metadata and metadata["page_start"] != page:
        logger.debug(f"Normalizing page_start from {metadata['page_start']} to {page}")

    if "page_end" not in metadata and "page_start" in metadata:
        metadata["page_end"] = metadata["page_start"]

    return metadata


def extract_page_range(metadata: Dict[str, Any]) -> tuple[int, int]:
    """
    Extract page range from metadata.

    Args:
        metadata: Chunk metadata

    Returns:
        Tuple of (start_page, end_page), both 1-based
    """
    page = extract_page_number(metadata)

    # Try to get end page
    end_page = page  # Default to same as start

    if "page_end" in metadata:
        end_page = validate_page_number(metadata["page_end"])
    elif "page_nums" in metadata:
        page_nums = metadata["page_nums"]
        if isinstance(page_nums, list) and len(page_nums) > 0:
            # Use last page in list as end
            end_page = validate_page_number(page_nums[-1])

    # Ensure end >= start
    end_page = max(page, end_page)

    return page, end_page


def merge_page_ranges(ranges: List[tuple[int, int]]) -> List[tuple[int, int]]:
    """
    Merge overlapping or consecutive page ranges.

    Args:
        ranges: List of (start, end) tuples

    Returns:
        Merged list of non-overlapping ranges

    Example:
        [(1, 3), (2, 5), (7, 8), (8, 10)] -> [(1, 5), (7, 10)]
    """
    if not ranges:
        return []

    # Sort by start page
    sorted_ranges = sorted(ranges)
    merged = [sorted_ranges[0]]

    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]

        # Check if ranges overlap or are consecutive
        if start <= last_end + 1:
            # Merge ranges
            merged[-1] = (last_start, max(last_end, end))
        else:
            # Add new range
            merged.append((start, end))

    return merged


def format_page_citation(doc_id: str, page: Union[int, tuple[int, int]]) -> str:
    """
    Format a page citation for display.

    Args:
        doc_id: Document identifier
        page: Single page number or (start, end) tuple

    Returns:
        Formatted citation string

    Examples:
        "doc_id; p.5"
        "doc_id; pp.5-8"
    """
    if isinstance(page, tuple):
        start, end = page
        if start == end:
            return f"{doc_id}; p.{start}"
        else:
            return f"{doc_id}; pp.{start}-{end}"
    else:
        return f"{doc_id}; p.{page}"


def group_by_page_proximity(
    results: List[Dict[str, Any]], max_gap: int = 1
) -> List[List[Dict[str, Any]]]:
    """
    Group search results by page proximity within the same document.

    Args:
        results: List of search results with metadata
        max_gap: Maximum page gap to consider as same group

    Returns:
        List of grouped results
    """
    from collections import defaultdict

    # Group by doc_id first
    doc_groups = defaultdict(list)
    for result in results:
        doc_id = result.get("doc_id") or result.get("metadata", {}).get("doc_id")
        if doc_id:
            doc_groups[doc_id].append(result)

    # Within each doc, group by page proximity
    all_groups = []
    for doc_id, doc_results in doc_groups.items():
        # Sort by page
        doc_results.sort(key=lambda x: extract_page_number(x.get("metadata", {})))

        # Group consecutive pages
        if not doc_results:
            continue

        current_group = [doc_results[0]]
        current_page = extract_page_number(doc_results[0].get("metadata", {}))

        for result in doc_results[1:]:
            page = extract_page_number(result.get("metadata", {}))

            if page <= current_page + max_gap:
                current_group.append(result)
                current_page = page
            else:
                all_groups.append(current_group)
                current_group = [result]
                current_page = page

        if current_group:
            all_groups.append(current_group)

    return all_groups


def calculate_page_coverage(
    results: List[Dict[str, Any]], doc_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate page coverage statistics for search results.

    Args:
        results: Search results with metadata
        doc_id: Optional filter by document

    Returns:
        Dictionary with coverage statistics
    """
    pages_hit = set()
    doc_pages = defaultdict(set)

    for result in results:
        result_doc_id = result.get("doc_id") or result.get("metadata", {}).get("doc_id")

        if doc_id and result_doc_id != doc_id:
            continue

        page = extract_page_number(result.get("metadata", {}))
        pages_hit.add(page)

        if result_doc_id:
            doc_pages[result_doc_id].add(page)

    # Calculate statistics
    stats = {
        "total_pages_hit": len(pages_hit),
        "page_numbers": sorted(list(pages_hit)),
        "documents": {},
    }

    for doc, pages in doc_pages.items():
        sorted_pages = sorted(list(pages))
        stats["documents"][doc] = {
            "pages_hit": len(pages),
            "page_numbers": sorted_pages,
            "page_ranges": merge_page_ranges([(p, p) for p in sorted_pages]),
        }

    return stats


# For backward compatibility
from collections import defaultdict


def extract_page_from_content(text: str) -> Optional[int]:
    """
    Extract page number from markdown content page markers.
    Looks for patterns like <!-- Page 15 --> in the text.

    This is more reliable than metadata for chunks that span multiple pages
    or have incorrect metadata.page values.

    Args:
        text: Chunk text content (markdown)

    Returns:
        Page number if found, None otherwise
    """
    import re

    # Look for <!-- Page N --> markers
    page_markers = re.findall(r"<!-- Page (\d+) -->", text)

    if page_markers:
        # Return the first page marker found (usually the most relevant)
        try:
            return int(page_markers[0])
        except (ValueError, TypeError):
            pass

    # Also try TABLE START markers that include page info
    # Example: --- TABLE START (Page 15, Table 1: 4x9, confidence=1.00) ---
    table_markers = re.findall(r"TABLE START \(Page (\d+)", text)
    if table_markers:
        try:
            return int(table_markers[0])
        except (ValueError, TypeError):
            pass

    return None


def get_best_page_number(text: str, metadata: Dict[str, Any]) -> int:
    """
    Get the most accurate page number by prioritizing content over metadata.

    Priority:
    1. Page marker from content (<!-- Page N -->)
    2. Page from metadata (with fallback strategies)
    3. Middle of page_start/page_end range
    4. Default to 1

    Args:
        text: Chunk text content
        metadata: Chunk metadata

    Returns:
        Best estimated page number (1-based)
    """
    # Try content first (most reliable)
    page_from_content = extract_page_from_content(text)
    if page_from_content:
        return page_from_content

    # Try metadata page field
    page_from_meta = extract_page_number(metadata)

    # If metadata.page seems wrong (=1 but page_end is much larger),
    # use middle of range instead
    if metadata and page_from_meta == 1:
        page_start = metadata.get("page_start", 1)
        page_end = metadata.get("page_end", 1)
        if page_end > page_start + 5:  # Range is suspiciously large
            # Use middle of range
            return (page_start + page_end) // 2

    return page_from_meta


def get_page(metadata: Dict[str, Any]) -> int:
    """
    Simple wrapper for extract_page_number for backward compatibility.

    Args:
        metadata: Chunk metadata

    Returns:
        Page number (1-based)
    """
    return extract_page_number(metadata)
