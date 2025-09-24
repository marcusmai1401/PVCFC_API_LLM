"""
Retrieval Evaluation Module
Evaluates retrieval performance against expected documents and relevance criteria.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
from loguru import logger

from app.core.tracing import trace_operation


@dataclass
class RetrievalMetrics:
    """Retrieval evaluation metrics."""

    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0
    retrieved_docs: List[Dict[str, Any]] = None
    relevant_docs_found: int = 0
    total_relevant_docs: int = 0
    latency_ms: float = 0.0


class RetrievalEvaluator:
    """Evaluates retrieval performance."""

    def __init__(self, retrieval_endpoint: Optional[str] = None):
        self.retrieval_endpoint = retrieval_endpoint
        self.logger = logger.bind(component="retrieval_evaluator")

        # For simulation mode when no endpoint provided
        self.simulation_mode = retrieval_endpoint is None
        if self.simulation_mode:
            self.logger.info("Running in simulation mode - no real retrieval endpoint")

    @trace_operation("retrieval_evaluation")
    def evaluate(
        self,
        query: str,
        doc_hints: List[str] = None,
        expected_docs: List[Dict[str, Any]] = None,
        k_values: List[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate retrieval performance for a query.

        Args:
            query: Search query
            doc_hints: Expected document categories/types
            expected_docs: List of expected relevant documents
            k_values: Values of k for Recall@k and Precision@k evaluation

        Returns:
            Dictionary with retrieval metrics and results
        """
        if k_values is None:
            k_values = [5, 10]

        self.logger.info(f"Evaluating retrieval for query: {query[:50]}...")

        start_time = time.time()

        try:
            # Get retrieval results
            if self.simulation_mode:
                retrieved_docs = self._simulate_retrieval(query, doc_hints)
            else:
                retrieved_docs = self._call_retrieval_api(query)

            retrieval_time = (time.time() - start_time) * 1000

            # Calculate metrics
            metrics = self._calculate_metrics(
                retrieved_docs=retrieved_docs,
                expected_docs=expected_docs or [],
                doc_hints=doc_hints or [],
                k_values=k_values,
            )

            metrics.latency_ms = retrieval_time
            metrics.retrieved_docs = retrieved_docs

            return {
                "recall_at_5": metrics.recall_at_5,
                "recall_at_10": metrics.recall_at_10,
                "precision_at_5": metrics.precision_at_5,
                "precision_at_10": metrics.precision_at_10,
                "ndcg_at_5": metrics.ndcg_at_5,
                "ndcg_at_10": metrics.ndcg_at_10,
                "retrieved_docs": retrieved_docs,
                "relevant_docs_found": metrics.relevant_docs_found,
                "total_relevant_docs": metrics.total_relevant_docs,
                "latency_ms": metrics.latency_ms,
            }

        except Exception as e:
            self.logger.error(f"Retrieval evaluation failed: {str(e)}")
            return {"error": str(e)}

    def _call_retrieval_api(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Call real retrieval API."""
        try:
            response = requests.post(
                self.retrieval_endpoint,
                json={"query": query, "top_k": top_k, "include_metadata": True},
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            return result.get("documents", [])

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Retrieval API call failed: {str(e)}")
            raise

    def _simulate_retrieval(
        self, query: str, doc_hints: List[str]
    ) -> List[Dict[str, Any]]:
        """Simulate retrieval results for testing."""
        # Simulate realistic retrieval results based on query and doc_hints
        simulated_docs = []

        # Create realistic document simulation
        base_docs = [
            {
                "id": "doc_datasheet_001",
                "type": "datasheet",
                "title": "Equipment Specifications",
                "score": 0.95,
            },
            {
                "id": "doc_datasheet_002",
                "type": "datasheet",
                "title": "Technical Parameters",
                "score": 0.88,
            },
            {
                "id": "doc_pid_001",
                "type": "pid",
                "title": "P&ID Main Process",
                "score": 0.92,
            },
            {
                "id": "doc_pid_002",
                "type": "pid",
                "title": "Instrumentation Diagram",
                "score": 0.85,
            },
            {
                "id": "doc_om_001",
                "type": "om",
                "title": "Operation Manual",
                "score": 0.82,
            },
            {
                "id": "doc_om_002",
                "type": "om",
                "title": "Maintenance Procedures",
                "score": 0.75,
            },
            {
                "id": "doc_sop_001",
                "type": "sop",
                "title": "Standard Operating Procedures",
                "score": 0.78,
            },
            {
                "id": "doc_general_001",
                "type": "general",
                "title": "General Information",
                "score": 0.65,
            },
            {
                "id": "doc_general_002",
                "type": "general",
                "title": "Background Notes",
                "score": 0.60,
            },
            {
                "id": "doc_irrelevant_001",
                "type": "other",
                "title": "Irrelevant Document",
                "score": 0.45,
            },
        ]

        # Score adjustment based on doc_hints
        for doc in base_docs:
            if doc_hints and doc["type"] in doc_hints:
                doc["score"] += 0.1  # Boost score for expected doc types

            # Query-specific adjustments
            query_lower = query.lower()
            if "pressure" in query_lower or "áp suất" in query_lower:
                if "specifications" in doc["title"].lower():
                    doc["score"] += 0.05
            elif "location" in query_lower or "vị trí" in query_lower:
                if "pid" in doc["type"] or "diagram" in doc["title"].lower():
                    doc["score"] += 0.08
            elif "procedure" in query_lower or "quy trình" in query_lower:
                if doc["type"] in ["om", "sop"]:
                    doc["score"] += 0.1

        # Sort by score and take top 10
        sorted_docs = sorted(base_docs, key=lambda x: x["score"], reverse=True)

        # Add some noise and variation
        import random

        random.seed(hash(query) % 1000)  # Deterministic but query-specific

        for i, doc in enumerate(sorted_docs[:10]):
            noise = random.uniform(-0.05, 0.05)
            doc["score"] = max(0.1, min(1.0, doc["score"] + noise))

            # Add metadata
            doc[
                "chunk_text"
            ] = f"Sample content from {doc['title']} related to: {query[:30]}..."
            doc["page_number"] = random.randint(1, 50)
            doc["chunk_index"] = i
            doc["metadata"] = {
                "doc_type": doc["type"],
                "relevance_score": doc["score"],
                "retrieval_rank": i + 1,
            }

        return sorted_docs[:10]

    def _calculate_metrics(
        self,
        retrieved_docs: List[Dict[str, Any]],
        expected_docs: List[Dict[str, Any]],
        doc_hints: List[str],
        k_values: List[int],
    ) -> RetrievalMetrics:
        """Calculate retrieval metrics."""
        metrics = RetrievalMetrics()

        if not retrieved_docs:
            return metrics

        # Determine relevant documents
        relevant_doc_ids = self._get_relevant_doc_ids(
            expected_docs, doc_hints, retrieved_docs
        )
        retrieved_doc_ids = [doc.get("id", "") for doc in retrieved_docs]

        # Calculate metrics for each k value
        for k in k_values:
            top_k_retrieved = retrieved_doc_ids[:k]
            relevant_in_top_k = len(
                [doc_id for doc_id in top_k_retrieved if doc_id in relevant_doc_ids]
            )

            # Recall@k = relevant_in_top_k / total_relevant_docs
            recall_at_k = (
                relevant_in_top_k / len(relevant_doc_ids) if relevant_doc_ids else 0
            )

            # Precision@k = relevant_in_top_k / k
            precision_at_k = relevant_in_top_k / k if k > 0 else 0

            # NDCG@k (simplified version)
            ndcg_at_k = self._calculate_ndcg(retrieved_docs[:k], relevant_doc_ids, k)

            # Store metrics
            if k == 5:
                metrics.recall_at_5 = recall_at_k
                metrics.precision_at_5 = precision_at_k
                metrics.ndcg_at_5 = ndcg_at_k
            elif k == 10:
                metrics.recall_at_10 = recall_at_k
                metrics.precision_at_10 = precision_at_k
                metrics.ndcg_at_10 = ndcg_at_k

        metrics.relevant_docs_found = len(
            [doc_id for doc_id in retrieved_doc_ids if doc_id in relevant_doc_ids]
        )
        metrics.total_relevant_docs = len(relevant_doc_ids)

        return metrics

    def _get_relevant_doc_ids(
        self,
        expected_docs: List[Dict[str, Any]],
        doc_hints: List[str],
        retrieved_docs: List[Dict[str, Any]],
    ) -> Set[str]:
        """Determine relevant document IDs."""
        relevant_ids = set()

        # Add explicitly expected documents
        for doc in expected_docs:
            if "id" in doc:
                relevant_ids.add(doc["id"])

        # If no explicit expected docs, use doc_hints to determine relevance
        if not relevant_ids and doc_hints:
            for doc in retrieved_docs:
                doc_type = doc.get("type", "")
                doc_metadata = doc.get("metadata", {})
                metadata_type = doc_metadata.get("doc_type", "")

                # Check if document type matches hints
                if doc_type in doc_hints or metadata_type in doc_hints:
                    relevant_ids.add(doc.get("id", ""))

                # Also consider high-scoring documents as potentially relevant
                score = doc.get("score", 0)
                if score > 0.8:  # High relevance threshold
                    relevant_ids.add(doc.get("id", ""))

        # If still no relevant docs identified, consider top scoring docs as relevant
        if not relevant_ids and retrieved_docs:
            # Take top 3 scoring documents as relevant
            sorted_docs = sorted(
                retrieved_docs, key=lambda x: x.get("score", 0), reverse=True
            )
            for doc in sorted_docs[:3]:
                relevant_ids.add(doc.get("id", ""))

        return relevant_ids

    def _calculate_ndcg(
        self, retrieved_docs: List[Dict[str, Any]], relevant_doc_ids: Set[str], k: int
    ) -> float:
        """Calculate Normalized Discounted Cumulative Gain (NDCG) at k."""
        import math

        if not retrieved_docs or not relevant_doc_ids:
            return 0.0

        # Calculate DCG (Discounted Cumulative Gain)
        dcg = 0.0
        for i, doc in enumerate(retrieved_docs[:k]):
            doc_id = doc.get("id", "")
            relevance = 1.0 if doc_id in relevant_doc_ids else 0.0

            # Use score as relevance grade if available
            if doc_id in relevant_doc_ids:
                relevance = doc.get("score", 1.0)

            # DCG formula: sum(rel_i / log2(i+2))
            dcg += relevance / math.log2(i + 2)

        # Calculate IDCG (Ideal DCG)
        # Sort by relevance in descending order
        ideal_relevances = []
        for doc in retrieved_docs:
            doc_id = doc.get("id", "")
            if doc_id in relevant_doc_ids:
                ideal_relevances.append(doc.get("score", 1.0))

        ideal_relevances.sort(reverse=True)

        idcg = 0.0
        for i, relevance in enumerate(ideal_relevances[:k]):
            idcg += relevance / math.log2(i + 2)

        # NDCG = DCG / IDCG
        return dcg / idcg if idcg > 0 else 0.0

    def batch_evaluate(
        self, queries_and_expected: List[Dict[str, Any]], k_values: List[int] = None
    ) -> Dict[str, Any]:
        """
        Batch evaluate multiple queries.

        Args:
            queries_and_expected: List of dicts with 'query', 'doc_hints', 'expected_docs'
            k_values: Values of k for evaluation

        Returns:
            Aggregated metrics across all queries
        """
        if k_values is None:
            k_values = [5, 10]

        all_results = []

        for item in queries_and_expected:
            query = item.get("query", "")
            doc_hints = item.get("doc_hints", [])
            expected_docs = item.get("expected_docs", [])

            result = self.evaluate(
                query=query,
                doc_hints=doc_hints,
                expected_docs=expected_docs,
                k_values=k_values,
            )

            if "error" not in result:
                all_results.append(result)

        # Aggregate results
        if not all_results:
            return {"error": "No successful evaluations"}

        aggregated = {
            "total_queries": len(all_results),
            "avg_recall_at_5": sum(r["recall_at_5"] for r in all_results)
            / len(all_results),
            "avg_recall_at_10": sum(r["recall_at_10"] for r in all_results)
            / len(all_results),
            "avg_precision_at_5": sum(r["precision_at_5"] for r in all_results)
            / len(all_results),
            "avg_precision_at_10": sum(r["precision_at_10"] for r in all_results)
            / len(all_results),
            "avg_ndcg_at_5": sum(r["ndcg_at_5"] for r in all_results)
            / len(all_results),
            "avg_ndcg_at_10": sum(r["ndcg_at_10"] for r in all_results)
            / len(all_results),
            "avg_latency_ms": sum(r["latency_ms"] for r in all_results)
            / len(all_results),
            "total_relevant_docs": sum(r["total_relevant_docs"] for r in all_results),
            "total_relevant_found": sum(r["relevant_docs_found"] for r in all_results),
        }

        return aggregated
