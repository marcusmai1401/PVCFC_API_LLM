import asyncio
import json
import os
import time
from typing import Any, Dict, List

import httpx
from google import genai
from google.genai import types
from rich.console import Console
from rich.progress import track
from rich.table import Table

# Configuration
API_URL = "http://localhost:8000/ask"
DEMO_FILE = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\Demo questions.json"
CAD_KEYWORDS = [
    "DRAWING",
    "P&ID",
    "PID",
    "LAYOUT",
    "DIAGRAM",
    "SECTIONAL",
    "ASSEMBLY",
    "ARRANGEMENT",
]
CAD_ANSWER_KEYWORDS = ["bản vẽ", "sơ đồ"]

# Gemini Judge Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Load from environment variable
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
JUDGE_MODEL = "gemini-2.0-flash"  # Use a fast/cheap model for judging

console = Console()


def parse_mixed_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Parses a file containing multiple concatenated JSON objects."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    decoder = json.JSONDecoder()
    objects = []
    pos = 0
    while pos < len(content):
        content = content.strip()
        if not content:
            break
        try:
            obj, index = decoder.raw_decode(content[pos:])
            objects.append(obj)
            pos += index
            while pos < len(content) and content[pos].isspace():
                pos += 1
        except json.JSONDecodeError:
            break
    return objects


def is_cad_document(doc_name: str, interactions: List[Dict]) -> bool:
    doc_name_upper = doc_name.upper()
    for kw in CAD_KEYWORDS:
        if kw in doc_name_upper:
            return True
    for interaction in interactions:
        answer = interaction.get("answer", "").lower()
        for kw in CAD_ANSWER_KEYWORDS:
            if kw in answer:
                return True
    return False


async def judge_answer(
    client: genai.Client, question: str, expected: str, actual: str
) -> Dict[str, Any]:
    """Uses Gemini to judge if the actual answer is semantically correct compared to expected."""
    if (
        not actual
        or "không tìm thấy" in actual.lower()
        or "not found" in actual.lower()
    ):
        return {"correct": False, "reason": "Answer indicates not found"}

    prompt = f"""You are an impartial judge evaluating the correctness of an AI generated answer.

Question: {question}

Expected Answer (Ground Truth):
{expected}

Generated Answer:
{actual}

Task: Determine if the Generated Answer conveys the SAME key information (facts, numbers, entities) as the Expected Answer.
Ignore minor phrasing differences or extra context unless it contradicts the truth.
Ignore citation format differences (e.g. [Doc 1] vs [Doc 5]).

Output JSON:
{{
  "correct": boolean,
  "reason": "brief explanation"
}}
"""
    try:
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        return {"correct": False, "reason": f"Judge error: {str(e)}"}


async def test_question(
    http_client: httpx.AsyncClient,
    judge_client: genai.Client,
    question: str,
    expected_answer: str,
    expected_page: int,
) -> Dict[str, Any]:
    payload = {
        "query": question,
        "query_type": "technical_doc",
        "max_context": 8,
        "language": "vi",
    }

    start_time = time.time()
    try:
        # Call API
        response = await http_client.post(API_URL, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        elapsed = time.time() - start_time

        actual_answer = data.get("answer", "")
        citations = data.get("citations", [])
        found_pages = [c.get("page") for c in citations]

        # 1. Check Page Accuracy
        page_correct = False
        if expected_page in found_pages:
            page_correct = True
        else:
            for p in found_pages:
                if isinstance(p, int) and abs(p - expected_page) <= 1:
                    page_correct = True
                    break

        # 2. Check Content Accuracy (LLM Judge)
        content_eval = await judge_answer(
            judge_client, question, expected_answer, actual_answer
        )
        content_correct = content_eval.get("correct", False)

        return {
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "expected_page": expected_page,
            "found_pages": found_pages,
            "page_correct": page_correct,
            "content_correct": content_correct,
            "judge_reason": content_eval.get("reason"),
            "latency": elapsed,
            "error": None,
        }

    except Exception as e:
        return {
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": "",
            "expected_page": expected_page,
            "found_pages": [],
            "page_correct": False,
            "content_correct": False,
            "judge_reason": "API Error",
            "latency": time.time() - start_time,
            "error": str(e),
        }


async def main():
    console.print(f"[bold blue]Starting Detailed Evaluation Script[/bold blue]")

    # Initialize Judge Client
    try:
        judge_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        console.print(f"[bold red]Failed to init Gemini Judge:[/bold red] {e}")
        return

    # Load Data
    try:
        data = parse_mixed_json_file(DEMO_FILE)
    except Exception as e:
        console.print(f"[bold red]Failed to parse JSON:[/bold red] {e}")
        return

    technical_docs = []
    for item in data:
        doc_name = item.get("document_name", "")
        interactions = item.get("interaction", [])

        if is_cad_document(doc_name, interactions):
            continue

        for interaction in interactions:
            technical_docs.append(
                {
                    "question": interaction["question"],
                    "answer": interaction["answer"],
                    "source_page": interaction["source_page"],
                }
            )

    console.print(f"Technical Questions: {len(technical_docs)}")

    # Run Tests
    results = []
    async with httpx.AsyncClient() as http_client:
        # Warmup / Health check
        try:
            await http_client.get("http://localhost:8000/metrics")
        except:
            console.print("[bold red]API not available![/bold red]")
            return

        for item in track(technical_docs, description="Evaluating..."):
            res = await test_question(
                http_client,
                judge_client,
                item["question"],
                item["answer"],
                item["source_page"],
            )
            results.append(res)

    # Analysis
    total = len(results)
    page_correct_count = sum(1 for r in results if r["page_correct"])
    content_correct_count = sum(1 for r in results if r["content_correct"])

    # Categorization
    # - Perfect: Page Correct AND Content Correct
    # - Lucky: Page Wrong BUT Content Correct (Hallucination or redundant info?)
    # - Missed: Page Correct BUT Content Wrong (Retrieval good, Generation bad?)
    # - Fail: Both Wrong

    perfect = sum(1 for r in results if r["page_correct"] and r["content_correct"])
    lucky = sum(1 for r in results if not r["page_correct"] and r["content_correct"])
    missed = sum(1 for r in results if r["page_correct"] and not r["content_correct"])
    fail = sum(1 for r in results if not r["page_correct"] and not r["content_correct"])

    table = Table(title="Detailed Evaluation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Percent", style="green")

    table.add_row("Total Questions", str(total), "100%")
    table.add_row(
        "Page Retrieval Accuracy",
        str(page_correct_count),
        f"{(page_correct_count/total)*100:.1f}%",
    )
    table.add_row(
        "Content Accuracy (LLM Judge)",
        str(content_correct_count),
        f"{(content_correct_count/total)*100:.1f}%",
    )
    table.add_section()
    table.add_row(
        "Perfect (Page+Content OK)", str(perfect), f"{(perfect/total)*100:.1f}%"
    )
    table.add_row(
        "Lucky (Page Wrong, Content OK)", str(lucky), f"{(lucky/total)*100:.1f}%"
    )
    table.add_row(
        "Generation Fail (Page OK, Content Bad)",
        str(missed),
        f"{(missed/total)*100:.1f}%",
    )
    table.add_row("Total Failure", str(fail), f"{(fail/total)*100:.1f}%")

    console.print(table)

    # Save detailed report to JSON
    with open("evaluation_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    console.print("\n[dim]Detailed report saved to evaluation_report.json[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
