#!/usr/bin/env python
"""
Batch Query Runner for BGE Reranking Evaluation

Sends multiple queries to the API and captures results with timing info.
Used to evaluate different reranking configurations.

Usage:
    python tools/batch_query_runner.py --input artifacts/qa/filtered_qa_set.jsonl --output artifacts/eval/run_baseline.jsonl --limit 30
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class BatchQueryRunner:
    """Run multiple queries against the API and capture results"""

    def __init__(
        self,
        api_url: str = "http://localhost:8000/ask",
        timeout: int = 120,
    ):
        self.api_url = api_url
        self.timeout = timeout

    def run_single_query(
        self,
        query: str,
        query_id: str = "unknown",
        max_context: int = 10,
        hyde: bool = True,
        execution_mode: str = "heavy_only",
        enable_vision: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a single query and capture results + timing

        Returns:
            Dict with query, response, timing, and metadata
        """
        payload = {
            "query": query,
            "language": "vi",
            "max_context": max_context,
            "hyde": hyde,
            "execution_mode": execution_mode,
            "confidence_mode": "calibrated",
            "enable_vision_generation": enable_vision,
        }

        start_time = time.time()

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            elapsed_ms = (time.time() - start_time) * 1000

            result = response.json()

            # Extract timing info from response metadata if available
            metadata = result.get("metadata", {})
            timing_info = metadata.get("timing", {})

            return {
                "query_id": query_id,
                "query": query,
                "success": True,
                "answer": result.get("answer", ""),
                "citations": result.get("citations", []),
                "confidence": result.get("confidence", 0.0),
                "timing": {
                    "total_ms": elapsed_ms,
                    "retrieval_ms": timing_info.get("retrieval_ms"),
                    "rerank_ms": timing_info.get("rerank_ms"),
                    "generation_ms": timing_info.get("generation_ms"),
                },
                "retrieval_info": {
                    "num_retrieved": len(result.get("retrieved_docs", [])),
                    "num_citations": len(result.get("citations", [])),
                    "rerank_method": metadata.get("rerank_method"),
                },
                "metadata": metadata,
            }

        except requests.exceptions.Timeout:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Query {query_id} timed out after {elapsed_ms:.0f}ms")
            return {
                "query_id": query_id,
                "query": query,
                "success": False,
                "error": "timeout",
                "timing": {"total_ms": elapsed_ms},
            }

        except requests.exceptions.ConnectionError:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Query {query_id} failed: connection error")
            return {
                "query_id": query_id,
                "query": query,
                "success": False,
                "error": "connection_error",
                "timing": {"total_ms": elapsed_ms},
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Query {query_id} failed: {e}")
            return {
                "query_id": query_id,
                "query": query,
                "success": False,
                "error": str(e),
                "timing": {"total_ms": elapsed_ms},
            }

    def run_batch(
        self,
        queries: List[Dict[str, Any]],
        output_path: Path,
        max_context: int = 10,
        hyde: bool = True,
        execution_mode: str = "heavy_only",
        enable_vision: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Run a batch of queries and save results incrementally

        Args:
            queries: List of query dicts with 'id' and 'query' fields
            output_path: Path to save results (JSONL)
            max_context: Number of context chunks
            hyde: Enable HyDE
            execution_mode: Execution mode
            enable_vision: Enable vision generation

        Returns:
            List of result dicts
        """
        results = []
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Open output file for incremental writes
        with output_path.open("w", encoding="utf-8") as f:
            for i, q in enumerate(queries, 1):
                query_id = q.get("id", f"Q{i:04d}")
                query_text = q.get("query", "")

                logger.info(f"[{i}/{len(queries)}] Running query {query_id}...")

                result = self.run_single_query(
                    query=query_text,
                    query_id=query_id,
                    max_context=max_context,
                    hyde=hyde,
                    execution_mode=execution_mode,
                    enable_vision=enable_vision,
                )

                # Add ground truth info if available
                if "expected_citations" in q and q["expected_citations"]:
                    result["ground_truth"] = q["expected_citations"]
                if "doc_hints" in q and q["doc_hints"]:
                    result["doc_hints"] = q["doc_hints"]

                # Save metadata from original query
                result["original_metadata"] = {
                    "difficulty": q.get("difficulty"),
                    "category": q.get("category"),
                    "type": q.get("type"),
                }

                results.append(result)

                # Write incrementally
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()

                # Log timing
                total_ms = result["timing"]["total_ms"]
                if result["success"]:
                    logger.info(
                        f"  ✓ Success ({total_ms:.0f}ms) - "
                        f"{result['retrieval_info']['num_citations']} citations"
                    )
                else:
                    logger.error(
                        f"  ✗ Failed ({total_ms:.0f}ms) - {result.get('error')}"
                    )

        logger.info(f"\n✅ Batch complete: {len(results)} queries processed")
        logger.info(f"📄 Results saved to: {output_path}")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Run batch queries for BGE reranking evaluation"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input JSONL file with queries",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output JSONL file for results",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000/ask",
        help="API endpoint URL",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of queries to run (for testing)",
    )
    parser.add_argument(
        "--max-context",
        type=int,
        default=10,
        help="Max context chunks",
    )
    parser.add_argument(
        "--no-hyde",
        action="store_true",
        help="Disable HyDE query expansion",
    )
    parser.add_argument(
        "--execution-mode",
        type=str,
        default="heavy_only",
        choices=["light_only", "heavy_only", "both"],
        help="Execution mode",
    )
    parser.add_argument(
        "--enable-vision",
        action="store_true",
        help="Enable vision generation",
    )

    args = parser.parse_args()

    # Load queries
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info(f"Loading queries from: {input_path}")
    queries = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    if args.limit:
        queries = queries[: args.limit]
        logger.info(f"Limited to first {args.limit} queries")

    logger.info(f"Loaded {len(queries)} queries")

    # Create runner
    runner = BatchQueryRunner(api_url=args.api_url)

    # Run batch
    logger.info("\n" + "=" * 80)
    logger.info("BATCH QUERY EXECUTION")
    logger.info("=" * 80)
    logger.info(f"API URL: {args.api_url}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Max context: {args.max_context}")
    logger.info(f"HyDE: {not args.no_hyde}")
    logger.info(f"Execution mode: {args.execution_mode}")
    logger.info(f"Vision: {args.enable_vision}")
    logger.info("=" * 80 + "\n")

    output_path = Path(args.output)

    results = runner.run_batch(
        queries=queries,
        output_path=output_path,
        max_context=args.max_context,
        hyde=not args.no_hyde,
        execution_mode=args.execution_mode,
        enable_vision=args.enable_vision,
    )

    # Quick summary
    success_count = sum(1 for r in results if r["success"])
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total queries: {len(results)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(results) - success_count}")

    # Timing stats (successful queries only)
    successful_results = [r for r in results if r["success"]]
    if successful_results:
        timings = [r["timing"]["total_ms"] for r in successful_results]
        timings.sort()
        p50 = timings[len(timings) // 2]
        p95 = timings[int(len(timings) * 0.95)]
        avg = sum(timings) / len(timings)

        logger.info(f"\nLatency (successful queries):")
        logger.info(f"  Mean: {avg:.0f}ms")
        logger.info(f"  P50:  {p50:.0f}ms")
        logger.info(f"  P95:  {p95:.0f}ms")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
