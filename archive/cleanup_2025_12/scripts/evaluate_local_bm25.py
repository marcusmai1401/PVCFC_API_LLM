"""
Evaluate retrieval accuracy using local BM25 index on existing chunks + debug chunks.
This bypasses the API and Docker services to test data quality directly.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from rank_bm25 import BM25Okapi
from rich.console import Console
from rich.progress import track
from rich.table import Table

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

console = Console()


def load_demo_questions(path: Path) -> List[Dict]:
    """Load questions from concatenated JSON file"""
    if not path.exists():
        console.print(f"[red]Demo questions file not found: {path}[/red]")
        return []

    questions = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        # Use regex to find JSON objects
        pattern = re.compile(r"\{.*?\}(?=\s*\{|\s*$)", re.DOTALL)
        # Actually raw_decode is better
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(content):
            try:
                # Skip whitespace
                while pos < len(content) and content[pos].isspace():
                    pos += 1
                if pos >= len(content):
                    break

                obj, idx = decoder.raw_decode(content[pos:])
                pos += idx

                # Process object
                doc_name = obj.get("document_name", "")
                interactions = obj.get("interaction", [])
                if isinstance(interactions, list):
                    for turn in interactions:
                        if isinstance(turn, dict):
                            turn["document"] = doc_name  # Propagate doc name
                            questions.append(turn)
            except json.JSONDecodeError:
                # Try to skip to next {
                pos += 1

    # Filter for technical doc questions only (non-drawing)
    filtered = []
    for q in questions:
        # Simple heuristic to filter out CAD/Drawings if query_type not set
        q_type = q.get("query_type", "technical_doc")
        doc_name = q.get("document", "").upper()
        if "DRAWING" in doc_name or "DWG" in doc_name or "P&ID" in doc_name:
            continue
        filtered.append(q)

    console.print(
        f"Loaded {len(filtered)} technical questions (from {len(questions)} total)"
    )
    return filtered


def load_chunks(dirs: List[Path]) -> List[Dict]:
    """Load chunks from multiple ingestion directories"""
    chunks = []
    seen_ids = set()

    for d in dirs:
        jsonl_path = d / "chunks" / "chunks.jsonl"
        if not jsonl_path.exists():
            continue

        console.print(f"Loading chunks from {jsonl_path}...")
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    chunk = json.loads(line)
                    # Deduplicate by chunk_id (prefer newer/debug chunks if appended later)
                    # But here we process dirs in order, so first wins? No, we want debug to override.
                    # Actually unique IDs usually differ by hash.
                    # If we ingest same file again, hash changes?
                    # ingest.py: doc_id includes hash of path. path relative to source.
                    # debug_input path is different from original path?
                    # debug_input/file.pdf vs source/file.pdf.
                    # So doc_ids will be different. We will have duplicates.
                    # That's fine for retrieval test.

                    chunks.append(chunk)
                except:
                    pass

    console.print(f"Loaded {len(chunks)} total chunks")
    return chunks


def normalize_text(text: str) -> List[str]:
    """Simple tokenization for BM25"""
    text = text.lower()
    # Remove punctuation
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def evaluate(questions: List[Dict], chunks: List[Dict]):
    """Run evaluation"""
    if not chunks:
        console.print("[red]No chunks loaded![/red]")
        return

    # Prepare BM25
    console.print("Building BM25 index...")
    tokenized_corpus = [
        normalize_text(c["text"] + " " + c.get("metadata", {}).get("file_name", ""))
        for c in chunks
    ]
    bm25 = BM25Okapi(tokenized_corpus)

    # Run queries
    correct_page = 0
    correct_doc = 0
    total = 0

    table = Table(title="Evaluation Results (Local BM25)")
    table.add_column("Question", style="cyan", max_width=50)
    table.add_column("Expected Doc/Page", style="green")
    table.add_column("Top Result", style="yellow")
    table.add_column("Status", style="bold")

    results = []

    for q in track(questions, description="Evaluating..."):
        query = q.get("question", "")
        expected_doc = q.get("document", "")
        expected_page = q.get("source_page") or q.get("page")

        if not query or not expected_doc:
            continue

        total += 1

        # Tokenize query
        tokenized_query = normalize_text(query)

        # Get top 5
        top_n = bm25.get_top_n(tokenized_query, chunks, n=5)

        # Check correctness
        found_doc = False
        found_page = False
        top_result_str = ""

        for i, hit in enumerate(top_n):
            hit_doc = hit.get("metadata", {}).get("file_name", "")
            hit_page_start = hit.get("page_start", -1)
            hit_page_end = hit.get("page_end", -1)

            # Simple matching of document name
            # Remove extension for looser match
            exp_base = Path(expected_doc).stem
            hit_base = Path(hit_doc).stem

            # Normalizing for matching (remove revision, etc if needed)
            # Just exact text containment for now
            doc_match = (
                exp_base.lower() in hit_base.lower()
                or hit_base.lower() in exp_base.lower()
            )

            if i == 0:
                top_result_str = f"{hit_doc} (p{hit_page_start+1})"

            if doc_match:
                found_doc = True
                # Check page (allow +/- 1 page tolerance)
                if expected_page is not None:
                    # expected_page is usually 1-based
                    # hit_page is 0-based
                    p_start = hit_page_start + 1
                    p_end = hit_page_end + 1

                    # Check overlap
                    # Expected page (e.g. 2) should be in [p_start, p_end]
                    # Tolerance +/- 1
                    try:
                        exp_p = int(
                            str(expected_page).split("-")[0]
                        )  # Handle ranges like "1-2"
                        if p_start - 1 <= exp_p <= p_end + 1:
                            found_page = True
                    except:
                        pass
                else:
                    # If no page expected, doc match is enough?
                    # Usually "citation" requires page.
                    pass

        status = "[red]FAIL[/red]"
        if found_page:
            correct_page += 1
            status = "[green]PERFECT[/green]"
        elif found_doc:
            correct_doc += 1
            status = "[yellow]DOC ONLY[/yellow]"

        table.add_row(
            query[:50] + "...",
            f"{expected_doc} p{expected_page}",
            top_result_str,
            status,
        )

        results.append(
            {
                "question": query,
                "status": status,
                "found_doc": found_doc,
                "found_page": found_page,
            }
        )

    console.print(table)

    if total > 0:
        console.print(f"\nTotal Questions: {total}")
        console.print(f"Correct Document: {correct_doc} ({correct_doc/total:.1%})")
        console.print(f"Correct Page: {correct_page} ({correct_page/total:.1%})")
        console.print(f"(Correct Page includes Correct Document cases)")
    else:
        console.print("[red]No questions evaluated[/red]")


def main():
    q_path = Path("Demo questions.json")
    # Use both debug and production artifacts
    chunk_dirs = [Path("artifacts/ingestion"), Path("artifacts/ingestion_debug")]

    questions = load_demo_questions(q_path)
    chunks = load_chunks(chunk_dirs)

    # Filter for the fixed document to verify fix
    filtered = []
    for q in questions:
        if "K06101" in q.get("document", "").upper() or "002_" in q.get("document", ""):
            filtered.append(q)

    console.print(f"Filtered for K06101/002: {len(filtered)} questions")
    evaluate(filtered, chunks)


if __name__ == "__main__":
    main()
