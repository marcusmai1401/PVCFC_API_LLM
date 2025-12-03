import os
import sys
import textwrap
from pathlib import Path

# Ensure project root is on sys.path so `app` package is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.query_transform import QueryTransformer
from app.rag.technical_doc_retriever import TechnicalDocRetriever


def main() -> None:
    question = (
        "According to the expected performance curves for the CO2 compressor, "
        "what is the 100% operating speed in RPM?"
    )

    print("Question:")
    print("  ", question)
    print("\nRunning QueryTransformer (with technical_doc override)...\n")

    transformer = QueryTransformer(enable_hyde=True)
    transformed = transformer.transform(
        question,
        filters=None,
        language="en",
        query_type_override="technical_doc",
    )

    print("Transformed query:")
    print("  normalized:", transformed.normalized)
    print("  intent:", transformed.intent.value)
    qc = (transformed.metadata or {}).get("query_classification")
    if qc:
        print("  classification:", qc)
    print()

    retriever = TechnicalDocRetriever(enable_llm_rerank=False)

    print("Running TechnicalDocRetriever.search(top_k=10)...\n")
    results = retriever.search(transformed, top_k=10)

    if not results:
        print("No results returned.")
        return

    print("Top 10 results:")
    for i, r in enumerate(results, start=1):
        meta = r.metadata or {}
        file_name = meta.get("file_name") or meta.get("title") or meta.get("doc_name")
        doc_type = meta.get("doc_type") or meta.get("doc_category")

        print(f"{i:2d}. score={r.score:.4f} source={r.source}")
        print(f"    doc_id   = {r.doc_id}")
        print(f"    page     = {r.page}")
        if file_name:
            print(f"    file_name= {file_name}")
        if doc_type:
            print(f"    doc_type = {doc_type}")

        snippet = (r.text or "").replace("\n", " ")
        snippet = " ".join(snippet.split())  # collapse whitespace
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        wrapped = textwrap.fill(snippet, width=100, subsequent_indent=" " * 12)
        print(f"    text     = {wrapped}")
        print()


if __name__ == "__main__":
    main()
