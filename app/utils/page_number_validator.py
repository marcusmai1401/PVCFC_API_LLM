"""
Page Number Validation and Normalization

BUG-009 FIX: Enforces consistent 1-indexed page numbering throughout the system.

PROBLEM:
- OpenSearch may return 0-indexed pages (page=0 for first page)
- PyMuPDF uses 0-indexed internally but displays 1-indexed
- Tags extraction may use either convention
- Citations show wrong page numbers to users

SOLUTION:
- All external APIs, citations, and user-facing displays use 1-indexed
- Internal processing can use 0-indexed but must convert at boundaries
- Validation catches 0-indexed pages and converts them
"""

from typing import Any, Dict, Optional

from loguru import logger


def validate_and_normalize_page(
    page: Optional[int],
    source: str = "unknown",
    doc_id: Optional[str] = None,
    allow_zero: bool = False,
) -> int:
    """
    Validate and normalize page number to 1-indexed.

    Args:
        page: Page number (may be 0-indexed, 1-indexed, or None)
        source: Source of the page number (for logging)
        doc_id: Document ID (for logging)
        allow_zero: If True, page=0 is valid (for special cases)

    Returns:
        1-indexed page number (minimum 1)

    Examples:
        >>> validate_and_normalize_page(0, "opensearch")
        # Logs warning, returns 1
        >>> validate_and_normalize_page(5, "citation")
        # Returns 5
        >>> validate_and_normalize_page(None, "fallback")
        # Logs warning, returns 1
    """
    # Handle None
    if page is None:
        logger.warning(
            f"[BUG-009] Page is None from {source} (doc_id={doc_id}). "
            f"Defaulting to page 1."
        )
        return 1

    # Handle negative pages
    if page < 0:
        logger.error(
            f"[BUG-009] Invalid negative page {page} from {source} (doc_id={doc_id}). "
            f"Defaulting to page 1."
        )
        return 1

    # Handle 0-indexed (suspicious)
    if page == 0:
        if allow_zero:
            return 0  # Special case (e.g., internal processing)
        else:
            logger.warning(
                f"[BUG-009] 0-indexed page detected from {source} (doc_id={doc_id}). "
                f"Converting to 1-indexed (page=1). "
                f"Source may be using 0-based indexing."
            )
            return 1

    # Valid 1-indexed page
    return page


def normalize_page_in_metadata(
    metadata: Dict[str, Any],
    source: str = "unknown",
) -> Dict[str, Any]:
    """
    Normalize page number in metadata dict (in-place).

    Args:
        metadata: Metadata dict with optional 'page' field
        source: Source of the metadata (for logging)

    Returns:
        Modified metadata dict (same object, modified in-place)
    """
    if "page" in metadata:
        original_page = metadata["page"]
        normalized_page = validate_and_normalize_page(
            original_page,
            source=source,
            doc_id=metadata.get("doc_id"),
        )
        if normalized_page != original_page:
            logger.debug(
                f"[BUG-009] Normalized page in metadata: {original_page} → {normalized_page} "
                f"(source={source}, doc_id={metadata.get('doc_id')})"
            )
        metadata["page"] = normalized_page

    return metadata


def enforce_1_indexed_pages_in_results(
    results: list, source: str = "retrieval"
) -> list:
    """
    Enforce 1-indexed pages in a list of retrieval results.

    Args:
        results: List of RetrievalResult or dict objects
        source: Source of the results (for logging)

    Returns:
        Same list (modified in-place)
    """
    for result in results:
        # Handle RetrievalResult objects
        if hasattr(result, "page"):
            original_page = result.page
            result.page = validate_and_normalize_page(
                original_page,
                source=source,
                doc_id=getattr(result, "doc_id", None),
            )
            # Also update metadata if present
            if hasattr(result, "metadata") and result.metadata:
                result.metadata["page"] = result.page

        # Handle dict results
        elif isinstance(result, dict):
            if "page" in result:
                result["page"] = validate_and_normalize_page(
                    result["page"],
                    source=source,
                    doc_id=result.get("doc_id"),
                )
            # Also check metadata
            if "metadata" in result and isinstance(result["metadata"], dict):
                normalize_page_in_metadata(result["metadata"], source=source)

    return results


def get_display_page_range(start_page: int, end_page: int) -> str:
    """
    Format page range for display to users.

    Args:
        start_page: Start page (1-indexed)
        end_page: End page (1-indexed)

    Returns:
        Formatted string (e.g., "p.5", "pp.5-7")

    Examples:
        >>> get_display_page_range(5, 5)
        "p.5"
        >>> get_display_page_range(5, 7)
        "pp.5-7"
    """
    # Normalize both pages
    start = max(1, start_page)
    end = max(1, end_page)

    if start == end:
        return f"p.{start}"
    else:
        return f"pp.{start}-{end}"
