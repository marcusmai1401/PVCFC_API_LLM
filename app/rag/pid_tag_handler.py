"""
P&ID Tag Location Handler

Special handling for queries asking about tag locations in P&ID diagrams.
Bypasses LLM generation to return direct answers from retrieval results.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from loguru import logger


@dataclass
class TagLocationQuery:
    """Detected tag location query"""

    is_tag_query: bool
    tag_name: Optional[str] = None
    query_type: str = "unknown"  # "location", "info", "unknown"


class PIDTagHandler:
    """Handler for P&ID tag location queries"""

    # Common P&ID tag patterns
    TAG_PATTERNS = [
        r"\b(\d{2}\s+[A-Z]{2,6}\s+\d{4}[A-Z]?)\b",  # 04 ZLH 2038A
        r"\b([A-Z]{2,6}-\d{4}[A-Z]?)\b",  # ZLH-2038A
        r"\b(\d{2}-[A-Z]{2,6}-\d{4}[A-Z]?)\b",  # 04-ZLH-2038A
    ]

    # Query patterns that indicate tag location questions
    LOCATION_PATTERNS = [
        r"(?:tag|instrument)\s+(.+?)\s+(?:nằm|ở|xuất hiện|có trong|tìm thấy|located|found|in)\s+(?:trang|page)",
        r"(?:trang|page)\s+(?:nào|what|which).*?(?:tag|instrument)\s+(.+?)[\?\.。]",
        r"(.+?)\s+(?:ở|nằm|located|found in)\s+(?:trang|page)\s+(?:nào|what|which)",
        r"(?:cho|tell|show).*?(?:tag|instrument)\s+(.+?)\s+(?:xuất hiện|appears|located)",
    ]

    def detect_tag_query(self, query: str) -> TagLocationQuery:
        """
        Detect if query is asking about tag location

        Args:
            query: User query string

        Returns:
            TagLocationQuery with detection results
        """
        query_lower = query.lower()

        # Check if query mentions tags/instruments and location/page
        mentions_tag = any(
            word in query_lower for word in ["tag", "instrument", "thiết bị"]
        )
        mentions_location = any(
            word in query_lower
            for word in ["trang", "page", "nằm", "ở", "xuất hiện", "located", "found"]
        )

        if not (mentions_tag and mentions_location):
            return TagLocationQuery(is_tag_query=False)

        # Try to extract tag name from query
        tag_name = self.extract_tag_name(query)

        if tag_name:
            logger.info(f"Detected tag location query for: {tag_name}")
            return TagLocationQuery(
                is_tag_query=True, tag_name=tag_name, query_type="location"
            )

        return TagLocationQuery(is_tag_query=False)

    def extract_tag_name(self, query: str) -> Optional[str]:
        """
        Extract tag name from query

        Args:
            query: User query string

        Returns:
            Tag name if found, None otherwise
        """
        # Try each tag pattern
        for pattern in self.TAG_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                # Return first match, normalized
                tag = matches[0].strip()
                logger.debug(f"Extracted tag: {tag} using pattern: {pattern}")
                return tag

        # Try location patterns to extract tag from context
        for pattern in self.LOCATION_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                # Extract potential tag from matched group
                potential_tag = matches[0].strip()
                # Verify it looks like a tag
                for tag_pattern in self.TAG_PATTERNS:
                    if re.search(tag_pattern, potential_tag, re.IGNORECASE):
                        logger.debug(f"Extracted tag from context: {potential_tag}")
                        return potential_tag

        return None

    def create_tag_location_answer(
        self, tag_name: str, retrieval_results: List, language: str = "vi"
    ) -> Tuple[str, List]:
        """
        Create direct answer for tag location query

        Args:
            tag_name: Tag name to search for
            retrieval_results: List of retrieval results
            language: Response language

        Returns:
            Tuple of (answer_text, citations)
        """
        if not retrieval_results:
            if language == "vi":
                return (
                    f"Không tìm thấy thông tin về tag {tag_name} trong cơ sở dữ liệu.",
                    [],
                )
            else:
                return (f"Tag {tag_name} was not found in the database.", [])

        # Find results that actually contain the tag
        matching_results = []
        for result in retrieval_results[:10]:  # Check top 10
            text = result.text if hasattr(result, "text") else result.get("text", "")
            # Normalize tag for comparison (remove spaces, hyphens)
            tag_normalized = re.sub(r"[\s\-]", "", tag_name.upper())
            text_normalized = re.sub(r"[\s\-]", "", text.upper())

            if tag_normalized in text_normalized:
                matching_results.append(result)

        if not matching_results:
            # Tag not found in text, but retrieval returned results
            # Use top result as best guess

            # Get document name from first result
            doc_name = self._extract_doc_name(retrieval_results[0])

            if language == "vi":
                answer = f"Tag {tag_name} có thể xuất hiện ở [Doc 1, p.{retrieval_results[0].page}]"
                if doc_name:
                    answer += f" của tài liệu **{doc_name}**"
                answer += ".\n\n"
                answer += (
                    f"Lưu ý: Tag không xuất hiện rõ ràng trong nội dung văn bản, "
                    f"có thể nằm trong diagram hoặc bảng phức tạp."
                )
            else:
                answer = f"Tag {tag_name} may appear on [Doc 1, p.{retrieval_results[0].page}]"
                if doc_name:
                    answer += f" of document **{doc_name}**"
                answer += ".\n\n"
                answer += (
                    f"Note: Tag is not clearly visible in text content, may be in "
                    f"diagrams or complex tables."
                )

            citations = retrieval_results[:3]
        else:
            # Tag found in text
            # Group by page and get max score per page
            page_scores = {}
            for r in matching_results:
                if hasattr(r, "page") and r.page is not None:
                    score = r.score if hasattr(r, "score") else 0.0
                    if r.page not in page_scores or score > page_scores[r.page]:
                        page_scores[r.page] = score

            # Sort pages by score (highest first)
            sorted_pages = sorted(page_scores.items(), key=lambda x: x[1], reverse=True)

            # Always keep top 1 page (best match)
            pages = [sorted_pages[0][0]] if sorted_pages else []

            # Consider adding 2nd page only if score is close to top 1
            if len(sorted_pages) > 1:
                top_score = sorted_pages[0][1]
                second_score = sorted_pages[1][1]

                # Add 2nd page if its score is at least 80% of top score
                # This ensures we only show multiple pages when confidence is similar
                if second_score >= top_score * 0.8:
                    pages.append(sorted_pages[1][0])

            pages.sort()

            # Get document name from first matching result
            doc_name = self._extract_doc_name(matching_results[0])

            if language == "vi":
                if len(pages) == 1:
                    answer = f"Tag {tag_name} xuất hiện ở [Doc 1, p.{pages[0]}]"
                    if doc_name:
                        answer += f" của tài liệu **{doc_name}**"
                    answer += "."
                else:
                    # Multiple pages: check if consecutive
                    # If consecutive and close (e.g. 5,6,7), use pp.5-7
                    # Otherwise, list them: [Doc 1, p.5], [Doc 1, p.7]
                    if len(pages) == 2 and pages[1] - pages[0] == 1:
                        # Two consecutive pages
                        answer = f"Tag {tag_name} xuất hiện ở [Doc 1, pp.{pages[0]}-{pages[1]}]"
                    elif len(pages) <= 3 or (pages[-1] - pages[0] > len(pages)):
                        # Non-consecutive or few pages: list individually
                        page_refs = ", ".join(
                            [f"[Doc 1, p.{p}]" for p in pages[:3]]
                        )  # Max 3
                        answer = f"Tag {tag_name} xuất hiện ở {page_refs}"
                    else:
                        # Many consecutive pages: use range
                        answer = f"Tag {tag_name} xuất hiện ở [Doc 1, pp.{pages[0]}-{pages[-1]}]"

                    if doc_name:
                        answer += f" của tài liệu **{doc_name}**"
                    answer += "."
            else:
                if len(pages) == 1:
                    answer = f"Tag {tag_name} appears on [Doc 1, p.{pages[0]}]"
                    if doc_name:
                        answer += f" of document **{doc_name}**"
                    answer += "."
                else:
                    # Multiple pages: check if consecutive
                    if len(pages) == 2 and pages[1] - pages[0] == 1:
                        # Two consecutive pages
                        answer = f"Tag {tag_name} appears on [Doc 1, pp.{pages[0]}-{pages[1]}]"
                    elif len(pages) <= 3 or (pages[-1] - pages[0] > len(pages)):
                        # Non-consecutive or few pages: list individually
                        page_refs = ", ".join(
                            [f"[Doc 1, p.{p}]" for p in pages[:3]]
                        )  # Max 3
                        answer = f"Tag {tag_name} appears on {page_refs}"
                    else:
                        # Many consecutive pages: use range
                        answer = f"Tag {tag_name} appears on [Doc 1, pp.{pages[0]}-{pages[-1]}]"

                    if doc_name:
                        answer += f" of document **{doc_name}**"
                    answer += "."

            citations = matching_results[:5]  # Return up to 5 citations

        logger.info(
            f"Generated tag location answer for {tag_name}: {len(citations)} citations"
        )
        return answer, citations

    def _extract_doc_name(self, result) -> Optional[str]:
        """
        Extract a human-readable document name from a retrieval result.
        Preference order: metadata.doc_name -> metadata.title -> file_name (no ext) -> pdf_path (stem)
        """
        try:
            # Get metadata dict from RetrievalResult or plain dict
            if hasattr(result, "metadata"):
                metadata = result.metadata or {}
            elif isinstance(result, dict):
                metadata = result.get("metadata", {}) or {}
            else:
                metadata = {}

            # 1) Direct fields
            name = metadata.get("doc_name") or metadata.get("title")
            if name:
                return str(name).strip()

            # 2) file_name without extension
            file_name = metadata.get("file_name")
            if file_name:
                base = str(file_name).split("/")[-1].split("\\")[-1]
                base = re.sub(r"\.pdf$", "", base, flags=re.IGNORECASE)
                if base:
                    return base.strip()

            # 3) pdf_path stem
            pdf_path = metadata.get("pdf_path")
            if pdf_path:
                base = str(pdf_path).split("/")[-1].split("\\")[-1]
                base = re.sub(r"\.pdf$", "", base, flags=re.IGNORECASE)
                if base:
                    return base.strip()

            return None
        except Exception as e:
            logger.debug(f"_extract_doc_name failed: {e}")
            return None

    def should_use_tag_handler(self, query: str, filters: dict = None) -> bool:
        """
        Determine if tag handler should be used

        Args:
            query: User query
            filters: Query filters

        Returns:
            True if tag handler should be used
        """
        # Check if query is about tags
        detection = self.detect_tag_query(query)
        if not detection.is_tag_query:
            return False

        # Check if filter includes P&ID documents
        if filters:
            doc_categories = filters.get("doc_category", [])
            if "pid" in doc_categories or not doc_categories:
                return True

        return True


# Global instance
_tag_handler = None


def get_tag_handler() -> PIDTagHandler:
    """Get global tag handler instance"""
    global _tag_handler
    if _tag_handler is None:
        _tag_handler = PIDTagHandler()
    return _tag_handler
