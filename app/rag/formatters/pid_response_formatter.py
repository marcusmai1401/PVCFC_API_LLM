"""
P&ID Response Formatter
Formats search results for P&ID tag queries with multi-prefix handling
"""

from typing import Dict, List, Optional

from loguru import logger


def format_pid_search_response(
    query: str, grouped_results: Dict, answer: Optional[str] = None
) -> Dict:
    """
    Format response for P&ID tag searches with multi-prefix handling

    Args:
        query: Original query string
        grouped_results: Grouped results from OpenSearchTagsRetriever
        answer: Optional LLM-generated answer

    Returns:
        Formatted response dict with:
        - Clear grouping by (unit, suffix)
        - Warnings for ambiguous queries
        - Co-location indicators
        - Page references
    """
    response = {
        "query": query,
        "total_tags": grouped_results.get("total_tags", 0),
        "has_ambiguity": grouped_results.get("has_ambiguity", False),
    }

    if answer:
        response["answer"] = answer

    # Format groups
    response["results"] = []
    for group in grouped_results.get("groups", []):
        result_group = {
            "unit": group.get("unit"),
            "suffix": group.get("suffix"),
            "prefixes": group.get("prefixes", []),
            "pages": group.get("pages", []),
            "co_located": group.get("co_located", False),
            "tags": [],
        }

        # Format individual tags
        for tag_dict in group.get("tags", []):
            tag_info = {
                "tag": tag_dict.get("text", ""),
                "page": tag_dict.get("page"),
                "doc_id": tag_dict.get("doc_id"),
                "confidence": tag_dict.get("confidence", 1.0),
            }

            # Add bbox if available
            if tag_dict.get("bbox"):
                tag_info["bbox"] = tag_dict["bbox"]

            # Add crop path if available
            if tag_dict.get("crop_path"):
                tag_info["crop_path"] = tag_dict["crop_path"]

            # Add component breakdown
            tag_info["components"] = {
                "unit": tag_dict.get("unit"),
                "prefix": tag_dict.get("prefix"),
                "suffix": tag_dict.get("suffix"),
                "variant": tag_dict.get("variant"),
                "annotation": tag_dict.get("annotation"),
            }

            result_group["tags"].append(tag_info)

        # Add warning if present
        if group.get("warning"):
            result_group["warning"] = group["warning"]

        response["results"].append(result_group)

    # Add clarification message for ambiguous queries
    if grouped_results.get("has_ambiguity"):
        response["clarification"] = (
            "Multiple instrument types found with this suffix. "
            "Refine your query with PREFIX or UNIT for more specific results."
        )

        # List all prefixes found
        all_prefixes = []
        for group in grouped_results.get("groups", []):
            all_prefixes.extend(group.get("prefixes", []))
        unique_prefixes = sorted(set(all_prefixes))

        response["found_prefixes"] = unique_prefixes
        response["suggestion"] = (
            f"Try queries like: '{unique_prefixes[0]} {query}' "
            f"or add UNIT like: '04 {query}'"
            if unique_prefixes
            else ""
        )

    logger.debug(
        f"Formatted PID response: {response.get('total_tags')} tags, ambiguity={response.get('has_ambiguity')}"
    )

    return response


def format_component_search_response(
    query: str, components: Dict, results: List[Dict], answer: Optional[str] = None
) -> Dict:
    """
    Format response for component-based search

    Args:
        query: Original query
        components: Detected components {unit?, prefix?, suffix?}
        results: Search results
        answer: Optional LLM answer

    Returns:
        Formatted response
    """
    response = {
        "query": query,
        "query_type": "component_search",
        "components_used": components,
        "total_results": len(results),
    }

    if answer:
        response["answer"] = answer

    # Format results
    response["tags"] = []
    for result in results:
        tag_info = {
            "tag": result.get("text", ""),
            "page": result.get("page"),
            "doc_id": result.get("doc_id"),
            "bbox": result.get("bbox"),
            "crop_path": result.get("crop_path"),
            "confidence": result.get("confidence", 1.0),
            "components": {
                "unit": result.get("unit"),
                "prefix": result.get("prefix"),
                "suffix": result.get("suffix"),
                "variant": result.get("variant"),
                "annotation": result.get("annotation"),
            },
        }
        response["tags"].append(tag_info)

    # Add informational message
    component_desc = []
    if components.get("unit"):
        component_desc.append(f"UNIT={components['unit']}")
    if components.get("prefix"):
        component_desc.append(f"PREFIX={components['prefix']}")
    if components.get("suffix"):
        component_desc.append(f"SUFFIX={components['suffix']}")
    if components.get("variant"):
        component_desc.append(f"VARIANT={components['variant']}")

    response["search_description"] = (
        f"Searching for tags with: {', '.join(component_desc)}"
        if component_desc
        else "No valid components detected"
    )

    return response


__all__ = ["format_pid_search_response", "format_component_search_response"]
