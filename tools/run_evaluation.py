#!/usr/bin/env python3
"""
CLI Interface for Batch Evaluation Runner
Provides command-line interface to run comprehensive RAG evaluation.
"""
import argparse
import asyncio
import json

# Add project root to path
import os
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger

from app.evaluation.batch_runner import BatchEvaluationRunner, EvaluationConfig


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = "DEBUG" if verbose else "INFO"
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )


def validate_files(qa_file: Path, output_dir: Path) -> bool:
    """Validate input files and output directory."""
    if not qa_file.exists():
        logger.error(f"QA file not found: {qa_file}")
        return False

    if not qa_file.suffix == ".jsonl":
        logger.warning(f"QA file should be JSONL format: {qa_file}")

    # Test if QA file is readable and valid
    try:
        with open(qa_file, "r", encoding="utf-8") as f:
            first_line = f.readline()
            if first_line.strip():
                json.loads(first_line)
        logger.info(f"✓ QA file validated: {qa_file}")
    except Exception as e:
        logger.error(f"Invalid QA file format: {e}")
        return False

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Output directory ready: {output_dir}")

    return True


def preview_qa_dataset(qa_file: Path, preview_count: int = 5):
    """Preview QA dataset content."""
    logger.info(f"📋 Previewing first {preview_count} questions from {qa_file.name}")

    try:
        with open(qa_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= preview_count:
                    break

                qa = json.loads(line)
                qa_id = qa.get("id", "N/A")
                query = qa.get("query", "N/A")
                intent = qa.get("intent", "N/A")
                doc_category = qa.get("doc_category", "N/A")

                print(f"  {i+1}. [{qa_id}] {query[:60]}...")
                print(f"     Intent: {intent}, Doc Category: {doc_category}")
                print()

    except Exception as e:
        logger.error(f"Failed to preview QA dataset: {e}")


def run_dry_run(config: EvaluationConfig) -> bool:
    """Run dry run validation."""
    logger.info("🧪 Running dry run validation...")

    try:
        # Load and validate QA data
        with open(config.qa_file, "r", encoding="utf-8") as f:
            qa_count = sum(1 for _ in f)

        if config.sample_size and config.sample_size < qa_count:
            logger.info(f"📊 Will sample {config.sample_size} from {qa_count} questions")
        else:
            logger.info(f"📊 Will evaluate all {qa_count} questions")

        # Validate configuration
        logger.info(f"🔧 Evaluation modes:")
        logger.info(f"  - Retrieval evaluation: {config.run_retrieval_eval}")
        logger.info(f"  - E2E evaluation: {config.run_e2e_eval}")
        logger.info(f"  - Citation evaluation: {config.run_citation_eval}")
        logger.info(f"  - Latency evaluation: {config.run_latency_eval}")

        logger.info(f"⚙️  Processing config:")
        logger.info(f"  - Max workers: {config.max_workers}")
        logger.info(f"  - Batch size: {config.batch_size}")
        logger.info(f"  - Timeout: {config.timeout_seconds}s")

        logger.info(f"📂 Output config:")
        logger.info(f"  - Output directory: {config.output_dir}")
        logger.info(f"  - Generate HTML report: {config.generate_html_report}")
        logger.info(f"  - Generate JSON report: {config.generate_json_report}")
        logger.info(f"  - Save individual results: {config.save_individual_results}")

        if config.retrieval_endpoint:
            logger.info(f"🔗 Retrieval endpoint: {config.retrieval_endpoint}")
        else:
            logger.info("🔗 Retrieval: Simulation mode")

        if config.rag_endpoint:
            logger.info(f"🔗 RAG endpoint: {config.rag_endpoint}")
        else:
            logger.info("🔗 RAG: Simulation mode")

        logger.success("✅ Dry run validation passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Dry run validation failed: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Run comprehensive RAG evaluation on QA datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run evaluation on Golden QA with default settings
  python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl

  # Run with custom output directory and sample size
  python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl \\
    --output-dir results/evaluation_20241215 --sample-size 20

  # Run with real API endpoints
  python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl \\
    --retrieval-endpoint http://localhost:8001/retrieve \\
    --rag-endpoint http://localhost:8002/generate

  # Preview dataset and run dry run
  python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl \\
    --preview --dry-run

  # Run only retrieval evaluation with high concurrency
  python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl \\
    --no-e2e --max-workers 8 --batch-size 20
        """,
    )

    # Positional arguments
    parser.add_argument(
        "qa_file", type=Path, help="Path to QA dataset file (JSONL format)"
    )

    # Output configuration
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("artifacts/eval"),
        help="Output directory for evaluation results (default: artifacts/eval)",
    )

    # Evaluation modes
    parser.add_argument(
        "--no-retrieval", action="store_true", help="Skip retrieval evaluation"
    )
    parser.add_argument(
        "--no-e2e", action="store_true", help="Skip end-to-end evaluation"
    )
    parser.add_argument(
        "--no-citation", action="store_true", help="Skip citation evaluation"
    )
    parser.add_argument(
        "--no-latency", action="store_true", help="Skip latency evaluation"
    )

    # Processing configuration
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of worker threads (default: 4)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for processing (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for each evaluation (default: 60)",
    )

    # Sampling configuration
    parser.add_argument(
        "--sample-size",
        type=int,
        help="Number of questions to sample (default: all questions)",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for sampling (default: 42)",
    )

    # Output options
    parser.add_argument(
        "--no-html", action="store_true", help="Don't generate HTML report"
    )
    parser.add_argument(
        "--no-json", action="store_true", help="Don't generate JSON report"
    )
    parser.add_argument(
        "--no-individual-results",
        action="store_true",
        help="Don't save individual QA results",
    )

    # API endpoints
    parser.add_argument(
        "--retrieval-endpoint",
        type=str,
        help="Retrieval API endpoint URL (default: simulation mode)",
    )
    parser.add_argument(
        "--rag-endpoint",
        type=str,
        help="RAG API endpoint URL (default: simulation mode)",
    )

    # Utility options
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview QA dataset before running evaluation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without running evaluation",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    logger.info("🚀 RAG Evaluation CLI")
    logger.info(f"📁 QA Dataset: {args.qa_file}")

    # Validate input files
    if not validate_files(args.qa_file, args.output_dir):
        sys.exit(1)

    # Preview dataset if requested
    if args.preview:
        preview_qa_dataset(args.qa_file)
        print()

    # Create evaluation configuration
    config = EvaluationConfig(
        qa_file=args.qa_file,
        output_dir=args.output_dir,
        # Evaluation modes
        run_retrieval_eval=not args.no_retrieval,
        run_e2e_eval=not args.no_e2e,
        run_citation_eval=not args.no_citation,
        run_latency_eval=not args.no_latency,
        # Processing config
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        timeout_seconds=args.timeout,
        # Sampling config
        sample_size=args.sample_size,
        random_seed=args.random_seed,
        # Output config
        generate_html_report=not args.no_html,
        generate_json_report=not args.no_json,
        save_individual_results=not args.no_individual_results,
        # API endpoints
        retrieval_endpoint=args.retrieval_endpoint,
        rag_endpoint=args.rag_endpoint,
    )

    # Run dry run if requested
    if args.dry_run:
        if run_dry_run(config):
            logger.success("✅ Configuration validated successfully!")
        else:
            sys.exit(1)
        return

    # Run evaluation
    try:
        logger.info("🎯 Starting batch evaluation...")
        runner = BatchEvaluationRunner(config)

        result = await runner.run_evaluation()

        if result["status"] == "completed":
            logger.success(f"🎉 Evaluation completed successfully!")
            logger.info(f"⏱️  Total time: {result['total_time_seconds']:.2f}s")
            logger.info(f"📊 Questions processed: {result['questions_processed']}")

            # Show key metrics
            metrics = result["aggregated_metrics"]
            if "overall" in metrics:
                overall = metrics["overall"]
                logger.info(f"📈 Success rate: {overall.get('success_rate', 0):.1%}")

            if "retrieval" in metrics and metrics["retrieval"]:
                retrieval = metrics["retrieval"]
                logger.info(
                    f"🔍 Avg Recall@5: {retrieval.get('avg_recall_at_5', 0):.3f}"
                )

            if "e2e" in metrics and metrics["e2e"]:
                e2e = metrics["e2e"]
                logger.info(
                    f"📝 Avg Citation Rate: {e2e.get('avg_citation_rate', 0):.3f}"
                )
                logger.info(
                    f"🎯 Avg Answer Quality: {e2e.get('avg_answer_quality', 0):.3f}"
                )

            if "latency" in metrics and metrics["latency"]:
                latency = metrics["latency"]
                logger.info(
                    f"⚡ Avg Latency: {latency.get('avg_total_latency_ms', 0):.0f}ms"
                )

            # Show report paths
            report_paths = result.get("report_paths", {})
            if report_paths:
                logger.info(f"📊 Reports generated:")
                for format_type, path in report_paths.items():
                    logger.info(f"  - {format_type.upper()}: {path}")
        else:
            logger.error("❌ Evaluation failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("⏸️  Evaluation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Evaluation failed with error: {e}")
        if args.verbose:
            logger.exception("Full error details:")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
