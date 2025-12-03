"""
Page Reranking Benchmark Suite

Measures performance and accuracy of page reranking with different configurations:
- BM25-only (no semantic, no caching)
- Hybrid (BM25 + semantic, no caching)
- Hybrid + Caching
- Hybrid + Caching + Validation

Metrics tracked:
- Latency: p50, p90, p95, p99 per stage
- Accuracy: page@1, page@3, page@5 accuracy
- Cache: hit rate, latency reduction
- Validation: confidence scores, filter rate

Usage:
    python tools/benchmarks/page_rerank_bench.py --mode all --queries 50 --output results.csv
"""

import argparse
import csv
import json
import statistics
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# Import components to benchmark
try:
    from app.config import get_config
    from app.rag.citation_retriever import CitationRetriever, SearchConfig
    from app.rag.page_reranker import PageReranker, get_page_reranker

    _imports_available = True
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    _imports_available = False


@dataclass
class BenchmarkQuery:
    """Test query with optional gold answer"""

    query: str
    doc_id: str
    gold_page: Optional[int] = None  # Expected correct page
    gold_pages: List[int] = field(default_factory=list)  # All relevant pages


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run"""

    query: str
    mode: str  # "bm25", "hybrid", "hybrid+cache", "hybrid+cache+validation"

    # Latency metrics (milliseconds)
    total_latency_ms: float = 0.0
    bm25_latency_ms: float = 0.0
    semantic_latency_ms: float = 0.0
    validation_latency_ms: float = 0.0

    # Results
    top_pages: List[int] = field(default_factory=list)
    top_scores: List[float] = field(default_factory=list)

    # Accuracy (if gold available)
    page_1_correct: Optional[bool] = None
    page_3_correct: Optional[bool] = None
    page_5_correct: Optional[bool] = None

    # Cache stats
    cache_hit: Optional[bool] = None

    # Validation stats
    validation_confidence: Optional[float] = None
    validation_filtered: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class PageRerankBenchmark:
    """Main benchmark runner"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize benchmark

        Args:
            config_path: Optional path to config file
        """
        if not _imports_available:
            raise RuntimeError("Required modules not available")

        self.config = get_config()
        self.results: List[BenchmarkResult] = []

        # Load test queries
        self.test_queries = self._load_test_queries()

        logger.info(f"Benchmark initialized with {len(self.test_queries)} test queries")

    def _load_test_queries(self) -> List[BenchmarkQuery]:
        """Load or generate test queries"""
        queries = []

        # Try to load from file
        queries_file = Path("tools/benchmarks/test_queries.json")
        if queries_file.exists():
            try:
                with open(queries_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        queries.append(BenchmarkQuery(**item))
                logger.info(f"Loaded {len(queries)} queries from {queries_file}")
                return queries
            except Exception as e:
                logger.warning(f"Failed to load queries file: {e}")

        # Generate synthetic queries if no file
        logger.info("Generating synthetic test queries")
        queries = self._generate_synthetic_queries()

        return queries

    def _generate_synthetic_queries(self) -> List[BenchmarkQuery]:
        """Generate synthetic test queries from available docs"""
        queries = []

        # Try to load doc_id_map
        try:
            doc_map_path = Path("artifacts/ingestion_production/doc_id_map.json")
            if not doc_map_path.exists():
                doc_map_path = Path("artifacts/ingestion/doc_id_map.json")

            if doc_map_path.exists():
                with open(doc_map_path, "r", encoding="utf-8") as f:
                    doc_map = json.load(f)

                # Sample queries for first few docs
                doc_ids = list(doc_map.keys())[:10]  # First 10 docs

                query_templates = [
                    "What is the operating temperature?",
                    "What are the specifications?",
                    "What is the maximum pressure?",
                    "What are the safety requirements?",
                    "What is the installation procedure?",
                ]

                for doc_id in doc_ids:
                    for template in query_templates[:2]:  # 2 queries per doc
                        queries.append(
                            BenchmarkQuery(
                                query=template, doc_id=doc_id, gold_page=None  # Unknown
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to generate queries: {e}")

        return queries

    def run_benchmark(
        self,
        modes: List[str],
        num_queries: Optional[int] = None,
    ) -> List[BenchmarkResult]:
        """
        Run benchmark with specified modes

        Args:
            modes: List of modes to test ["bm25", "hybrid", "hybrid+cache", "hybrid+cache+validation"]
            num_queries: Number of queries to test (None = all)

        Returns:
            List of benchmark results
        """
        test_queries = (
            self.test_queries[:num_queries] if num_queries else self.test_queries
        )

        logger.info(f"Running benchmark: modes={modes}, queries={len(test_queries)}")

        results = []

        for mode in modes:
            logger.info(f"\\n{'='*60}")
            logger.info(f"Testing mode: {mode}")
            logger.info(f"{'='*60}")

            for i, query_obj in enumerate(test_queries, 1):
                logger.info(f"Query {i}/{len(test_queries)}: {query_obj.query[:50]}...")

                result = self._run_single_query(query_obj, mode)
                results.append(result)

                # Log intermediate stats every 10 queries
                if i % 10 == 0:
                    self._log_intermediate_stats(results, mode)

        self.results = results
        return results

    def _run_single_query(
        self,
        query_obj: BenchmarkQuery,
        mode: str,
    ) -> BenchmarkResult:
        """Run benchmark for a single query"""
        result = BenchmarkResult(
            query=query_obj.query,
            mode=mode,
        )

        start_total = time.time()

        try:
            if mode == "bm25":
                # BM25 only - no semantic, no caching
                result = self._benchmark_bm25_only(query_obj, result)

            elif mode == "hybrid":
                # Hybrid (BM25 + semantic) - no caching
                result = self._benchmark_hybrid(query_obj, result, use_cache=False)

            elif mode == "hybrid+cache":
                # Hybrid with caching
                result = self._benchmark_hybrid(query_obj, result, use_cache=True)

            elif mode == "hybrid+cache+validation":
                # Full pipeline with validation
                result = self._benchmark_full_pipeline(query_obj, result)

            else:
                logger.error(f"Unknown mode: {mode}")

        except Exception as e:
            logger.error(f"Benchmark failed for query '{query_obj.query}': {e}")
            result.total_latency_ms = -1  # Mark as failed

        # Calculate total latency
        result.total_latency_ms = (time.time() - start_total) * 1000

        # Calculate accuracy if gold available
        if query_obj.gold_page:
            result.page_1_correct = (
                (result.top_pages[0] == query_obj.gold_page)
                if result.top_pages
                else False
            )
            result.page_3_correct = (
                (query_obj.gold_page in result.top_pages[:3])
                if len(result.top_pages) >= 3
                else False
            )
            result.page_5_correct = (
                (query_obj.gold_page in result.top_pages[:5])
                if len(result.top_pages) >= 5
                else False
            )

        return result

    def _benchmark_bm25_only(
        self,
        query_obj: BenchmarkQuery,
        result: BenchmarkResult,
    ) -> BenchmarkResult:
        """Benchmark BM25-only mode"""
        # Create reranker without semantic
        import os

        os.environ["ENABLE_PAGE_SEMANTIC"] = "false"
        os.environ["ENABLE_PAGE_RANK_CACHE"] = "false"

        reranker = PageReranker()

        start = time.time()
        pages = reranker.rank_pages_for_doc(
            query=query_obj.query,
            doc_id=query_obj.doc_id,
            top_k=5,
        )
        result.bm25_latency_ms = (time.time() - start) * 1000

        result.top_pages = [p for p, _ in pages]
        result.top_scores = [s for _, s in pages]

        return result

    def _benchmark_hybrid(
        self,
        query_obj: BenchmarkQuery,
        result: BenchmarkResult,
        use_cache: bool,
    ) -> BenchmarkResult:
        """Benchmark hybrid mode (BM25 + semantic)"""
        import os

        os.environ["ENABLE_PAGE_SEMANTIC"] = "true"
        os.environ["ENABLE_PAGE_RANK_CACHE"] = "true" if use_cache else "false"

        reranker = PageReranker()

        # Clear cache for fair comparison
        if not use_cache and reranker._rank_cache:
            reranker.clear_caches()

        start = time.time()
        pages = reranker.rank_pages_for_doc(
            query=query_obj.query,
            doc_id=query_obj.doc_id,
            top_k=5,
        )
        latency = (time.time() - start) * 1000

        result.bm25_latency_ms = latency  # Combined for now
        result.semantic_latency_ms = 0  # Not separated

        result.top_pages = [p for p, _ in pages]
        result.top_scores = [s for _, s in pages]

        # Check cache stats
        if use_cache and reranker._rank_cache:
            stats = reranker.get_cache_stats()
            total_accesses = stats["rank_cache"]["hits"] + stats["rank_cache"]["misses"]
            result.cache_hit = (
                (stats["rank_cache"]["hits"] > 0) if total_accesses > 0 else False
            )

        return result

    def _benchmark_full_pipeline(
        self,
        query_obj: BenchmarkQuery,
        result: BenchmarkResult,
    ) -> BenchmarkResult:
        """Benchmark full pipeline with validation"""
        import os

        os.environ["ENABLE_PAGE_SEMANTIC"] = "true"
        os.environ["ENABLE_PAGE_RANK_CACHE"] = "true"

        # Use CitationRetriever with validation
        retriever = CitationRetriever()

        config = SearchConfig(
            top_k_docs=1,
            top_k_pages_per_doc=5,
            enable_validation=True,
            validation_level=2,
            min_confidence_threshold=0.7,
            filter_invalid_citations=False,
        )

        start = time.time()
        citations = retriever.search_with_citations(
            query=query_obj.query,
            doc_ids=[query_obj.doc_id],
            config_override=config,
        )
        total_time = (time.time() - start) * 1000

        result.bm25_latency_ms = total_time  # Simplified

        result.top_pages = [c.page for c in citations]
        result.top_scores = [c.score for c in citations]

        # Validation stats
        if citations and "validation" in citations[0].metadata:
            val = citations[0].metadata["validation"]
            result.validation_confidence = val.get("confidence", 0.0)
            result.validation_filtered = not val.get("is_valid", True)

        return result

    def _log_intermediate_stats(self, results: List[BenchmarkResult], mode: str):
        """Log intermediate statistics"""
        mode_results = [r for r in results if r.mode == mode]

        if not mode_results:
            return

        latencies = [r.total_latency_ms for r in mode_results if r.total_latency_ms > 0]

        if latencies:
            logger.info(
                f"  Latency stats (n={len(latencies)}): "
                f"p50={statistics.median(latencies):.1f}ms, "
                f"p90={statistics.quantiles(latencies, n=10)[8]:.1f}ms"
            )

    def generate_report(self, output_path: Path):
        """Generate benchmark report"""
        logger.info(f"Generating report: {output_path}")

        # Write CSV
        if self.results:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.results[0].to_dict().keys())
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result.to_dict())

        # Generate summary
        summary_path = output_path.with_suffix(".summary.txt")
        self._generate_summary(summary_path)

        logger.info(f"Report saved: {output_path}")
        logger.info(f"Summary saved: {summary_path}")

    def _generate_summary(self, summary_path: Path):
        """Generate text summary"""
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\\n")
            f.write("Page Reranking Benchmark Summary\\n")
            f.write("=" * 60 + "\\n\\n")

            # Group by mode
            by_mode = defaultdict(list)
            for r in self.results:
                by_mode[r.mode].append(r)

            for mode, results in by_mode.items():
                f.write(f"\\nMode: {mode}\\n")
                f.write("-" * 40 + "\\n")

                latencies = [
                    r.total_latency_ms for r in results if r.total_latency_ms > 0
                ]

                if latencies:
                    f.write(f"Queries: {len(latencies)}\\n")
                    f.write(f"Latency p50: {statistics.median(latencies):.2f}ms\\n")
                    if len(latencies) >= 10:
                        f.write(
                            f"Latency p90: {statistics.quantiles(latencies, n=10)[8]:.2f}ms\\n"
                        )
                    f.write(f"Latency avg: {statistics.mean(latencies):.2f}ms\\n")
                    f.write(f"Latency min: {min(latencies):.2f}ms\\n")
                    f.write(f"Latency max: {max(latencies):.2f}ms\\n")

                # Accuracy stats
                page1_correct = [
                    r
                    for r in results
                    if r.page_1_correct is not None and r.page_1_correct
                ]
                page3_correct = [
                    r
                    for r in results
                    if r.page_3_correct is not None and r.page_3_correct
                ]

                if page1_correct or page3_correct:
                    f.write(f"\\nAccuracy:\\n")
                    total_with_gold = len(
                        [r for r in results if r.page_1_correct is not None]
                    )
                    if total_with_gold > 0:
                        f.write(
                            f"  Page@1: {len(page1_correct) / total_with_gold:.1%}\\n"
                        )
                        f.write(
                            f"  Page@3: {len(page3_correct) / total_with_gold:.1%}\\n"
                        )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Page reranking benchmark")
    parser.add_argument(
        "--mode",
        type=str,
        default="all",
        choices=["all", "bm25", "hybrid", "hybrid+cache", "hybrid+cache+validation"],
        help="Benchmark mode",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=None,
        help="Number of queries to test (default: all)",
    )
    parser.add_argument(
        "--output", type=str, default="benchmark_results.csv", help="Output CSV file"
    )

    args = parser.parse_args()

    # Determine modes
    if args.mode == "all":
        modes = ["bm25", "hybrid", "hybrid+cache", "hybrid+cache+validation"]
    else:
        modes = [args.mode]

    # Run benchmark
    benchmark = PageRerankBenchmark()
    benchmark.run_benchmark(modes=modes, num_queries=args.queries)

    # Generate report
    output_path = Path(args.output)
    benchmark.generate_report(output_path)

    logger.info("Benchmark complete!")


if __name__ == "__main__":
    main()
