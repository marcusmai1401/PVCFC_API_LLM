"""
Script chạy test 300 câu hỏi qua API PVCFC RAG
Tạo output tương ứng trong folder 300 answers/

Input:  300 questions/Level X/XY.json
Output: 300 answers/Level X/XY_answers.json

Usage:
    python scripts/run_300_questions_test.py
    python scripts/run_300_questions_test.py --level 1  # Chỉ chạy Level 1
    python scripts/run_300_questions_test.py --file 1A  # Chỉ chạy file 1A
    python scripts/run_300_questions_test.py --dry-run  # Chạy thử không gọi API
"""

import argparse
import asyncio
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Thêm project root vào path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Constants
API_BASE_URL = "http://localhost:8000"
QUESTIONS_DIR = PROJECT_ROOT / "300 questions"
ANSWERS_DIR = PROJECT_ROOT / "300 answers"
TIMEOUT_SECONDS = 300  # 5 phút cho mỗi câu hỏi (Vision có thể lâu)


async def call_ask_api(
    client: httpx.AsyncClient,
    question: str,
    language: str = "vi",
    max_context: int = 30,
    enable_vision: bool = True,
    query_type: str = "technical_doc",
) -> dict:
    """Gọi API /ask và trả về response"""
    payload = {
        "query": question,
        "language": language,
        "max_context": max_context,
        "enable_vision_generation": enable_vision,
        "query_type": query_type,
    }

    response = await client.post(
        f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()


def process_api_response(api_response: dict) -> dict:
    """Trích xuất answer và citations từ API response"""
    return {
        "answer": api_response.get("answer", ""),
        "citations": api_response.get("citations", []),
        "confidence": api_response.get("confidence"),
        "meta": {
            "model": api_response.get("meta", {}).get("model"),
            "latency_ms": api_response.get("meta", {}).get("latency_ms"),
            "trace_id": api_response.get("meta", {}).get("trace_id"),
        },
    }


async def process_question_file(
    client: httpx.AsyncClient,
    input_file: Path,
    output_file: Path,
    dry_run: bool = False,
) -> dict:
    """Xử lý một file câu hỏi và tạo file answers tương ứng"""

    # Đọc file câu hỏi
    with open(input_file, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    results = []
    stats = {"total": 0, "success": 0, "failed": 0}

    for item in questions_data:
        stt = item.get("STT")
        interactions = item.get("interaction", [])

        for interaction in interactions:
            question = interaction.get("question", "")
            stats["total"] += 1

            print(f"  [{stt}] {question[:60]}...", flush=True)

            if dry_run:
                # Dry run - không gọi API
                result = {
                    "STT": stt,
                    "question": question,
                    "answer": "[DRY RUN - No API call]",
                    "citations": [],
                }
                stats["success"] += 1
            else:
                try:
                    api_response = await call_ask_api(client, question)
                    processed = process_api_response(api_response)

                    result = {
                        "STT": stt,
                        "question": question,
                        "answer": processed["answer"],
                        "citations": processed["citations"],
                        "confidence": processed["confidence"],
                        "meta": processed["meta"],
                    }
                    stats["success"] += 1
                    print(
                        f"       [OK] Success (confidence: {processed['confidence']})",
                        flush=True,
                    )

                except httpx.HTTPStatusError as e:
                    result = {
                        "STT": stt,
                        "question": question,
                        "answer": f"[ERROR] HTTP {e.response.status_code}",
                        "citations": [],
                        "error": str(e),
                    }
                    stats["failed"] += 1
                    print(
                        f"       [FAIL] HTTP Error: {e.response.status_code}",
                        flush=True,
                    )

                except httpx.TimeoutException:
                    result = {
                        "STT": stt,
                        "question": question,
                        "answer": "[ERROR] Request timeout",
                        "citations": [],
                        "error": "Timeout",
                    }
                    stats["failed"] += 1
                    print(f"       [FAIL] Timeout", flush=True)

                except Exception as e:
                    result = {
                        "STT": stt,
                        "question": question,
                        "answer": f"[ERROR] {type(e).__name__}",
                        "citations": [],
                        "error": str(e),
                    }
                    stats["failed"] += 1
                    print(f"       [FAIL] Error: {e}", flush=True)

            results.append(result)

    # Tạo thư mục output nếu chưa có
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Ghi file output
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "source_file": str(input_file),
        "stats": stats,
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  → Saved to {output_file}")
    return stats


async def check_api_health() -> bool:
    """Kiểm tra API có đang chạy không"""
    try:
        # Use sync client for health check to avoid async issues
        response = httpx.get(f"{API_BASE_URL}/healthz", timeout=60)
        return response.status_code == 200
    except Exception as e:
        print(f"Health check error: {e}")
        return False


async def main(
    level: Optional[int] = None,
    file_filter: Optional[str] = None,
    dry_run: bool = False,
):
    """Main function"""

    print("=" * 60)
    print("PVCFC RAG - 300 Questions Test Runner")
    print("=" * 60)
    print(f"API URL: {API_BASE_URL}")
    print(f"Questions dir: {QUESTIONS_DIR}")
    print(f"Answers dir: {ANSWERS_DIR}")
    print(f"Dry run: {dry_run}")
    print()

    # Kiểm tra API
    if not dry_run:
        print("Checking API health...")
        if not await check_api_health():
            print("ERROR: API is not running at", API_BASE_URL)
            print("Please start the API first: .\\launchers\\start_api.ps1")
            sys.exit(1)
        print("[OK] API is healthy\n")

    # Tìm tất cả file câu hỏi
    question_files = []

    for level_dir in sorted(QUESTIONS_DIR.iterdir()):
        if not level_dir.is_dir():
            continue

        # Filter theo level nếu có
        level_num = int(level_dir.name.replace("Level ", ""))
        if level is not None and level_num != level:
            continue

        for json_file in sorted(level_dir.glob("*.json")):
            # Filter theo file nếu có
            if file_filter and file_filter not in json_file.stem:
                continue

            # Tạo đường dẫn output tương ứng
            output_file = (
                ANSWERS_DIR / level_dir.name / f"{json_file.stem}_answers.json"
            )
            question_files.append((json_file, output_file))

    if not question_files:
        print("No question files found matching criteria")
        sys.exit(1)

    print(f"Found {len(question_files)} question files to process\n")

    # Xử lý từng file
    total_stats = {"total": 0, "success": 0, "failed": 0}

    async with httpx.AsyncClient() as client:
        for i, (input_file, output_file) in enumerate(question_files, 1):
            print(f"\n[{i}/{len(question_files)}] Processing {input_file.name}")
            print("-" * 40)

            stats = await process_question_file(
                client, input_file, output_file, dry_run
            )

            total_stats["total"] += stats["total"]
            total_stats["success"] += stats["success"]
            total_stats["failed"] += stats["failed"]

    # Tổng kết
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total questions: {total_stats['total']}")
    print(f"Success: {total_stats['success']}")
    print(f"Failed: {total_stats['failed']}")
    if total_stats["total"] > 0:
        success_rate = total_stats["success"] / total_stats["total"] * 100
        print(f"Success rate: {success_rate:.1f}%")
    print(f"\nResults saved to: {ANSWERS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 300 questions test")
    parser.add_argument("--level", type=int, help="Only process specific level (1-6)")
    parser.add_argument(
        "--file",
        type=str,
        help="Only process files containing this string (e.g., '1A')",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run without calling API"
    )

    args = parser.parse_args()

    asyncio.run(main(level=args.level, file_filter=args.file, dry_run=args.dry_run))
