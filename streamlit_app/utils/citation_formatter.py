"""
IEEE-style Citation Formatter Utility
=====================================
Chuyển đổi [Doc X, p.Y] -> [n] và tạo reference list theo chuẩn IEEE.

Usage:
    from streamlit_app.utils.citation_formatter import (
        convert_to_ieee_style,
        render_ieee_references
    )

    converted_text, ieee_refs = convert_to_ieee_style(answer, citations, doc_map)
    refs_html = render_ieee_references(ieee_refs, language="vi")
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional dependency for page validation
try:
    import PyPDF2

    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


@lru_cache(maxsize=1024)
def get_pdf_page_count(pdf_path: str) -> int:
    """Get total pages in a PDF file with caching."""
    if not HAS_PYPDF2:
        return 99999  # Skip validation if PyPDF2 not available
    try:
        if not Path(pdf_path).exists():
            return 99999
        with open(pdf_path, "rb") as f:
            # PyPDF2 3.0.0+ uses PdfReader
            reader = PyPDF2.PdfReader(f)
            return len(reader.pages)
    except Exception:
        return 99999


def convert_to_ieee_style(
    answer_text: str, citations: List[Dict], doc_number_map: Optional[Dict] = None
) -> Tuple[str, List[Dict]]:
    """
    Convert inline [Doc X, p.Y] citations to IEEE-style [n] format.

    Args:
        answer_text: The answer text containing [Doc X, p.Y] style citations
        citations: List of citation dicts from the API response
        doc_number_map: Optional mapping from doc_number to {doc_id, pdf_path, file_name}

    Returns:
        Tuple of (converted_text, ieee_citation_list)
        - converted_text: Answer with [1], [2], etc. instead of [Doc X, p.Y]
        - ieee_citation_list: List of unique citations in order of first appearance
          Each entry: {"ref_num": int, "doc_id": str, "file_name": str, "pages": [int], "pdf_path": str}
    """
    if not answer_text:
        return answer_text, []

    # Normalize doc_number_map keys to strings for uniform matching
    doc_number_map_str: Dict[str, Dict] = {}
    if isinstance(doc_number_map, dict):
        for k, v in doc_number_map.items():
            doc_number_map_str[str(k)] = v

    # Build mapping from citations list
    # doc_id -> {file_name, pages: set(), pdf_path}
    doc_id_info: Dict[str, Dict[str, Any]] = {}

    # First, populate from citations list
    for cit in citations:
        doc_id = cit.get("doc_id", "Unknown")
        page = cit.get("page")
        pdf_path = cit.get("pdf_path", "")

        # Try to get file_name from pdf_path
        file_name = doc_id
        if pdf_path:
            try:
                file_name = Path(pdf_path).name
            except Exception:
                pass

        if doc_id not in doc_id_info:
            doc_id_info[doc_id] = {
                "file_name": file_name,
                "pages": set(),
                "pdf_path": pdf_path,
            }

        if page:
            try:
                # Handle page ranges like "5-7"
                if isinstance(page, str) and "-" in page:
                    start, end = page.split("-", 1)
                    for p in range(int(start), int(end) + 1):
                        doc_id_info[doc_id]["pages"].add(int(p))
                else:
                    doc_id_info[doc_id]["pages"].add(int(page))
            except (ValueError, TypeError):
                pass

        # Update file_name and pdf_path if better info available
        if pdf_path and not doc_id_info[doc_id].get("pdf_path"):
            doc_id_info[doc_id]["pdf_path"] = pdf_path
            try:
                doc_id_info[doc_id]["file_name"] = Path(pdf_path).name
            except Exception:
                pass

    # Also enrich from doc_number_map
    for doc_num, info in doc_number_map_str.items():
        doc_id = info.get("doc_id", "")
        if doc_id and doc_id in doc_id_info:
            # Update with better info from doc_number_map
            if info.get("pdf_path") and not doc_id_info[doc_id].get("pdf_path"):
                doc_id_info[doc_id]["pdf_path"] = info["pdf_path"]
            if info.get("file_name") and info["file_name"] != "Unknown":
                doc_id_info[doc_id]["file_name"] = info["file_name"]

    # Track unique citations in order of first appearance
    # Maps doc_id -> IEEE ref number (1-based)
    doc_id_to_ieee: Dict[str, int] = {}
    ieee_citation_list: List[Dict] = []

    # Pattern to match [Doc X, p.Y] or [Doc X, pp. Y-Z] or [Doc X]
    # Also handles multiple: [Doc 1, p.5; Doc 2, p.10]
    pattern = re.compile(
        r"\[Doc\s*(\d+)(?:,\s*(?:pp?\.)?\s*(\d+)(?:[-–](\d+))?)?(?:;\s*Doc\s*(\d+)(?:,\s*(?:pp?\.)?\s*(\d+)(?:[-–](\d+))?)?)?\]",
        re.IGNORECASE,
    )

    def get_doc_id_for_doc_num(doc_num: str) -> Optional[str]:
        """Get doc_id from doc_number_map"""
        if doc_num in doc_number_map_str:
            return doc_number_map_str[doc_num].get("doc_id")
        return None

    def ensure_ieee_entry(doc_id: str, page: Optional[int] = None) -> int:
        """Ensure doc_id has an IEEE entry and return its ref number"""
        if doc_id not in doc_id_to_ieee:
            ref_num = len(ieee_citation_list) + 1
            doc_id_to_ieee[doc_id] = ref_num

            info = doc_id_info.get(doc_id, {})
            pdf_path = info.get("pdf_path", "")

            # Validate pages against PDF length if possible
            valid_pages = set()
            raw_pages = info.get("pages", set())

            max_pages = 99999
            if pdf_path:
                max_pages = get_pdf_page_count(pdf_path)

            for p in raw_pages:
                if 1 <= p <= max_pages:
                    valid_pages.add(p)

            ieee_citation_list.append(
                {
                    "ref_num": ref_num,
                    "doc_id": doc_id,
                    "file_name": info.get("file_name", doc_id),
                    "pages": sorted(list(valid_pages)),
                    "pdf_path": pdf_path,
                }
            )

        # Add page to existing entry if provided and valid
        if page is not None:
            ref_num = doc_id_to_ieee[doc_id]
            entry = ieee_citation_list[ref_num - 1]

            # Validate new page
            pdf_path = entry.get("pdf_path", "")
            max_pages = 99999
            if pdf_path:
                max_pages = get_pdf_page_count(pdf_path)

            if 1 <= page <= max_pages:
                if page not in entry["pages"]:
                    entry["pages"].append(page)
                    entry["pages"] = sorted(entry["pages"])

        return doc_id_to_ieee[doc_id]

    def replace_citation(match: re.Match) -> str:
        """Replace a citation match with IEEE format"""
        full_match = match.group(0)

        # Extract all Doc X patterns from the matched text
        doc_pattern = r"Doc\s*(\d+)(?:,\s*(?:pp?\.)?\s*(\d+))?"
        doc_matches = list(re.finditer(doc_pattern, full_match, re.IGNORECASE))

        ieee_refs = []

        for doc_match in doc_matches:
            doc_num = str(doc_match.group(1))
            page_str = doc_match.group(2)
            page = int(page_str) if page_str else None

            # Get doc_id for this doc_num
            doc_id = get_doc_id_for_doc_num(doc_num)

            if doc_id:
                ieee_num = ensure_ieee_entry(doc_id, page)
                if str(ieee_num) not in ieee_refs:
                    ieee_refs.append(str(ieee_num))
            else:
                # Fallback: try to find in citations by index
                idx = int(doc_num) - 1
                if 0 <= idx < len(citations):
                    doc_id = citations[idx].get("doc_id", f"doc_{doc_num}")
                    ieee_num = ensure_ieee_entry(doc_id, page)
                    if str(ieee_num) not in ieee_refs:
                        ieee_refs.append(str(ieee_num))
                else:
                    # Last resort: use doc_num as-is
                    if doc_num not in ieee_refs:
                        ieee_refs.append(doc_num)

        # Return IEEE-style references
        if len(ieee_refs) == 1:
            return f"[{ieee_refs[0]}]"
        else:
            # Multiple citations: [1][2] or [1, 2]
            return "".join([f"[{ref}]" for ref in ieee_refs])

    # Replace all citation patterns
    converted_text = pattern.sub(replace_citation, answer_text)

    # Also handle simple [X] patterns that might be footnote-style
    # but avoid replacing if it's already an IEEE ref
    simple_pattern = re.compile(r"\[(\d+)\](?!\w)")

    def replace_simple_citation(match: re.Match) -> str:
        num = match.group(1)
        # Check if this number corresponds to an existing doc_num
        if num in doc_number_map_str:
            doc_id = doc_number_map_str[num].get("doc_id")
            if doc_id:
                ieee_num = ensure_ieee_entry(doc_id)
                return f"[{ieee_num}]"
        return match.group(0)  # Keep as-is

    # Only apply if we haven't already converted
    if "[Doc" in answer_text.lower():
        converted_text = simple_pattern.sub(replace_simple_citation, converted_text)

    # Remove duplicate consecutive citations like [1][1] -> [1]
    dedupe_pattern = r"\[(\d+)\]\[(\1)\]"
    while re.search(dedupe_pattern, converted_text):
        converted_text = re.sub(dedupe_pattern, r"[\1]", converted_text)

    return converted_text, ieee_citation_list


def render_ieee_references(ieee_citation_list: List[Dict], language: str = "vi") -> str:
    """
    Render IEEE reference list as HTML.

    Args:
        ieee_citation_list: List from convert_to_ieee_style()
        language: "vi" for Vietnamese, "en" for English

    Returns:
        HTML string for rendering in Streamlit

    Output format (vi):
        Nguồn:
        [1] 07087-CP22-K06101 Lubricant List.pdf, trang 131
        [2] Operation Manual.pdf, trang 45, 67
    """
    if not ieee_citation_list:
        return ""

    header = "Nguồn:" if language == "vi" else "References:"
    page_label = "trang" if language == "vi" else "p."

    lines = [f"<div style='margin-top: 1rem;'><strong>{header}</strong></div>"]

    for ref in ieee_citation_list:
        ref_num = ref.get("ref_num", "?")
        file_name = ref.get("file_name", "Unknown")
        pages = ref.get("pages", [])

        # Format pages
        if pages:
            # Sort and format pages
            sorted_pages = sorted(set(pages))
            pages_str = ", ".join(str(p) for p in sorted_pages)
            line = f"<div style='margin: 4px 0; color: var(--color-text-secondary);'><strong>[{ref_num}]</strong> {file_name}, {page_label} {pages_str}</div>"
        else:
            line = f"<div style='margin: 4px 0; color: var(--color-text-secondary);'><strong>[{ref_num}]</strong> {file_name}</div>"

        lines.append(line)

    return "\n".join(lines)


def render_ieee_references_markdown(
    ieee_citation_list: List[Dict], language: str = "vi"
) -> str:
    """
    Render IEEE reference list as Markdown (alternative to HTML).

    Args:
        ieee_citation_list: List from convert_to_ieee_style()
        language: "vi" for Vietnamese, "en" for English

    Returns:
        Markdown string for rendering
    """
    if not ieee_citation_list:
        return ""

    header = "**Nguồn:**" if language == "vi" else "**References:**"
    page_label = "trang" if language == "vi" else "p."

    lines = [header]

    for ref in ieee_citation_list:
        ref_num = ref.get("ref_num", "?")
        file_name = ref.get("file_name", "Unknown")
        pages = ref.get("pages", [])

        if pages:
            sorted_pages = sorted(set(pages))
            pages_str = ", ".join(str(p) for p in sorted_pages)
            lines.append(f"**[{ref_num}]** {file_name}, {page_label} {pages_str}")
        else:
            lines.append(f"**[{ref_num}]** {file_name}")

    return "  \n".join(lines)  # Double space for line breaks in Markdown
