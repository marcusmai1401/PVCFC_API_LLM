"""
Batch Evaluation Runner for RAG Pipeline
Runs comprehensive evaluation on QA datasets with parallel processing and detailed reporting.
"""
import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from loguru import logger

from app.core.logging import get_structured_logger
from app.core.metrics import MetricsCollector
from app.core.tracing import trace_operation, trace_span


@dataclass
class EvaluationConfig:
    """Configuration for batch evaluation."""

    qa_file: Path
    output_dir: Path

    # Evaluation modes
    run_retrieval_eval: bool = True
    run_e2e_eval: bool = True
    run_citation_eval: bool = True
    run_latency_eval: bool = True

    # Processing config
    max_workers: int = 4
    batch_size: int = 10
    timeout_seconds: int = 60

    # Sampling config
    sample_size: Optional[int] = None  # None = all questions
    random_seed: int = 42

    # Output config
    generate_html_report: bool = True
    generate_json_report: bool = True
    save_individual_results: bool = True

    # API endpoints (for real evaluation)
    retrieval_endpoint: Optional[str] = None
    rag_endpoint: Optional[str] = None

    def __post_init__(self):
        self.qa_file = Path(self.qa_file)
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class EvaluationResult:
    """Single QA evaluation result."""

    qa_id: str
    query: str
    intent: str
    doc_category: Optional[str]
    expected_behavior: str

    # Retrieval results
    retrieval_docs: List[Dict[str, Any]] = None
    retrieval_recall_5: float = 0.0
    retrieval_recall_10: float = 0.0
    retrieval_precision_5: float = 0.0

    # RAG results
    generated_answer: Optional[str] = None
    citations: List[Dict[str, Any]] = None
    citation_rate: float = 0.0
    answer_quality_score: float = 0.0
    cove_verification_score: float = 0.0

    # Performance metrics
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0

    # Validation results
    expected_behavior_met: bool = False
    validation_notes: str = ""

    # Error handling
    has_error: bool = False
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class BatchEvaluationRunner:
    """Main batch evaluation runner."""

    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.logger = get_structured_logger(
            name="batch_evaluation", component="evaluation_runner"
        )
        self.metrics = MetricsCollector()

        # Load QA data
        self.qa_data = self._load_qa_data()
        self.results: List[EvaluationResult] = []

        # Progress tracking
        self.progress_lock = threading.Lock()
        self.completed_count = 0
        self.total_count = len(self.qa_data)

        # Load evaluation modules
        self.retrieval_evaluator = None
        self.e2e_evaluator = None

        if config.run_retrieval_eval:
            from app.evaluation.retrieval_evaluator import RetrievalEvaluator

            self.retrieval_evaluator = RetrievalEvaluator(config.retrieval_endpoint)

        if config.run_e2e_eval:
            from app.evaluation.e2e_evaluator import E2EEvaluator

            self.e2e_evaluator = E2EEvaluator(config.rag_endpoint)

    def _load_qa_data(self) -> List[Dict[str, Any]]:
        """Load QA dataset."""
        qa_list = []
        with open(self.config.qa_file, "r", encoding="utf-8") as f:
            for line in f:
                qa_list.append(json.loads(line))

        # Apply sampling if configured
        if self.config.sample_size and self.config.sample_size < len(qa_list):
            import random

            random.seed(self.config.random_seed)
            qa_list = random.sample(qa_list, self.config.sample_size)
            self.logger.info(
                f"Sampled {len(qa_list)} questions from {self.config.sample_size}"
            )

        self.logger.info(f"Loaded {len(qa_list)} QA pairs for evaluation")
        return qa_list

    @trace_operation("batch_evaluation")
    async def run_evaluation(self) -> Dict[str, Any]:
        """Run full batch evaluation."""
        self.logger.info("🚀 Starting batch evaluation")
        start_time = time.time()

        try:
            # Process in batches with concurrent execution
            await self._process_batches()

            # Generate aggregated metrics
            aggregated_metrics = self._aggregate_results()

            # Generate reports
            report_paths = await self._generate_reports(aggregated_metrics)

            total_time = time.time() - start_time

            self.logger.info(f"✅ Batch evaluation completed in {total_time:.2f}s")
            self.logger.info(f"📊 Processed {len(self.results)} questions")
            self.logger.info(f"📝 Reports saved to {self.config.output_dir}")

            return {
                "status": "completed",
                "total_time_seconds": total_time,
                "questions_processed": len(self.results),
                "aggregated_metrics": aggregated_metrics,
                "report_paths": report_paths,
            }

        except Exception as e:
            self.logger.error(f"❌ Batch evaluation failed: {str(e)}", exc_info=True)
            raise

    async def _process_batches(self):
        """Process QA pairs in batches with concurrent execution."""
        batch_size = self.config.batch_size
        max_workers = self.config.max_workers

        # Split into batches
        batches = [
            self.qa_data[i : i + batch_size]
            for i in range(0, len(self.qa_data), batch_size)
        ]

        self.logger.info(
            f"Processing {len(batches)} batches with {max_workers} workers"
        )

        # Process batches concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batches
            future_to_batch = {
                executor.submit(self._process_batch, batch_idx, batch): batch_idx
                for batch_idx, batch in enumerate(batches)
            }

            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    batch_results = future.result(timeout=self.config.timeout_seconds)
                    self.results.extend(batch_results)

                    with self.progress_lock:
                        self.completed_count += len(batch_results)
                        progress = (self.completed_count / self.total_count) * 100
                        self.logger.info(
                            f"Batch {batch_idx + 1} completed. Progress: {progress:.1f}%"
                        )

                except Exception as e:
                    self.logger.error(f"Batch {batch_idx} failed: {str(e)}")
                    # Continue with other batches

    def _process_batch(
        self, batch_idx: int, batch: List[Dict[str, Any]]
    ) -> List[EvaluationResult]:
        """Process a single batch of QA pairs."""
        batch_results = []

        for qa in batch:
            try:
                result = self._evaluate_single_qa(qa)
                batch_results.append(result)

                # Record metrics
                self.metrics.increment_counter("evaluation.questions_processed")
                if result.has_error:
                    self.metrics.increment_counter("evaluation.questions_failed")
                else:
                    self.metrics.increment_counter("evaluation.questions_succeeded")

            except Exception as e:
                # Create error result
                error_result = EvaluationResult(
                    qa_id=qa.get("id", "unknown"),
                    query=qa.get("query", ""),
                    intent=qa.get("intent", ""),
                    doc_category=qa.get("doc_category"),
                    expected_behavior=qa.get("expected_behavior", ""),
                    has_error=True,
                    error_message=str(e),
                )
                batch_results.append(error_result)
                self.metrics.increment_counter("evaluation.questions_failed")

                self.logger.error(f"Failed to evaluate QA {qa.get('id')}: {str(e)}")

        return batch_results

    def _evaluate_single_qa(self, qa: Dict[str, Any]) -> EvaluationResult:
        """Evaluate a single QA pair."""
        qa_id = qa.get("id", "unknown")

        with trace_span("evaluate_qa", qa_id=qa_id):
            result = EvaluationResult(
                qa_id=qa_id,
                query=qa.get("query", ""),
                intent=qa.get("intent", ""),
                doc_category=qa.get("doc_category"),
                expected_behavior=qa.get("expected_behavior", ""),
            )

            try:
                # Run retrieval evaluation
                if self.config.run_retrieval_eval and self.retrieval_evaluator:
                    retrieval_results = self._evaluate_retrieval(qa, result)
                    result = self._merge_retrieval_results(result, retrieval_results)

                # Run E2E evaluation
                if self.config.run_e2e_eval and self.e2e_evaluator:
                    e2e_results = self._evaluate_e2e(qa, result)
                    result = self._merge_e2e_results(result, e2e_results)

                # Validate expected behavior
                result = self._validate_expected_behavior(qa, result)

            except Exception as e:
                result.has_error = True
                result.error_message = str(e)
                self.logger.error(f"Evaluation error for {qa_id}: {str(e)}")

            return result

    def _evaluate_retrieval(
        self, qa: Dict[str, Any], result: EvaluationResult
    ) -> Dict[str, Any]:
        """Evaluate retrieval performance."""
        if not self.retrieval_evaluator:
            return {}

        start_time = time.time()
        try:
            retrieval_results = self.retrieval_evaluator.evaluate(
                query=qa["query"],
                doc_hints=qa.get("doc_hints", []),
                expected_docs=qa.get("expected_citations", []),
            )
            result.retrieval_latency_ms = (time.time() - start_time) * 1000
            return retrieval_results
        except Exception as e:
            self.logger.error(f"Retrieval evaluation failed for {qa['id']}: {str(e)}")
            return {"error": str(e)}

    def _evaluate_e2e(
        self, qa: Dict[str, Any], result: EvaluationResult
    ) -> Dict[str, Any]:
        """Evaluate end-to-end RAG performance."""
        if not self.e2e_evaluator:
            return {}

        start_time = time.time()
        try:
            e2e_results = self.e2e_evaluator.evaluate(
                query=qa["query"],
                expected_behavior=qa.get("expected_behavior"),
                expected_answer_snippet=qa.get("expected_answer_snippet"),
                context={"doc_category": qa.get("doc_category")},
            )
            result.generation_latency_ms = (time.time() - start_time) * 1000
            result.total_latency_ms = (
                result.retrieval_latency_ms + result.generation_latency_ms
            )
            return e2e_results
        except Exception as e:
            self.logger.error(f"E2E evaluation failed for {qa['id']}: {str(e)}")
            return {"error": str(e)}

    def _merge_retrieval_results(
        self, result: EvaluationResult, retrieval_data: Dict[str, Any]
    ) -> EvaluationResult:
        """Merge retrieval evaluation results."""
        if "error" in retrieval_data:
            result.has_error = True
            result.error_message += f"Retrieval: {retrieval_data['error']}; "
            return result

        result.retrieval_docs = retrieval_data.get("retrieved_docs", [])
        result.retrieval_recall_5 = retrieval_data.get("recall_at_5", 0.0)
        result.retrieval_recall_10 = retrieval_data.get("recall_at_10", 0.0)
        result.retrieval_precision_5 = retrieval_data.get("precision_at_5", 0.0)

        return result

    def _merge_e2e_results(
        self, result: EvaluationResult, e2e_data: Dict[str, Any]
    ) -> EvaluationResult:
        """Merge E2E evaluation results."""
        if "error" in e2e_data:
            result.has_error = True
            result.error_message += f"E2E: {e2e_data['error']}; "
            return result

        result.generated_answer = e2e_data.get("answer", "")
        result.citations = e2e_data.get("citations", [])
        result.citation_rate = e2e_data.get("citation_rate", 0.0)
        result.answer_quality_score = e2e_data.get("answer_quality", 0.0)
        result.cove_verification_score = e2e_data.get("cove_score", 0.0)

        return result

    def _validate_expected_behavior(
        self, qa: Dict[str, Any], result: EvaluationResult
    ) -> EvaluationResult:
        """Validate if result meets expected behavior."""
        expected_behavior = qa.get("expected_behavior", "")

        if not expected_behavior:
            result.expected_behavior_met = True
            return result

        # Check different expected behaviors
        if expected_behavior == "should_not_answer":
            # Negative cases - should have low citation rate and explicit rejection
            result.expected_behavior_met = result.citation_rate < 0.2 and (
                not result.generated_answer
                or any(
                    phrase in result.generated_answer.lower()
                    for phrase in [
                        "không có thông tin",
                        "no information",
                        "cannot answer",
                    ]
                )
            )

        elif expected_behavior == "should_ask_clarification":
            # Ambiguous cases - should ask for clarification
            result.expected_behavior_met = result.generated_answer and any(
                phrase in result.generated_answer.lower()
                for phrase in ["vui lòng làm rõ", "clarification", "which", "specify"]
            )

        elif expected_behavior == "should_provide_value_with_unit":
            # Should have citations and contain unit patterns
            result.expected_behavior_met = (
                result.citation_rate > 0.5
                and result.generated_answer
                and any(
                    unit in result.generated_answer
                    for unit in [
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
                    ]
                )
            )

        elif expected_behavior == "should_provide_location":
            # Should have citations and contain location info
            result.expected_behavior_met = (
                result.citation_rate > 0.5
                and result.generated_answer
                and len(result.generated_answer) > 20
            )

        elif expected_behavior == "should_provide_steps":
            # Procedural - should have multiple steps or clear procedure
            result.expected_behavior_met = (
                result.citation_rate > 0.3
                and result.generated_answer
                and any(
                    phrase in result.generated_answer.lower()
                    for phrase in [
                        "bước",
                        "step",
                        "procedure",
                        "quy trình",
                        "first",
                        "then",
                    ]
                )
            )

        else:
            # Default: should provide specific answer with citations
            result.expected_behavior_met = (
                result.citation_rate > 0.3
                and result.generated_answer
                and len(result.generated_answer) > 10
            )

        return result

    def _aggregate_results(self) -> Dict[str, Any]:
        """Aggregate evaluation results into summary metrics."""
        if not self.results:
            return {}

        total_results = len(self.results)
        successful_results = [r for r in self.results if not r.has_error]

        # Overall metrics
        overall = {
            "total_questions": total_results,
            "successful_evaluations": len(successful_results),
            "failed_evaluations": total_results - len(successful_results),
            "success_rate": len(successful_results) / total_results
            if total_results > 0
            else 0,
        }

        if not successful_results:
            return {"overall": overall}

        # Performance metrics
        retrieval_metrics = self._aggregate_retrieval_metrics(successful_results)
        e2e_metrics = self._aggregate_e2e_metrics(successful_results)
        latency_metrics = self._aggregate_latency_metrics(successful_results)
        behavior_metrics = self._aggregate_behavior_metrics(successful_results)

        # Breakdown by categories
        intent_breakdown = self._aggregate_by_category(successful_results, "intent")
        doc_category_breakdown = self._aggregate_by_category(
            successful_results, "doc_category"
        )

        return {
            "overall": overall,
            "retrieval": retrieval_metrics,
            "e2e": e2e_metrics,
            "latency": latency_metrics,
            "behavior_validation": behavior_metrics,
            "breakdown_by_intent": intent_breakdown,
            "breakdown_by_doc_category": doc_category_breakdown,
        }

    def _aggregate_retrieval_metrics(
        self, results: List[EvaluationResult]
    ) -> Dict[str, float]:
        """Aggregate retrieval metrics."""
        if not results:
            return {}

        recall_5_scores = [
            r.retrieval_recall_5 for r in results if r.retrieval_recall_5 is not None
        ]
        recall_10_scores = [
            r.retrieval_recall_10 for r in results if r.retrieval_recall_10 is not None
        ]
        precision_5_scores = [
            r.retrieval_precision_5
            for r in results
            if r.retrieval_precision_5 is not None
        ]

        return {
            "avg_recall_at_5": sum(recall_5_scores) / len(recall_5_scores)
            if recall_5_scores
            else 0,
            "avg_recall_at_10": sum(recall_10_scores) / len(recall_10_scores)
            if recall_10_scores
            else 0,
            "avg_precision_at_5": sum(precision_5_scores) / len(precision_5_scores)
            if precision_5_scores
            else 0,
            "questions_with_retrieval": len(recall_5_scores),
        }

    def _aggregate_e2e_metrics(
        self, results: List[EvaluationResult]
    ) -> Dict[str, float]:
        """Aggregate end-to-end metrics."""
        if not results:
            return {}

        citation_rates = [
            r.citation_rate for r in results if r.citation_rate is not None
        ]
        quality_scores = [
            r.answer_quality_score
            for r in results
            if r.answer_quality_score is not None
        ]
        cove_scores = [
            r.cove_verification_score
            for r in results
            if r.cove_verification_score is not None
        ]

        return {
            "avg_citation_rate": sum(citation_rates) / len(citation_rates)
            if citation_rates
            else 0,
            "avg_answer_quality": sum(quality_scores) / len(quality_scores)
            if quality_scores
            else 0,
            "avg_cove_score": sum(cove_scores) / len(cove_scores) if cove_scores else 0,
            "questions_with_answers": len([r for r in results if r.generated_answer]),
        }

    def _aggregate_latency_metrics(
        self, results: List[EvaluationResult]
    ) -> Dict[str, float]:
        """Aggregate latency metrics."""
        if not results:
            return {}

        retrieval_latencies = [
            r.retrieval_latency_ms for r in results if r.retrieval_latency_ms > 0
        ]
        generation_latencies = [
            r.generation_latency_ms for r in results if r.generation_latency_ms > 0
        ]
        total_latencies = [
            r.total_latency_ms for r in results if r.total_latency_ms > 0
        ]

        return {
            "avg_retrieval_latency_ms": sum(retrieval_latencies)
            / len(retrieval_latencies)
            if retrieval_latencies
            else 0,
            "avg_generation_latency_ms": sum(generation_latencies)
            / len(generation_latencies)
            if generation_latencies
            else 0,
            "avg_total_latency_ms": sum(total_latencies) / len(total_latencies)
            if total_latencies
            else 0,
            "p95_total_latency_ms": self._percentile(total_latencies, 95)
            if total_latencies
            else 0,
            "p99_total_latency_ms": self._percentile(total_latencies, 99)
            if total_latencies
            else 0,
        }

    def _aggregate_behavior_metrics(
        self, results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """Aggregate expected behavior validation metrics."""
        if not results:
            return {}

        behavior_met = [r for r in results if r.expected_behavior_met]

        return {
            "total_validations": len(results),
            "behaviors_met": len(behavior_met),
            "behavior_compliance_rate": len(behavior_met) / len(results)
            if results
            else 0,
        }

    def _aggregate_by_category(
        self, results: List[EvaluationResult], category_field: str
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate metrics by category (intent or doc_category)."""
        from collections import defaultdict

        category_results = defaultdict(list)
        for result in results:
            category_value = getattr(result, category_field, "unknown")
            if category_value:
                category_results[category_value].append(result)

        breakdown = {}
        for category, cat_results in category_results.items():
            if cat_results:
                breakdown[category] = {
                    "count": len(cat_results),
                    "success_rate": len([r for r in cat_results if not r.has_error])
                    / len(cat_results),
                    "avg_citation_rate": sum(r.citation_rate for r in cat_results)
                    / len(cat_results),
                    "avg_total_latency_ms": sum(r.total_latency_ms for r in cat_results)
                    / len(cat_results),
                    "behavior_compliance_rate": len(
                        [r for r in cat_results if r.expected_behavior_met]
                    )
                    / len(cat_results),
                }

        return breakdown

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    async def _generate_reports(self, metrics: Dict[str, Any]) -> Dict[str, Path]:
        """Generate evaluation reports."""
        report_paths = {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # CSV summary export (aggregated metrics + breakdowns)
        try:
            import csv

            csv_path = self.config.output_dir / f"evaluation_summary_{timestamp}.csv"
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["section", "metric", "value"])
                # Overall
                overall = metrics.get("overall", {})
                for k, v in overall.items():
                    writer.writerow(["overall", k, v])
                # Retrieval
                retrieval = metrics.get("retrieval", {})
                for k, v in retrieval.items():
                    writer.writerow(["retrieval", k, v])
                # E2E
                e2e = metrics.get("e2e", {})
                for k, v in e2e.items():
                    writer.writerow(["e2e", k, v])
                # Latency
                latency = metrics.get("latency", {})
                for k, v in latency.items():
                    writer.writerow(["latency", k, v])
                # Behavior validation
                behavior = metrics.get("behavior_validation", {})
                for k, v in behavior.items():
                    writer.writerow(["behavior", k, v])
                # Breakdown by intent
                for intent, data in (
                    metrics.get("breakdown_by_intent", {}) or {}
                ).items():
                    for k, v in data.items():
                        writer.writerow([f"intent:{intent}", k, v])
                # Breakdown by doc category
                for doc_cat, data in (
                    metrics.get("breakdown_by_doc_category", {}) or {}
                ).items():
                    for k, v in data.items():
                        writer.writerow([f"doc:{doc_cat}", k, v])
            report_paths["csv"] = csv_path
            self.logger.info(f"📄 CSV summary saved: {csv_path}")
        except Exception as e:
            self.logger.error(f"Failed to write CSV summary: {e}")

        # JSON report
        if self.config.generate_json_report:
            json_path = self.config.output_dir / f"evaluation_report_{timestamp}.json"
            # Convert config to serializable dict
            config_dict = asdict(self.config)
            # Convert Path objects to strings
            config_dict["qa_file"] = str(config_dict["qa_file"])
            config_dict["output_dir"] = str(config_dict["output_dir"])

            report_data = {
                "config": config_dict,
                "metrics": metrics,
                "individual_results": [r.to_dict() for r in self.results]
                if self.config.save_individual_results
                else [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)

            report_paths["json"] = json_path
            self.logger.info(f"📄 JSON report saved: {json_path}")

        # HTML report
        if self.config.generate_html_report:
            from app.evaluation.report_generator import HTMLReportGenerator

            html_generator = HTMLReportGenerator()
            html_path = await html_generator.generate_report(
                metrics=metrics,
                results=self.results,
                config=self.config,
                output_path=self.config.output_dir
                / f"evaluation_report_{timestamp}.html",
            )
            report_paths["html"] = html_path

        return report_paths
