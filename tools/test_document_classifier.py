#!/usr/bin/env python
"""
Test Document Classification
Tests both rule-based and LLM-enhanced document classification
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger
from rich.console import Console
from rich.table import Table

from app.ingestion.document_classifier import DocumentClassifier
from app.services.document_classification_llm import DocumentClassificationLLM

console = Console()


def test_rule_based_classification(pdf_path: Path, show_details: bool = False):
    """Test rule-based classification"""
    console.print("\n[bold blue]Testing Rule-Based Classification[/bold blue]")

    classifier = DocumentClassifier()

    # Extract first page text if possible
    first_page_text = None
    try:
        import pymupdf as fitz

        with fitz.open(pdf_path) as doc:
            if len(doc) > 0:
                first_page_text = doc[0].get_text()[:2000]
    except:
        logger.warning("Could not extract first page text")

    # Classify
    doc_type, revision = classifier.classify(
        file_path=pdf_path, first_page_text=first_page_text
    )

    console.print(f"  📄 File: {pdf_path.name}")
    console.print(f"  📁 Type: [green]{doc_type}[/green]")
    console.print(f"  📌 Revision: [yellow]{revision if revision else 'N/A'}[/yellow]")

    if show_details and first_page_text:
        console.print(f"\n  [dim]First page preview (100 chars):[/dim]")
        console.print(f"  [dim]{first_page_text[:100]}...[/dim]")

    return doc_type, revision


def test_llm_classification(
    pdf_path: Path, model_name: str = "gemini", show_details: bool = False
):
    """Test LLM-enhanced classification"""
    console.print("\n[bold blue]Testing LLM-Enhanced Classification[/bold blue]")

    classifier = DocumentClassifier()
    llm_classifier = DocumentClassificationLLM()

    # Extract first page text if possible
    first_page_text = None
    metadata = {}

    try:
        import pymupdf as fitz

        with fitz.open(pdf_path) as doc:
            if len(doc) > 0:
                first_page_text = doc[0].get_text()[:2000]
            # Get metadata
            metadata = doc.metadata
    except:
        logger.warning("Could not extract document content")

    # First get rule-based classification
    rule_type, rule_revision = classifier.classify(
        file_path=pdf_path, first_page_text=first_page_text, metadata=metadata
    )

    console.print(f"  📄 File: {pdf_path.name}")
    console.print(f"  📁 Rule-based Type: [yellow]{rule_type}[/yellow]")

    # If unknown, try LLM
    if rule_type == "unknown":
        console.print("  🤖 Enhancing with LLM...")

        try:
            llm_type, llm_revision, confidence = llm_classifier.classify(
                file_path=pdf_path,
                first_page_text=first_page_text,
                metadata=metadata,
                confidence_threshold=0.6,
            )

            console.print(f"  📁 LLM Type: [green]{llm_type}[/green]")
            console.print(f"  📊 Confidence: [cyan]{confidence:.2f}[/cyan]")
            console.print(
                f"  📌 Revision: [yellow]{llm_revision if llm_revision else 'N/A'}[/yellow]"
            )

            return llm_type, llm_revision
        except Exception as e:
            console.print(f"  ❌ LLM classification failed: {e}")
    else:
        console.print(f"  ✅ Confident rule-based result, skipping LLM")

    return rule_type, rule_revision


def test_with_llm_method(pdf_path: Path, model_name: str = "gemini"):
    """Test using the classify_with_llm method"""
    console.print("\n[bold blue]Testing classify_with_llm Method[/bold blue]")

    classifier = DocumentClassifier()

    # Extract first page text if possible
    first_page_text = None
    metadata = {}

    try:
        import pymupdf as fitz

        with fitz.open(pdf_path) as doc:
            if len(doc) > 0:
                first_page_text = doc[0].get_text()[:2000]
            metadata = doc.metadata
    except:
        pass

    # Use the integrated method
    doc_type, revision = classifier.classify_with_llm(
        file_path=pdf_path,
        first_page_text=first_page_text,
        model_name=model_name,
        metadata=metadata,
    )

    console.print(f"  📄 File: {pdf_path.name}")
    console.print(f"  📁 Final Type: [green]{doc_type}[/green]")
    console.print(f"  📌 Revision: [yellow]{revision if revision else 'N/A'}[/yellow]")

    return doc_type, revision


def batch_test_directory(dir_path: Path, use_llm: bool = False, limit: int = 10):
    """Test classification on multiple PDFs in a directory"""
    console.print(f"\n[bold blue]Batch Testing Directory: {dir_path}[/bold blue]")

    pdf_files = list(dir_path.rglob("*.pdf"))[:limit]

    if not pdf_files:
        console.print("[yellow]No PDF files found[/yellow]")
        return

    # Create results table
    table = Table(title=f"Classification Results ({len(pdf_files)} files)")
    table.add_column("File", style="cyan")
    table.add_column("Rule-Based", style="yellow")
    table.add_column("LLM-Enhanced", style="green")
    table.add_column("Revision", style="magenta")

    classifier = DocumentClassifier()
    llm_classifier = DocumentClassificationLLM() if use_llm else None

    for pdf_path in pdf_files:
        # Get rule-based classification
        rule_type, rule_revision = classifier.classify(file_path=pdf_path)

        # Get LLM classification if enabled and needed
        llm_type = "-"
        final_revision = rule_revision

        if use_llm and rule_type == "unknown":
            try:
                # Extract first page for LLM
                first_page_text = None
                try:
                    import pymupdf as fitz

                    with fitz.open(pdf_path) as doc:
                        if len(doc) > 0:
                            first_page_text = doc[0].get_text()[:1500]
                except:
                    pass

                if llm_classifier:
                    llm_type, llm_revision, _ = llm_classifier.classify(
                        file_path=pdf_path,
                        first_page_text=first_page_text,
                        confidence_threshold=0.6,
                    )
                    final_revision = llm_revision or rule_revision
            except Exception as e:
                llm_type = f"Error: {str(e)[:20]}"

        table.add_row(
            pdf_path.name[:40],
            rule_type,
            llm_type if use_llm else "-",
            final_revision or "-",
        )

    console.print(table)

    # Summary statistics
    console.print("\n[bold]Summary Statistics:[/bold]")
    console.print(f"  Total files: {len(pdf_files)}")

    # Count document types
    from collections import Counter

    rule_types = [classifier.classify(file_path=f)[0] for f in pdf_files]
    type_counts = Counter(rule_types)

    console.print("\n  Document type distribution:")
    for doc_type, count in type_counts.most_common():
        percentage = (count / len(pdf_files)) * 100
        console.print(f"    {doc_type}: {count} ({percentage:.1f}%)")


def create_test_documents():
    """Create sample test documents for classification"""
    console.print("\n[bold blue]Creating Test Documents[/bold blue]")

    test_dir = Path("test_docs")
    test_dir.mkdir(exist_ok=True)

    try:
        import pymupdf as fitz

        # Test document templates
        test_docs = [
            (
                "PID_04_FE_2046_Rev_A.pdf",
                "P&ID Drawing\nFlow Element 04-FE-2046\nRevision A",
            ),
            (
                "Equipment_Datasheet_KT06101.pdf",
                "Technical Data Sheet\nCompressor KT06101\nDesign Parameters",
            ),
            (
                "Operation_Manual_V2.pdf",
                "Operation Manual\nVersion 2.0\nSafety Instructions",
            ),
            ("MOC_2024_001.pdf", "Management of Change\nMOC-2024-001\nChange Request"),
            (
                "RCA_Report_Incident_2024.pdf",
                "Root Cause Analysis\nIncident Investigation\n2024-03-15",
            ),
            (
                "Unknown_Document.pdf",
                "Some random content that doesn't match any pattern",
            ),
        ]

        for filename, content in test_docs:
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), content, fontsize=12)
            doc.save(test_dir / filename)
            doc.close()
            console.print(f"  ✅ Created: {filename}")

        console.print(f"\n[green]Test documents created in {test_dir}[/green]")
        return test_dir

    except ImportError:
        console.print("[red]PyMuPDF not available, cannot create test documents[/red]")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test document classification")
    parser.add_argument("--pdf", type=str, help="Path to PDF file to test")
    parser.add_argument(
        "--dir", type=str, help="Directory containing PDFs for batch testing"
    )
    parser.add_argument(
        "--create-test", action="store_true", help="Create test documents"
    )
    parser.add_argument(
        "--use-llm", action="store_true", help="Use LLM-enhanced classification"
    )
    parser.add_argument(
        "--model", type=str, default="gemini", help="LLM model to use (default: gemini)"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Limit number of files for batch testing"
    )
    parser.add_argument(
        "--details", action="store_true", help="Show detailed information"
    )

    args = parser.parse_args()

    console.print("[bold]Document Classification Test Tool[/bold]\n")

    # Create test documents if requested
    if args.create_test:
        test_dir = create_test_documents()
        if test_dir and not args.dir:
            args.dir = str(test_dir)

    # Test single PDF
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            console.print(f"[red]File not found: {pdf_path}[/red]")
            return

        # Test rule-based
        test_rule_based_classification(pdf_path, args.details)

        # Test LLM if requested
        if args.use_llm:
            test_llm_classification(pdf_path, args.model, args.details)

            # Test integrated method
            test_with_llm_method(pdf_path, args.model)

    # Batch test directory
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            console.print(f"[red]Directory not found: {dir_path}[/red]")
            return

        batch_test_directory(dir_path, args.use_llm, args.limit)

    else:
        console.print("[yellow]Please specify --pdf or --dir for testing[/yellow]")
        console.print("Use --create-test to generate sample documents")


if __name__ == "__main__":
    main()
