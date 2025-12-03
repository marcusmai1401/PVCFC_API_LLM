"""
RAG CLI - Command Line Interface for Phase 1 RAG Pipeline

Provides easy-to-use commands for:
- Querying documents with citations
- Building page index
- Validating citations
- Interactive search

Usage:
    python rag_cli.py query "What is the operating pressure?"
    python rag_cli.py query "temperature specifications" --doc-ids DOC1 DOC2
    python rag_cli.py build-index
    python rag_cli.py interactive
    python rag_cli.py --help
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from loguru import logger

    from app.config import get_config
    from app.rag.citation_retriever import (
        CitationRetriever,
        SearchConfig,
        get_citation_retriever,
    )

    # Configure logger for CLI
    logger.remove()
    logger.add(sys.stderr, level="WARNING")  # Only show warnings/errors in CLI

except ImportError as e:
    print(f"Error: Failed to import required modules: {e}")
    print(
        "Please ensure you are in the project directory and dependencies are installed."
    )
    sys.exit(1)


def cmd_query(args):
    """Handle query command"""
    print(f"\n{'='*80}")
    print(f"QUERY: {args.query}")
    print(f"{'='*80}\n")

    # Initialize retriever
    retriever = get_citation_retriever()

    # Parse doc_ids if provided
    doc_ids = args.doc_ids if args.doc_ids else None

    # Create config
    config = SearchConfig(
        top_k_docs=args.top_k_docs,
        top_k_pages_per_doc=args.top_k_pages,
        max_total_citations=args.max_citations,
        max_snippets_per_page=args.max_snippets,
        highlight_keywords=not args.no_highlight,
    )

    # Search
    try:
        citations = retriever.search_with_citations(
            query=args.query,
            doc_ids=doc_ids,
            config_override=config,
        )
    except Exception as e:
        print(f"Error during search: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    # Display results
    if not citations:
        print("No citations found.")
        return 0

    print(f"Found {len(citations)} citations:\n")

    for citation in citations:
        if args.format == "simple":
            # Simple format: just citation info
            doc_name = citation.metadata.get("doc_name", citation.doc_id)
            print(
                f"[{citation.rank}] {doc_name}, Page {citation.page} (Score: {citation.score:.2%})"
            )

        elif args.format == "detailed":
            # Detailed format: with snippets
            formatted = citation.format_citation(include_snippets=True)
            print(formatted)
            print(f"{'-'*80}\n")

        elif args.format == "json":
            # JSON format
            import json

            print(json.dumps(citation.to_dict(), indent=2, ensure_ascii=False))
            print()

    return 0


def cmd_build_index(args):
    """Handle build-index command"""
    print(f"\n{'='*80}")
    print("BUILD PAGE INDEX")
    print(f"{'='*80}\n")

    # Import build tool
    try:
        sys.path.insert(0, str(Path(__file__).parent / "tools"))
        from tools.build_page_index import PageIndexBuilder
    except ImportError as e:
        print(f"Error: Could not import build_page_index tool: {e}")
        return 1

    # Get doc_id_map path
    config = get_config()
    doc_id_map_path = args.doc_id_map or "artifacts/ingestion/doc_id_map.json"

    if not Path(doc_id_map_path).exists():
        print(f"Error: doc_id_map not found at {doc_id_map_path}")
        print("Please provide correct path with --doc-id-map")
        return 1

    # Build index
    try:
        builder = PageIndexBuilder(
            doc_id_map_path=doc_id_map_path,
            enable_ocr=not args.no_ocr,
        )

        builder.run()

        print(f"\n✓ Index built successfully!")
        print(f"  Total pages: {builder.stats['total_pages']}")
        print(f"  OCR pages: {builder.stats['ocr_pages']}")
        print(f"  Output: {builder.output_dir}")

        return 0

    except Exception as e:
        print(f"Error building index: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_interactive(args):
    """Handle interactive mode"""
    print(f"\n{'='*80}")
    print("INTERACTIVE SEARCH MODE")
    print(f"{'='*80}\n")
    print("Enter your queries (or 'quit' to exit):\n")

    # Initialize retriever
    retriever = get_citation_retriever()

    config = SearchConfig(
        top_k_docs=args.top_k_docs,
        top_k_pages_per_doc=args.top_k_pages,
        max_total_citations=args.max_citations,
        max_snippets_per_page=2,  # Keep snippets concise in interactive mode
    )

    while True:
        try:
            query = input("\nQuery: ").strip()

            if not query:
                continue

            if query.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            # Search
            citations = retriever.search_with_citations(
                query=query,
                config_override=config,
            )

            if not citations:
                print("  No citations found.")
                continue

            print(f"\n  Found {len(citations)} citations:")

            for citation in citations[:5]:  # Show top 5 in interactive
                doc_name = citation.metadata.get("doc_name", citation.doc_id[:50])
                print(
                    f"\n  [{citation.rank}] {doc_name}, Page {citation.page} (Score: {citation.score:.1%})"
                )

                if citation.snippets:
                    snippet = citation.snippets[0]
                    preview = (
                        snippet.highlighted_text[:150]
                        if snippet.highlighted_text
                        else snippet.text[:150]
                    )
                    print(f"      {preview}...")

            if len(citations) > 5:
                print(f"\n  ... and {len(citations) - 5} more results")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n  Error: {e}")

    return 0


def cmd_build_embeddings(args):
    """Handle build-embeddings command"""
    print(f"\n{'='*80}")
    print("BUILD PAGE EMBEDDINGS")
    print(f"{'='*80}\n")

    try:
        sys.path.insert(0, str(Path(__file__).parent / "tools"))
        from tools.build_page_embeddings import build_embeddings
    except ImportError as e:
        print(f"Error: Could not import build_page_embeddings tool: {e}")
        return 1

    provider = args.provider
    model = args.model
    batch_size = args.batch_size

    from app.config import get_config

    cfg = get_config()
    out_path = Path(args.output) if args.output else cfg.page_embeddings_path

    try:
        build_embeddings(
            provider=provider, model=model, batch_size=batch_size, out_path=out_path
        )
        print(f"\n✓ Embeddings built successfully!")
        print(f"  Output: {out_path}")
        return 0
    except Exception as e:
        print(f"Error building embeddings: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_validate(args):
    """Handle validate command"""
    print(f"\n{'='*80}")
    print("VALIDATE SYSTEM")
    print(f"{'='*80}\n")

    checks = []

    # Check 1: Config
    print("1. Checking configuration...")
    try:
        config = get_config()
        config.validate()
        checks.append(("Configuration", True, "OK"))
    except Exception as e:
        checks.append(("Configuration", False, str(e)))

    # Check 2: Page index
    print("2. Checking page index...")
    try:
        config = get_config()
        if config.page_bm25_index_path.exists():
            import pickle

            with open(config.page_bm25_index_path, "rb") as f:
                data = pickle.load(f)
            page_count = len(data["doc_ids"])
            doc_count = len(set(data["doc_ids"]))
            checks.append(("Page Index", True, f"{page_count} pages, {doc_count} docs"))
        else:
            checks.append(("Page Index", False, "Index file not found"))
    except Exception as e:
        checks.append(("Page Index", False, str(e)))

    # Check 3: Text data
    print("3. Checking text data...")
    try:
        config = get_config()
        if config.text_by_page_path.exists():
            import jsonlines

            line_count = sum(1 for _ in jsonlines.open(config.text_by_page_path))
            checks.append(("Text Data", True, f"{line_count} pages"))
        else:
            checks.append(("Text Data", False, "File not found"))
    except Exception as e:
        checks.append(("Text Data", False, str(e)))

    # Check 4: RAG components
    print("4. Checking RAG components...")
    try:
        retriever = get_citation_retriever()
        checks.append(("RAG Components", True, "All initialized"))
    except Exception as e:
        checks.append(("RAG Components", False, str(e)))

    # Check 5: Page embeddings (optional)
    print("5. Checking page embeddings (optional)...")
    try:
        if config.page_embeddings_path.exists():
            import numpy as np

            data = np.load(str(config.page_embeddings_path), allow_pickle=True)
            embs = data["embeddings"]
            checks.append(
                (
                    "Page Embeddings",
                    True,
                    f"{embs.shape[0]} pages x {embs.shape[1]} dims",
                )
            )
        else:
            checks.append(("Page Embeddings", False, "Embeddings file not found"))
    except Exception as e:
        checks.append(("Page Embeddings", False, str(e)))

    # Print summary
    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}\n")

    all_passed = True
    for name, passed, message in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {name}: {message}")
        if not passed:
            all_passed = False

    if all_passed:
        print(f"\n🎉 System validation passed! RAG pipeline is ready.")
        return 0
    else:
        print(f"\n⚠ Some checks failed. Please review above.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="RAG CLI - Phase 1 Citation-Aware Retrieval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple query
  python rag_cli.py query "operating pressure"

  # Query with options
  python rag_cli.py query "temperature specs" --top-k-docs 3 --format detailed

  # Search in specific documents
  python rag_cli.py query "safety" --doc-ids DOC1 DOC2 DOC3

  # Build page index
  python rag_cli.py build-index

  # Interactive mode
  python rag_cli.py interactive

  # Validate system
  python rag_cli.py validate
        """,
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Query command
    query_parser = subparsers.add_parser(
        "query", help="Search documents with citations"
    )
    query_parser.add_argument("query", type=str, help="Search query")
    query_parser.add_argument(
        "--doc-ids", nargs="+", help="Specific document IDs to search"
    )
    query_parser.add_argument(
        "--top-k-docs", type=int, default=5, help="Number of documents (default: 5)"
    )
    query_parser.add_argument(
        "--top-k-pages", type=int, default=3, help="Pages per document (default: 3)"
    )
    query_parser.add_argument(
        "--max-citations", type=int, default=10, help="Max citations (default: 10)"
    )
    query_parser.add_argument(
        "--max-snippets", type=int, default=3, help="Snippets per page (default: 3)"
    )
    query_parser.add_argument(
        "--no-highlight", action="store_true", help="Disable keyword highlighting"
    )
    query_parser.add_argument(
        "--format",
        choices=["simple", "detailed", "json"],
        default="detailed",
        help="Output format",
    )
    query_parser.set_defaults(func=cmd_query)

    # Build index command
    build_parser = subparsers.add_parser(
        "build-index", help="Build page-level BM25 index"
    )
    build_parser.add_argument("--doc-id-map", type=str, help="Path to doc_id_map.json")
    build_parser.add_argument("--no-ocr", action="store_true", help="Disable OCR")
    build_parser.set_defaults(func=cmd_build_index)

    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive", help="Interactive search mode"
    )
    interactive_parser.add_argument(
        "--top-k-docs", type=int, default=5, help="Documents per query"
    )
    interactive_parser.add_argument(
        "--top-k-pages", type=int, default=3, help="Pages per document"
    )
    interactive_parser.add_argument(
        "--max-citations", type=int, default=10, help="Max citations"
    )
    interactive_parser.set_defaults(func=cmd_interactive)

    # Build embeddings command
    embed_parser = subparsers.add_parser(
        "build-embeddings", help="Build page-level embeddings (semantic)"
    )
    embed_parser.add_argument(
        "--provider",
        default="local",
        choices=["local", "gemini"],
        help="Embedding provider",
    )
    embed_parser.add_argument(
        "--model", default="BAAI/bge-small-en-v1.5", help="Embedding model"
    )
    embed_parser.add_argument(
        "--batch-size", type=int, default=64, help="Batch size (default: 64)"
    )
    embed_parser.add_argument(
        "--output",
        type=str,
        help="Output path for .npz (default: config.page_embeddings_path)",
    )
    embed_parser.set_defaults(func=cmd_build_embeddings)

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate system components"
    )
    validate_parser.set_defaults(func=cmd_validate)

    # Parse args
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
