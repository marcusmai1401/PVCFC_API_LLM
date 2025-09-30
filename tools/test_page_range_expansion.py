#!/usr/bin/env python
"""
Test Page Range Expansion
Tests the page-range expansion algorithm for retrieval
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger
from rich.console import Console
from rich.table import Table

from app.rag.page_range_expander import PageCluster, PageRangeConfig, PageRangeExpander
from app.rag.query_transform import QueryTransformer, TransformedQuery
from app.rag.retriever import HybridRetriever, HybridSearchConfig, RetrievalResult

console = Console()


def create_mock_results() -> List[RetrievalResult]:
    """Create mock retrieval results for testing"""
    mock_results = [
        # Document 1: pages 5, 6, 7, 8 (consecutive, high score)
        RetrievalResult(
            chunk_id="doc1_p5_c1",
            text="Content from doc1 page 5",
            score=0.9,
            source="bm25",
            metadata={"doc_id": "doc1", "page": 5},
            doc_id="doc1",
            page=5,
        ),
        RetrievalResult(
            chunk_id="doc1_p6_c1",
            text="Content from doc1 page 6",
            score=0.85,
            source="bm25",
            metadata={"doc_id": "doc1", "page": 6},
            doc_id="doc1",
            page=6,
        ),
        RetrievalResult(
            chunk_id="doc1_p7_c1",
            text="Content from doc1 page 7",
            score=0.8,
            source="faiss",
            metadata={"doc_id": "doc1", "page": 7},
            doc_id="doc1",
            page=7,
        ),
        RetrievalResult(
            chunk_id="doc1_p8_c1",
            text="Content from doc1 page 8",
            score=0.75,
            source="faiss",
            metadata={"doc_id": "doc1", "page": 8},
            doc_id="doc1",
            page=8,
        ),
        # Document 1: page 15 (isolated, lower score)
        RetrievalResult(
            chunk_id="doc1_p15_c1",
            text="Content from doc1 page 15",
            score=0.6,
            source="bm25",
            metadata={"doc_id": "doc1", "page": 15},
            doc_id="doc1",
            page=15,
        ),
        # Document 2: pages 2, 3 (consecutive)
        RetrievalResult(
            chunk_id="doc2_p2_c1",
            text="Content from doc2 page 2",
            score=0.7,
            source="faiss",
            metadata={"doc_id": "doc2", "page": 2},
            doc_id="doc2",
            page=2,
        ),
        RetrievalResult(
            chunk_id="doc2_p3_c1",
            text="Content from doc2 page 3",
            score=0.65,
            source="bm25",
            metadata={"doc_id": "doc2", "page": 3},
            doc_id="doc2",
            page=3,
        ),
        # Document 3: pages 1, 3 (gap of 1)
        RetrievalResult(
            chunk_id="doc3_p1_c1",
            text="Content from doc3 page 1",
            score=0.55,
            source="bm25",
            metadata={"doc_id": "doc3", "page": 1},
            doc_id="doc3",
            page=1,
        ),
        RetrievalResult(
            chunk_id="doc3_p3_c1",
            text="Content from doc3 page 3",
            score=0.5,
            source="faiss",
            metadata={"doc_id": "doc3", "page": 3},
            doc_id="doc3",
            page=3,
        ),
    ]

    return mock_results


def test_clustering(config: PageRangeConfig):
    """Test page clustering algorithm"""
    console.print("\n[bold blue]Testing Page Clustering[/bold blue]")

    # Create mock results
    results = create_mock_results()

    # Initialize expander
    expander = PageRangeExpander(config)

    # Analyze clusters
    stats = expander.analyze_clusters(results)

    console.print(f"\n📊 Clustering Analysis:")
    console.print(f"  Total results: {stats['total_results']}")
    console.print(f"  Unique documents: {stats['unique_documents']}")
    console.print(f"  Total clusters: {stats['total_clusters']}")

    # Display clusters table
    if stats["clusters"]:
        table = Table(title="Page Clusters")
        table.add_column("Document", style="cyan")
        table.add_column("Page Range", style="yellow")
        table.add_column("Pages", style="green")
        table.add_column("Total Score", style="magenta")
        table.add_column("Avg Score", style="blue")

        for cluster in stats["clusters"]:
            table.add_row(
                cluster["doc_id"],
                cluster["page_range"],
                str(cluster["page_count"]),
                f"{cluster['total_score']:.3f}",
                f"{cluster['avg_score']:.3f}",
            )

        console.print(table)

    return stats


def test_expansion(config: PageRangeConfig):
    """Test page-range expansion"""
    console.print("\n[bold blue]Testing Page-Range Expansion[/bold blue]")

    # Create mock results
    original_results = create_mock_results()

    # Initialize expander
    expander = PageRangeExpander(config)

    # Expand results
    expanded_results = expander.expand_results(original_results)

    console.print(f"\n📈 Expansion Results:")
    console.print(f"  Original results: {len(original_results)}")
    console.print(f"  Expanded results: {len(expanded_results)}")

    # Show before/after comparison
    console.print("\n[bold]Original Distribution:[/bold]")
    doc_pages_before = {}
    for result in original_results:
        if result.doc_id not in doc_pages_before:
            doc_pages_before[result.doc_id] = []
        doc_pages_before[result.doc_id].append(result.page)

    for doc_id, pages in sorted(doc_pages_before.items()):
        console.print(f"  {doc_id}: pages {sorted(pages)}")

    console.print("\n[bold]After Expansion:[/bold]")
    doc_pages_after = {}
    for result in expanded_results:
        doc_id = result.doc_id or result.metadata.get("doc_id")
        page = result.page or result.metadata.get("page", 1)
        if doc_id not in doc_pages_after:
            doc_pages_after[doc_id] = []
        doc_pages_after[doc_id].append(page)

    for doc_id, pages in sorted(doc_pages_after.items()):
        console.print(f"  {doc_id}: pages {sorted(pages)}")

    return expanded_results


def test_with_retriever(query: str):
    """Test page-range expansion with actual retriever"""
    console.print("\n[bold blue]Testing with HybridRetriever[/bold blue]")

    # Configure retriever with page-range expansion
    config = HybridSearchConfig(
        k_bm25=20,
        k_faiss=20,
        top_rrf=10,
        enable_page_range_expansion=True,
        max_pages_to_scan=5,
        min_cluster_score=0.2,
        page_gap_tolerance=1,
        expand_parent=False,  # Disable parent expansion to test page-range
    )

    try:
        # Initialize retriever
        retriever = HybridRetriever(
            bm25_index_dir="artifacts/index/bm25",
            faiss_index_dir="artifacts/index/faiss",
            config=config,
        )

        # Transform query
        transformer = QueryTransformer()
        transformed = transformer.transform(query)

        # Search with page-range expansion
        results = retriever.search(transformed, config)

        console.print(f"\n🔍 Query: '{query}'")
        console.print(f"📄 Retrieved {len(results)} results")

        # Analyze page distribution
        doc_pages = {}
        for result in results:
            doc_id = result.doc_id or result.metadata.get("doc_id", "unknown")
            page = result.page or result.metadata.get("page", 1)
            if doc_id not in doc_pages:
                doc_pages[doc_id] = []
            doc_pages[doc_id].append((page, result.score))

        # Display results
        table = Table(title="Retrieved Pages with Expansion")
        table.add_column("Document", style="cyan")
        table.add_column("Pages", style="yellow")
        table.add_column("Score Range", style="green")

        for doc_id, page_scores in sorted(doc_pages.items()):
            pages = [p for p, _ in page_scores]
            scores = [s for _, s in page_scores]
            table.add_row(
                doc_id[:40],
                str(sorted(pages)),
                f"{min(scores):.3f} - {max(scores):.3f}",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure indices are loaded[/yellow]")


def test_config_variations():
    """Test different configuration variations"""
    console.print("\n[bold blue]Testing Configuration Variations[/bold blue]")

    configs = [
        ("Default", PageRangeConfig()),
        (
            "Strict",
            PageRangeConfig(
                max_pages_to_scan=3, min_cluster_score=0.5, gap_tolerance=0
            ),
        ),
        (
            "Relaxed",
            PageRangeConfig(
                max_pages_to_scan=10, min_cluster_score=0.1, gap_tolerance=2
            ),
        ),
        ("Disabled", PageRangeConfig(enable_expansion=False)),
    ]

    results = create_mock_results()

    for name, config in configs:
        console.print(f"\n[yellow]Config: {name}[/yellow]")
        console.print(f"  max_pages: {config.max_pages_to_scan}")
        console.print(f"  min_score: {config.min_cluster_score}")
        console.print(f"  gap_tolerance: {config.gap_tolerance}")

        expander = PageRangeExpander(config)
        stats = expander.analyze_clusters(results)
        expanded = expander.expand_results(results)

        console.print(f"  → Clusters: {stats['total_clusters']}")
        console.print(f"  → Expanded results: {len(expanded)}")


def main():
    parser = argparse.ArgumentParser(description="Test page-range expansion")
    parser.add_argument("--query", type=str, help="Query to test with retriever")
    parser.add_argument(
        "--max-pages", type=int, default=5, help="Maximum pages to scan (default: 5)"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.1,
        help="Minimum cluster score (default: 0.1)",
    )
    parser.add_argument(
        "--gap-tolerance", type=int, default=1, help="Page gap tolerance (default: 1)"
    )
    parser.add_argument("--test-all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    console.print("[bold]Page Range Expansion Test Tool[/bold]\n")

    # Create config from arguments
    config = PageRangeConfig(
        max_pages_to_scan=args.max_pages,
        min_cluster_score=args.min_score,
        gap_tolerance=args.gap_tolerance,
    )

    if args.test_all or not args.query:
        # Run all tests
        test_clustering(config)
        test_expansion(config)
        test_config_variations()

        if args.query:
            test_with_retriever(args.query)
    else:
        # Test with actual retriever
        test_with_retriever(args.query)


if __name__ == "__main__":
    main()
