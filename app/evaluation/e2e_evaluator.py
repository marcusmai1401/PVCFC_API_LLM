"""
End-to-End RAG Evaluation Module
Evaluates the complete RAG pipeline including answer quality, citations, and CoVe verification.
"""
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

from app.core.tracing import trace_operation


@dataclass
class E2EMetrics:
    """End-to-end evaluation metrics."""

    answer: str = ""
    citations: List[Dict[str, Any]] = None
    citation_rate: float = 0.0
    citation_precision: float = 0.0
    citation_recall: float = 0.0
    answer_quality_score: float = 0.0
    cove_verification_score: float = 0.0
    factual_consistency_score: float = 0.0
    completeness_score: float = 0.0
    relevance_score: float = 0.0
    latency_ms: float = 0.0
    expected_behavior_met: bool = False
    behavior_validation_notes: str = ""


class E2EEvaluator:
    """Evaluates end-to-end RAG performance."""

    def __init__(self, rag_endpoint: Optional[str] = None):
        self.rag_endpoint = rag_endpoint
        self.logger = logger.bind(component="e2e_evaluator")

        # For simulation mode when no endpoint provided
        self.simulation_mode = rag_endpoint is None
        if self.simulation_mode:
            self.logger.info("Running in simulation mode - no real RAG endpoint")

    @trace_operation("e2e_evaluation")
    def evaluate(
        self,
        query: str,
        expected_behavior: Optional[str] = None,
        expected_answer_snippet: Optional[str] = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate end-to-end RAG performance for a query.

        Args:
            query: User query
            expected_behavior: Expected behavior (should_not_answer, should_ask_clarification, etc.)
            expected_answer_snippet: Expected content patterns in answer
            context: Additional context (doc_category, etc.)

        Returns:
            Dictionary with E2E metrics and results
        """
        self.logger.info(f"Evaluating E2E RAG for query: {query[:50]}...")

        start_time = time.time()
        context = context or {}

        try:
            # Get RAG response
            if self.simulation_mode:
                rag_response = self._simulate_rag_response(
                    query, expected_behavior, context
                )
            else:
                rag_response = self._call_rag_api(query)

            response_time = (time.time() - start_time) * 1000

            # Extract components from response
            answer = rag_response.get("answer", "")
            citations = rag_response.get("citations", [])
            metadata = rag_response.get("metadata", {})

            # Calculate metrics
            metrics = self._calculate_e2e_metrics(
                query=query,
                answer=answer,
                citations=citations,
                metadata=metadata,
                expected_behavior=expected_behavior,
                expected_answer_snippet=expected_answer_snippet,
                context=context,
            )

            metrics.latency_ms = response_time

            return {
                "answer": metrics.answer,
                "citations": metrics.citations,
                "citation_rate": metrics.citation_rate,
                "citation_precision": metrics.citation_precision,
                "citation_recall": metrics.citation_recall,
                "answer_quality": metrics.answer_quality_score,
                "cove_score": metrics.cove_verification_score,
                "factual_consistency": metrics.factual_consistency_score,
                "completeness": metrics.completeness_score,
                "relevance": metrics.relevance_score,
                "latency_ms": metrics.latency_ms,
                "expected_behavior_met": metrics.expected_behavior_met,
                "validation_notes": metrics.behavior_validation_notes,
            }

        except Exception as e:
            self.logger.error(f"E2E evaluation failed: {str(e)}")
            return {"error": str(e)}

    def _call_rag_api(self, query: str) -> Dict[str, Any]:
        """Call real RAG API."""
        try:
            response = requests.post(
                self.rag_endpoint,
                json={
                    "query": query,
                    "include_citations": True,
                    "include_metadata": True,
                },
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()
            return result

        except requests.exceptions.RequestException as e:
            self.logger.error(f"RAG API call failed: {str(e)}")
            raise

    def _simulate_rag_response(
        self, query: str, expected_behavior: Optional[str], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate RAG response for testing."""
        query_lower = query.lower()
        doc_category = context.get("doc_category", "")

        # Simulate different response types based on expected behavior
        if expected_behavior == "should_not_answer":
            # Negative case - should refuse to answer
            return {
                "answer": "Tôi không có thông tin về câu hỏi này trong cơ sở dữ liệu hiện tại.",
                "citations": [],
                "metadata": {
                    "confidence": 0.95,
                    "reasoning": "No relevant information found",
                },
            }

        elif expected_behavior == "should_ask_clarification":
            # Ambiguous case - should ask for clarification
            return {
                "answer": "Vui lòng làm rõ cụ thể bạn muốn biết thông tin về thiết bị nào hoặc thông số nào?",
                "citations": [],
                "metadata": {"confidence": 0.7, "reasoning": "Query too ambiguous"},
            }

        # Generate realistic answers based on query content
        answer = ""
        citations = []

        if "áp suất" in query_lower or "pressure" in query_lower:
            answer = "Áp suất vận hành của hệ thống là 15.5 bar (225 psi) theo thông số kỹ thuật."
            citations = [
                {
                    "document_id": "doc_datasheet_001",
                    "page_number": 12,
                    "chunk_text": "Operating pressure: 15.5 bar (225 psi)",
                    "confidence": 0.95,
                },
                {
                    "document_id": "doc_datasheet_002",
                    "page_number": 8,
                    "chunk_text": "Maximum working pressure 16 bar",
                    "confidence": 0.88,
                },
            ]

        elif "nhiệt độ" in query_lower or "temperature" in query_lower:
            answer = "Nhiệt độ làm việc tối đa của thiết bị là 180°C theo datasheet kỹ thuật."
            citations = [
                {
                    "document_id": "doc_datasheet_001",
                    "page_number": 15,
                    "chunk_text": "Maximum operating temperature: 180°C",
                    "confidence": 0.92,
                }
            ]

        elif (
            "vị trí" in query_lower
            or "location" in query_lower
            or "nằm ở đâu" in query_lower
        ):
            answer = "Thiết bị được đặt tại vị trí Grid E-7 trên bản vẽ P&ID, tầng 2 của khu vực xử lý chính."
            citations = [
                {
                    "document_id": "doc_pid_001",
                    "page_number": 3,
                    "chunk_text": "Equipment location: Grid E-7, Level 2",
                    "confidence": 0.90,
                }
            ]

        elif (
            "quy trình" in query_lower
            or "procedure" in query_lower
            or "bảo trì" in query_lower
        ):
            answer = """Quy trình bảo trì thiết bị bao gồm các bước sau:
1. Tắt nguồn cung cấp và cô lập hệ thống
2. Xả áp suất và làm sạch đường ống
3. Kiểm tra các bộ phận chính
4. Thay thế các linh kiện hỏng hóc
5. Lắp ráp lại và thử nghiệm hoạt động"""
            citations = [
                {
                    "document_id": "doc_om_001",
                    "page_number": 45,
                    "chunk_text": "Maintenance procedure steps 1-5",
                    "confidence": 0.85,
                },
                {
                    "document_id": "doc_sop_001",
                    "page_number": 23,
                    "chunk_text": "Standard maintenance protocol",
                    "confidence": 0.82,
                },
            ]

        elif "thông số" in query_lower or "specification" in query_lower:
            answer = """Thông số kỹ thuật chính của thiết bị:
- Công suất: 45 kW
- Áp suất vận hành: 15.5 bar
- Nhiệt độ tối đa: 180°C
- Dung tích: 2500 lít
- Vật liệu: Thép không gỉ 316L"""
            citations = [
                {
                    "document_id": "doc_datasheet_001",
                    "page_number": 5,
                    "chunk_text": "Technical specifications table",
                    "confidence": 0.95,
                }
            ]

        else:
            # Default response
            answer = "Dựa trên tài liệu kỹ thuật, thông tin được yêu cầu có thể tìm thấy trong các datasheet và sổ tay vận hành."
            citations = [
                {
                    "document_id": "doc_general_001",
                    "page_number": 1,
                    "chunk_text": "General equipment information",
                    "confidence": 0.70,
                }
            ]

        return {
            "answer": answer,
            "citations": citations,
            "metadata": {
                "confidence": 0.85,
                "reasoning": "Based on technical documentation",
                "processing_time_ms": 250,
            },
        }

    def _calculate_e2e_metrics(
        self,
        query: str,
        answer: str,
        citations: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        expected_behavior: Optional[str],
        expected_answer_snippet: Optional[str],
        context: Dict[str, Any],
    ) -> E2EMetrics:
        """Calculate comprehensive E2E metrics."""
        metrics = E2EMetrics()
        metrics.answer = answer
        metrics.citations = citations or []

        # Calculate citation metrics
        metrics.citation_rate = self._calculate_citation_rate(answer, citations)
        (
            metrics.citation_precision,
            metrics.citation_recall,
        ) = self._calculate_citation_precision_recall(citations)

        # Calculate answer quality metrics
        metrics.answer_quality_score = self._calculate_answer_quality(
            query, answer, citations
        )
        metrics.cove_verification_score = self._calculate_cove_score(
            answer, citations, metadata
        )
        metrics.factual_consistency_score = self._calculate_factual_consistency(
            answer, citations
        )
        metrics.completeness_score = self._calculate_completeness(query, answer)
        metrics.relevance_score = self._calculate_relevance(query, answer)

        # Validate expected behavior
        (
            metrics.expected_behavior_met,
            metrics.behavior_validation_notes,
        ) = self._validate_expected_behavior(
            answer, citations, expected_behavior, expected_answer_snippet
        )

        return metrics

    def _calculate_citation_rate(
        self, answer: str, citations: List[Dict[str, Any]]
    ) -> float:
        """Calculate citation rate - ratio of cited content to total content."""
        if not answer or not citations:
            return 0.0

        # Simple heuristic: if there are citations and non-empty answer, assume some citation
        answer_length = len(answer.strip())
        citation_count = len(citations)

        if answer_length == 0:
            return 0.0

        # Basic citation rate calculation
        # More citations for longer answers suggests better citation coverage
        expected_citations = max(1, answer_length // 100)  # 1 citation per ~100 chars
        citation_ratio = min(1.0, citation_count / expected_citations)

        return citation_ratio

    def _calculate_citation_precision_recall(
        self, citations: List[Dict[str, Any]]
    ) -> tuple[float, float]:
        """Calculate citation precision and recall."""
        if not citations:
            return 0.0, 0.0

        # Simulate precision/recall based on citation confidence scores
        total_citations = len(citations)
        high_confidence_citations = len(
            [c for c in citations if c.get("confidence", 0) > 0.8]
        )

        precision = (
            high_confidence_citations / total_citations if total_citations > 0 else 0
        )

        # For recall, we simulate based on typical expected citation coverage
        expected_citations = 3  # Assume 3 relevant citations on average
        recall = min(1.0, total_citations / expected_citations)

        return precision, recall

    def _calculate_answer_quality(
        self, query: str, answer: str, citations: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall answer quality score."""
        if not answer:
            return 0.0

        quality_score = 0.0

        # Length appropriateness (0.2 weight)
        answer_length = len(answer.strip())
        if 20 <= answer_length <= 500:
            quality_score += 0.2
        elif answer_length > 500:
            quality_score += 0.15  # Slightly penalize very long answers
        elif answer_length > 10:
            quality_score += 0.1

        # Citation support (0.3 weight)
        if citations:
            citation_score = min(0.3, len(citations) * 0.1)
            quality_score += citation_score

        # Content relevance to query (0.3 weight)
        relevance = self._calculate_relevance(query, answer)
        quality_score += relevance * 0.3

        # Structure and clarity (0.2 weight)
        structure_score = self._assess_answer_structure(answer)
        quality_score += structure_score * 0.2

        return min(1.0, quality_score)

    def _calculate_cove_score(
        self, answer: str, citations: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> float:
        """Calculate Chain-of-Verification (CoVe) score."""
        if not answer:
            return 0.0

        # Base confidence from metadata
        base_confidence = metadata.get("confidence", 0.5)

        # Citation consistency bonus
        citation_bonus = 0.0
        if citations:
            avg_citation_confidence = sum(
                c.get("confidence", 0.5) for c in citations
            ) / len(citations)
            citation_bonus = min(0.2, avg_citation_confidence * 0.2)

        # Answer factuality check (simplified)
        factuality_score = self._check_answer_factuality(answer)

        # Combine scores
        cove_score = (base_confidence * 0.6) + citation_bonus + (factuality_score * 0.2)

        return min(1.0, cove_score)

    def _calculate_factual_consistency(
        self, answer: str, citations: List[Dict[str, Any]]
    ) -> float:
        """Calculate factual consistency between answer and citations."""
        if not answer or not citations:
            return 0.0

        # Simplified consistency check
        # In a real implementation, this would use semantic similarity

        consistency_score = 0.7  # Base score

        # Bonus for high-confidence citations
        if citations:
            high_conf_citations = [
                c for c in citations if c.get("confidence", 0) > 0.85
            ]
            if high_conf_citations:
                consistency_score += 0.2

        # Check for contradictory language patterns
        contradiction_patterns = [
            "không",
            "không phải",
            "not",
            "no",
            "never",
            "contradicts",
        ]
        if any(pattern in answer.lower() for pattern in contradiction_patterns):
            consistency_score -= 0.3

        return max(0.0, min(1.0, consistency_score))

    def _calculate_completeness(self, query: str, answer: str) -> float:
        """Calculate answer completeness relative to query."""
        if not answer:
            return 0.0

        # Check if answer addresses main query components
        query_lower = query.lower()
        answer_lower = answer.lower()

        completeness_score = 0.5  # Base score

        # Check for specific query terms in answer
        key_terms = self._extract_key_terms(query)
        term_coverage = (
            sum(1 for term in key_terms if term in answer_lower) / len(key_terms)
            if key_terms
            else 0
        )
        completeness_score += term_coverage * 0.3

        # Length-based completeness (more complete answers tend to be longer)
        answer_length = len(answer.strip())
        if answer_length > 50:
            completeness_score += 0.2

        return min(1.0, completeness_score)

    def _calculate_relevance(self, query: str, answer: str) -> float:
        """Calculate answer relevance to query."""
        if not answer:
            return 0.0

        query_lower = query.lower()
        answer_lower = answer.lower()

        # Simple keyword overlap
        query_words = set(query_lower.split())
        answer_words = set(answer_lower.split())

        # Remove common stop words
        stop_words = {
            "là",
            "của",
            "và",
            "trong",
            "có",
            "được",
            "để",
            "này",
            "đó",
            "the",
            "is",
            "and",
            "or",
            "of",
            "in",
            "to",
        }
        query_words -= stop_words
        answer_words -= stop_words

        if not query_words:
            return 0.5

        overlap = len(query_words & answer_words)
        relevance = overlap / len(query_words)

        return min(1.0, relevance)

    def _assess_answer_structure(self, answer: str) -> float:
        """Assess answer structure and clarity."""
        if not answer:
            return 0.0

        structure_score = 0.5  # Base score

        # Check for bullet points or numbering (good structure)
        if re.search(r"[0-9]\.|[\*\-]|\n", answer):
            structure_score += 0.3

        # Check sentence structure
        sentences = answer.split(".")
        if 1 <= len(sentences) <= 10:  # Reasonable number of sentences
            structure_score += 0.2

        return min(1.0, structure_score)

    def _check_answer_factuality(self, answer: str) -> float:
        """Check answer factuality (simplified version)."""
        if not answer:
            return 0.0

        # Look for factual indicators
        factual_indicators = [
            "theo",
            "dựa trên",
            "according to",
            "based on",
            "documented",
            "specified",
        ]
        uncertainty_indicators = ["có thể", "might", "possibly", "perhaps", "unclear"]

        factuality_score = 0.6  # Base score

        # Bonus for factual language
        if any(indicator in answer.lower() for indicator in factual_indicators):
            factuality_score += 0.2

        # Penalty for uncertain language
        if any(indicator in answer.lower() for indicator in uncertainty_indicators):
            factuality_score -= 0.1

        return max(0.0, min(1.0, factuality_score))

    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from query."""
        # Simple key term extraction
        stop_words = {
            "là",
            "của",
            "và",
            "trong",
            "có",
            "được",
            "để",
            "này",
            "đó",
            "gì",
            "nào",
            "như",
            "thế",
            "bao",
            "nhiêu",
        }
        words = [
            w.lower()
            for w in query.split()
            if w.lower() not in stop_words and len(w) > 2
        ]
        return words

    def _validate_expected_behavior(
        self,
        answer: str,
        citations: List[Dict[str, Any]],
        expected_behavior: Optional[str],
        expected_answer_snippet: Optional[str],
    ) -> tuple[bool, str]:
        """Validate if response meets expected behavior."""
        if not expected_behavior:
            return True, "No expected behavior specified"

        notes = []
        behavior_met = False

        if expected_behavior == "should_not_answer":
            # Should have low citation rate and refusal language
            refusal_patterns = [
                "không có thông tin",
                "no information",
                "cannot answer",
                "không thể trả lời",
            ]
            has_refusal = any(pattern in answer.lower() for pattern in refusal_patterns)
            low_citations = len(citations) <= 1

            behavior_met = has_refusal and low_citations
            notes.append(
                f"Refusal language: {has_refusal}, Low citations: {low_citations}"
            )

        elif expected_behavior == "should_ask_clarification":
            # Should ask for clarification
            clarification_patterns = [
                "vui lòng làm rõ",
                "clarification",
                "specify",
                "which",
                "cụ thể",
            ]
            has_clarification = any(
                pattern in answer.lower() for pattern in clarification_patterns
            )

            behavior_met = has_clarification
            notes.append(f"Has clarification request: {has_clarification}")

        elif expected_behavior == "should_provide_value_with_unit":
            # Should contain numerical values with units
            unit_patterns = [
                "bar",
                "psi",
                "kPa",
                "MPa",
                "°C",
                "K",
                "°F",
                "kW",
                "MW",
                "HP",
                "rpm",
                "m³/h",
                "kg/h",
            ]
            has_units = any(unit in answer for unit in unit_patterns)
            has_citations = len(citations) > 0

            behavior_met = has_units and has_citations
            notes.append(f"Has units: {has_units}, Has citations: {has_citations}")

        elif expected_behavior == "should_provide_location":
            # Should provide location information
            has_location = len(answer.strip()) > 20 and len(citations) > 0

            behavior_met = has_location
            notes.append(f"Adequate location info: {has_location}")

        elif expected_behavior == "should_provide_steps":
            # Should provide step-by-step information
            step_patterns = [
                "bước",
                "step",
                "procedure",
                "quy trình",
                "1.",
                "2.",
                "first",
                "then",
                "next",
            ]
            has_steps = any(pattern in answer.lower() for pattern in step_patterns)

            behavior_met = has_steps
            notes.append(f"Has procedural steps: {has_steps}")

        else:
            # Default: should provide substantive answer with citations
            has_content = len(answer.strip()) > 10
            has_citations = len(citations) > 0

            behavior_met = has_content and has_citations
            notes.append(f"Has content: {has_content}, Has citations: {has_citations}")

        # Check expected answer snippet if provided
        if expected_answer_snippet:
            snippet_patterns = expected_answer_snippet.split("|")
            has_expected_content = any(
                pattern.strip() in answer for pattern in snippet_patterns
            )
            behavior_met = behavior_met and has_expected_content
            notes.append(f"Has expected content pattern: {has_expected_content}")

        return behavior_met, " | ".join(notes)
