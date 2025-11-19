import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
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

console = Console()


def parse_mixed_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Parses a file containing multiple concatenated JSON objects."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Attempt to split by closing brace followed by newline and opening brace
    # This is a heuristic for the specific format provided
    # We add a wrapper to make it a valid list if possible, or split

    objects = []
    # Regex to find boundaries between JSON objects: } followed by optional whitespace and {
    # We'll treat the whole file as a sequence of JSONs.
    # Since simple split might fail if nested braces, we use a decoder.

    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(content):
        content = content.strip()
        if not content:
            break
        try:
            obj, index = decoder.raw_decode(content[pos:])
            objects.append(obj)
            pos += index
            # Skip whitespace
            while pos < len(content) and content[pos].isspace():
                pos += 1
        except json.JSONDecodeError:
            # Try to skip garbage or stop
            break

    return objects


def is_cad_document(doc_name: str, interactions: List[Dict]) -> bool:
    """Determines if a document is CAD-like based on name and answer content."""
    doc_name_upper = doc_name.upper()

    # Check filename keywords
    for kw in CAD_KEYWORDS:
        if kw in doc_name_upper:
            return True

    # Check answer content
    for interaction in interactions:
        answer = interaction.get("answer", "").lower()
        for kw in CAD_ANSWER_KEYWORDS:
            if kw in answer:
                return True

    return False


async def test_question(
    client: httpx.AsyncClient, question: str, expected_page: int
) -> Dict[str, Any]:
    """Sends a question to the API and evaluates the response."""
    payload = {
        "query": question,
        "query_type": "technical_doc",
        "max_context": 8,
        "language": "vi",  # Assuming Vietnamese based on the file content
    }

    start_time = time.time()
    try:
        response = await client.post(API_URL, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        elapsed = time.time() - start_time

        citations = data.get("citations", [])
        found_pages = [c.get("page") for c in citations]

        # Check if expected page is in citations (fuzzy match)
        # API might return page 5, expected 5. Or API page 5-6.
        # We check if expected_page is present.
        is_correct = False
        if expected_page in found_pages:
            is_correct = True

        # Also check for "offset" pages (sometimes extraction is off by 1)
        if not is_correct:
            for p in found_pages:
                if isinstance(p, int) and abs(p - expected_page) <= 1:
                    is_correct = True  # Relaxed correctness
                    break

        return {
            "question": question,
            "correct": is_correct,
            "found_pages": found_pages,
            "expected_page": expected_page,
            "latency": elapsed,
            "error": None,
        }

    except Exception as e:
        return {
            "question": question,
            "correct": False,
            "found_pages": [],
            "expected_page": expected_page,
            "latency": time.time() - start_time,
            "error": str(e),
        }


async def main():
    console.print(f"[bold blue]Starting Evaluation Script[/bold blue]")
    console.print(f"Reading file: {DEMO_FILE}")

    try:
        data = parse_mixed_json_file(DEMO_FILE)
    except Exception as e:
        console.print(f"[bold red]Failed to parse JSON file:[/bold red] {e}")
        return

    technical_docs = []
    skipped_cad = 0

    # Filter documents
    for item in data:
        doc_name = item.get("document_name", "")
        interactions = item.get("interaction", [])

        if is_cad_document(doc_name, interactions):
            skipped_cad += 1
            continue

        for interaction in interactions:
            technical_docs.append(
                {
                    "doc_name": doc_name,
                    "question": interaction["question"],
                    "answer": interaction["answer"],
                    "source_page": interaction["source_page"],
                }
            )

    console.print(f"Total items loaded: {len(data)}")
    console.print(f"Skipped CAD-like docs: {skipped_cad}")
    console.print(f"Technical Doc questions to test: {len(technical_docs)}")

    if not technical_docs:
        console.print("[yellow]No technical documents found to test.[/yellow]")
        return

    # Run tests
    results = []
    correct_count = 0

    async with httpx.AsyncClient() as client:
        # Check API health
        try:
            resp = await client.get("http://localhost:8000/metrics")
            if resp.status_code != 200:
                console.print(
                    "[bold red]API is not healthy. Please start the server.[/bold red]"
                )
                return
        except:
            console.print(
                "[bold red]Could not connect to API at http://localhost:8000. Please start the server.[/bold red]"
            )
            return

        for i, item in enumerate(track(technical_docs, description="Testing...")):
            res = await test_question(client, item["question"], item["source_page"])
            results.append(res)
            if res["correct"]:
                correct_count += 1

            # Optional: Print failure details immediately
            # if not res["correct"]:
            #     console.print(f"[red]Fail:[/red] {item['question'][:50]}... (Exp: {res['expected_page']}, Got: {res['found_pages']})")

    # Summary
    accuracy = (correct_count / len(technical_docs)) * 100

    table = Table(title="Evaluation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Total Questions", str(len(technical_docs)))
    table.add_row("Correct (Page Match)", str(correct_count))
    table.add_row("Accuracy", f"{accuracy:.2f}%")

    avg_latency = sum(r["latency"] for r in results) / len(results)
    table.add_row("Avg Latency", f"{avg_latency:.2f}s")

    console.print(table)

    # Detailed failure log
    if correct_count < len(technical_docs):
        console.print("\n[bold red]Failed Questions (Sample):[/bold red]")
        failures = [r for r in results if not r["correct"]]
        for f in failures[:5]:
            console.print(f"- Q: {f['question']}")
            console.print(
                f"  Exp: {f['expected_page']} | Got: {f['found_pages']} | Err: {f['error']}"
            )
            console.print("---")


if __name__ == "__main__":
    asyncio.run(main())
