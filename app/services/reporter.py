"""
Reporter service for generating structured reports from multiple queries.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.rag.generator import ResponseGenerator
from app.rag.retriever import HybridRetriever
from app.rag.schemas import Citation, ReportSection
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class ReporterService:
    """Service for generating structured reports."""

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        generator: Optional[ResponseGenerator] = None,
        llm_service: Optional[LLMService] = None,
        settings: Optional[Settings] = None,
    ):
        """Initialize reporter service."""
        self.settings = settings or Settings()
        self.retriever = retriever
        self.generator = generator or ResponseGenerator(settings=self.settings)
        self.llm_service = llm_service or LLMService(settings=self.settings)

    async def generate_report(
        self,
        topic: str,
        sub_queries: List[str],
        filters: Optional[Dict[str, List[str]]] = None,
        language: str = "vi",
        format: str = "markdown",
    ) -> Dict[str, Any]:
        """
        Generate a structured report from multiple sub-queries.

        Args:
            topic: Main topic for the report
            sub_queries: List of sub-queries to answer
            filters: Optional document filters
            language: Response language
            format: Output format (markdown or json)

        Returns:
            Report with sections, citations, and metadata
        """
        try:
            # Process each sub-query in parallel (with limit)
            sections = await self._process_sub_queries(sub_queries, filters, language)

            # Generate executive summary
            summary = await self._generate_summary(topic, sections, language)

            # Format report
            if format == "markdown":
                report_content = self._format_markdown_report(topic, summary, sections)
            else:
                report_content = {
                    "title": self._generate_title(topic, language),
                    "summary": summary,
                    "sections": sections,
                }

            # Collect all citations
            all_citations = []
            for section in sections:
                all_citations.extend(section.citations)

            # Deduplicate citations
            unique_citations = self._deduplicate_citations(all_citations)

            return {
                "title": self._generate_title(topic, language),
                "sections": sections,
                "summary": summary,
                "content": report_content if format == "markdown" else None,
                "total_citations": len(unique_citations),
                "format": format,
            }

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise

    async def _process_sub_queries(
        self,
        sub_queries: List[str],
        filters: Optional[Dict[str, List[str]]],
        language: str,
    ) -> List[ReportSection]:
        """Process sub-queries into report sections."""
        sections = []

        # Process queries with concurrency limit
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent queries

        async def process_query(query: str, index: int) -> ReportSection:
            async with semaphore:
                try:
                    # Retrieve context for sub-query
                    retrieval_results = await self.retriever.retrieve(
                        query=query, k=30, filters=filters
                    )

                    # Rerank if available
                    if hasattr(self.retriever, "reranker") and self.retriever.reranker:
                        reranked = await self.retriever.reranker.rerank(
                            query=query, chunks=retrieval_results["chunks"], top_k=8
                        )
                        context_chunks = reranked["chunks"]
                    else:
                        context_chunks = retrieval_results["chunks"][:8]

                    # Generate answer for sub-query
                    response = await self.generator.generate(
                        query=query,
                        context_chunks=context_chunks,
                        language=language,
                        max_tokens=300,  # Shorter for report sections
                    )

                    # Extract citations
                    citations = self._extract_citations_from_response(response)

                    # Create section
                    return ReportSection(
                        heading=self._generate_heading(query, index, language),
                        content=response.get("answer", ""),
                        citations=citations,
                        sub_query=query,
                    )

                except Exception as e:
                    logger.error(f"Failed to process sub-query '{query}': {e}")
                    return ReportSection(
                        heading=self._generate_heading(query, index, language),
                        content=f"Không thể xử lý câu hỏi này: {str(e)}"
                        if language == "vi"
                        else f"Failed to process this query: {str(e)}",
                        citations=[],
                        sub_query=query,
                    )

        # Process all queries concurrently
        tasks = [process_query(query, i) for i, query in enumerate(sub_queries)]
        sections = await asyncio.gather(*tasks)

        return sections

    async def _generate_summary(
        self, topic: str, sections: List[ReportSection], language: str
    ) -> str:
        """Generate executive summary from report sections."""
        # Combine key points from sections
        key_points = []
        for section in sections[:5]:  # Limit to first 5 sections
            if section.content:
                # Extract first sentence or key fact
                first_sentence = section.content.split(".")[0] + "."
                key_points.append(f"- {first_sentence}")

        # Generate summary prompt
        if language == "vi":
            prompt = f"""
            Tạo tóm tắt ngắn gọn (2-3 câu) cho báo cáo về: {topic}

            Các điểm chính:
            {chr(10).join(key_points)}

            Tóm tắt:
            """
        else:
            prompt = f"""
            Generate a brief summary (2-3 sentences) for a report about: {topic}

            Key points:
            {chr(10).join(key_points)}

            Summary:
            """

        try:
            # Use light model for summary
            response = await self.llm_service.complete(
                prompt=prompt, max_tokens=150, tier="light"
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return ""

    def _generate_title(self, topic: str, language: str) -> str:
        """Generate report title."""
        if language == "vi":
            return f"Báo cáo: {topic}"
        else:
            return f"Report: {topic}"

    def _generate_heading(self, query: str, index: int, language: str) -> str:
        """Generate section heading from query."""
        # Simplify query into heading
        # Remove question marks and common question words
        heading = query.replace("?", "")

        if language == "vi":
            for word in ["là gì", "như thế nào", "bao nhiêu", "khi nào"]:
                heading = heading.replace(word, "")
        else:
            for word in ["what is", "how does", "how much", "when"]:
                heading = heading.replace(word, "", 1)

        heading = heading.strip().capitalize()

        # Add section number
        return f"{index + 1}. {heading}"

    def _format_markdown_report(
        self, topic: str, summary: str, sections: List[ReportSection]
    ) -> str:
        """Format report as markdown."""
        lines = []

        # Title
        lines.append(f"# {self._generate_title(topic, 'vi')}")
        lines.append("")

        # Summary
        if summary:
            lines.append("## Tóm tắt")
            lines.append(summary)
            lines.append("")

        # Table of contents
        lines.append("## Mục lục")
        for section in sections:
            lines.append(f"- {section.heading}")
        lines.append("")

        # Sections
        for section in sections:
            lines.append(f"## {section.heading}")
            lines.append(section.content)

            # Add citations if present
            if section.citations:
                lines.append("\n**Nguồn tham khảo:**")
                for citation in section.citations:
                    cite_text = f"- Tài liệu: {citation.doc_id}, Trang: {citation.page}"
                    if citation.bbox:
                        cite_text += f" (Vị trí: {citation.bbox})"
                    lines.append(cite_text)
            lines.append("")

        return "\n".join(lines)

    def _extract_citations_from_response(
        self, response: Dict[str, Any]
    ) -> List[Citation]:
        """Extract citations from generator response."""
        citations = []

        if "citations" in response:
            for cite_data in response["citations"]:
                citation = Citation(
                    doc_id=cite_data.get("doc_id", "unknown"),
                    page=cite_data.get("page", 1),
                    bbox=cite_data.get("bbox"),
                    confidence=cite_data.get("confidence", 0.5),
                )
                citations.append(citation)

        return citations

    def _deduplicate_citations(self, citations: List[Citation]) -> List[Citation]:
        """Deduplicate citations by doc_id and page."""
        seen = set()
        unique = []

        for citation in citations:
            key = (citation.doc_id, citation.page)
            if key not in seen:
                seen.add(key)
                unique.append(citation)

        return unique
