"""
Batch Test Script for Technical Document Questions
===================================================
Đọc file Demo questions.json và chạy từng câu hỏi qua pipeline Technical Doc.
Lưu kết quả (answer + citations) vào file JSON output.

Usage:
    python scripts/evaluation/batch_test_technical_docs.py
    python scripts/evaluation/batch_test_technical_docs.py --input "Demo questions.json" --output "results.json"
    python scripts/evaluation/batch_test_technical_docs.py --start 1 --end 10  # Chỉ chạy STT 1-10
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from loguru import logger

# Default configuration
DEFAULT_INPUT_FILE = "Demo questions.json"
DEFAULT_OUTPUT_FILE = "evaluation_results_{timestamp}.json"
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 300  # 5 minutes (matching STREAMLIT_TIMEOUT)


def load_questions(input_file: str) -> list[dict]:
    """Load questions from JSON file and extract STT + question."""
    logger.info(f"Loading questions from: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = []
    for item in data:
        stt = item.get("STT")
        interactions = item.get("interaction", [])

        if interactions and len(interactions) > 0:
            question = interactions[0].get("question", "")
            if question:
                questions.append({"stt": stt, "question": question})

    logger.info(f"Loaded {len(questions)} questions")
    return questions


def call_ask_api(
    question: str, max_context: int = 30, api_url: str = None
) -> dict[str, Any]:
    """
    Call /ask API endpoint with technical_doc query type.

    Returns:
        dict with keys: answer, citations, confidence, latency_ms, error
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/ask"

    payload = {
        "query": question,
        "query_type": "technical_doc",  # NOT P&ID
        "language": "vi",
        "max_context": max_context,
        "enable_vision_generation": True,
    }

    start_time = time.time()

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=API_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200:
            result = response.json()
            return {
                "answer": result.get("answer", ""),
                "citations": result.get("citations", []),
                "confidence": result.get("confidence"),
                "latency_ms": latency_ms,
                "error": None,
                "meta": result.get("meta", {}),
            }
        else:
            return {
                "answer": None,
                "citations": [],
                "confidence": None,
                "latency_ms": latency_ms,
                "error": f"HTTP {response.status_code}: {response.text[:500]}",
            }

    except requests.exceptions.Timeout:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "answer": None,
            "citations": [],
            "confidence": None,
            "latency_ms": latency_ms,
            "error": f"Timeout after {API_TIMEOUT}s",
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "answer": None,
            "citations": [],
            "confidence": None,
            "latency_ms": latency_ms,
            "error": str(e),
        }


def format_citations(citations: list) -> list[dict]:
    """Format citations for output - extract key fields only."""
    formatted = []
    for c in citations:
        formatted.append(
            {
                "doc_id": c.get("doc_id"),
                "page": c.get("page"),
                "confidence": c.get("confidence"),
                "pdf_path": c.get("pdf_path"),
            }
        )
    return formatted


def run_batch_test(
    questions: list[dict],
    output_file: str,
    start_stt: float | None = None,
    end_stt: float | None = None,
    delay_between_requests: float = 1.0,
    api_url: str = None,
) -> dict:
    """
    Run batch test on all questions.

    Args:
        questions: List of {stt, question} dicts
        output_file: Path to save results
        start_stt: Only process questions with STT >= start_stt
        end_stt: Only process questions with STT <= end_stt
        delay_between_requests: Seconds to wait between API calls

    Returns:
        Summary statistics
    """
    # Filter by STT range if specified
    if start_stt is not None or end_stt is not None:
        filtered = []
        for q in questions:
            stt = q["stt"]
            if start_stt is not None and stt < start_stt:
                continue
            if end_stt is not None and stt > end_stt:
                continue
            filtered.append(q)
        questions = filtered
        logger.info(
            f"Filtered to {len(questions)} questions (STT {start_stt} - {end_stt})"
        )

    results = []
    total = len(questions)
    success_count = 0
    error_count = 0
    total_latency = 0

    logger.info(f"Starting batch test with {total} questions...")
    logger.info(f"Output will be saved to: {output_file}")

    for idx, q in enumerate(questions, 1):
        stt = q["stt"]
        question = q["question"]

        logger.info(f"[{idx}/{total}] Processing STT {stt}...")
        logger.debug(f"Question: {question[:100]}...")

        # Call API
        api_result = call_ask_api(question, api_url=api_url)

        # Build result record
        result = {
            "stt": stt,
            "question": question,
            "answer": api_result["answer"],
            "citations": format_citations(api_result["citations"]),
            "confidence": api_result["confidence"],
            "latency_ms": api_result["latency_ms"],
            "error": api_result["error"],
            "timestamp": datetime.now().isoformat(),
        }

        results.append(result)

        # Update stats
        if api_result["error"]:
            error_count += 1
            logger.warning(f"  ❌ Error: {api_result['error'][:100]}")
        else:
            success_count += 1
            total_latency += api_result["latency_ms"]
            answer_preview = (api_result["answer"] or "")[:100]
            logger.info(f"  ✅ Success ({api_result['latency_ms']}ms)")
            logger.debug(f"  Answer: {answer_preview}...")

        # Save intermediate results (in case of crash)
        if idx % 10 == 0:
            _save_results(results, output_file)
            logger.info(f"  💾 Saved intermediate results ({idx}/{total})")

        # Delay between requests
        if idx < total:
            time.sleep(delay_between_requests)

    # Final save
    _save_results(results, output_file)

    # Calculate summary
    avg_latency = total_latency / success_count if success_count > 0 else 0
    summary = {
        "total_questions": total,
        "success_count": success_count,
        "error_count": error_count,
        "success_rate": f"{success_count/total*100:.1f}%" if total > 0 else "N/A",
        "avg_latency_ms": int(avg_latency),
        "output_file": output_file,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info("=" * 60)
    logger.info("BATCH TEST COMPLETED")
    logger.info(f"  Total: {total}")
    logger.info(f"  Success: {success_count} ({summary['success_rate']})")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Avg Latency: {int(avg_latency)}ms")
    logger.info(f"  Results saved to: {output_file}")
    logger.info("=" * 60)

    return summary


def _save_results(results: list, output_file: str):
    """Save results to JSON file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Batch test Technical Document questions against RAG API"
    )
    parser.add_argument(
        "--input",
        "-i",
        default=DEFAULT_INPUT_FILE,
        help=f"Input JSON file with questions (default: {DEFAULT_INPUT_FILE})",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output JSON file for results (default: auto-generated with timestamp)",
    )
    parser.add_argument(
        "--start", type=float, default=None, help="Start STT (inclusive)"
    )
    parser.add_argument("--end", type=float, default=None, help="End STT (inclusive)")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--api-url",
        default=API_BASE_URL,
        help=f"API base URL (default: {API_BASE_URL})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )

    # Set API URL (update module-level variable)
    if args.api_url != API_BASE_URL:
        # Note: This only affects this run, not the module default
        pass

    # Generate output filename if not specified
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"scripts/evaluation/results/evaluation_results_{timestamp}.json"

    # Check input file exists
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    # Load questions
    questions = load_questions(args.input)

    if not questions:
        logger.error("No questions found in input file")
        sys.exit(1)

    # Run batch test
    summary = run_batch_test(
        questions=questions,
        output_file=args.output,
        start_stt=args.start,
        end_stt=args.end,
        delay_between_requests=args.delay,
        api_url=args.api_url,
    )

    # Print summary
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
