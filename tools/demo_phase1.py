"""
Demo script for Phase 1 modules
Shows PDF detection and text extraction in action
"""
import json
from pathlib import Path
from app.rag.document_detector import DocumentDetector, PDFType
from app.rag.extractors.vector_extractor import VectorExtractor
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def demo_pdf_detection():
    """Demo PDF type detection"""
    console.print("\n[bold cyan]===== PDF TYPE DETECTION DEMO =====[/bold cyan]\n")
    
    detector = DocumentDetector()
    sample_dir = Path("data/raw/samples")
    
    # Create a table for results
    table = Table(title="PDF Detection Results")
    table.add_column("File", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Confidence", style="yellow")
    table.add_column("Pages", style="magenta")
    table.add_column("Vector/Scan", style="blue")
    
    for pdf_file in sample_dir.glob("*.pdf"):
        result = detector.detect_pdf_type(pdf_file)
        
        type_str = result['type'].value if hasattr(result['type'], 'value') else str(result['type'])
        confidence = f"{result.get('confidence', 0):.2%}"
        pages = str(result.get('total_pages', 0))
        ratio = f"{result.get('vector_pages', 0)}/{result.get('scan_pages', 0)}"
        
        table.add_row(pdf_file.name, type_str, confidence, pages, ratio)
        
    console.print(table)
    
    # Show detailed analysis for one file
    console.print("\n[bold]Detailed Analysis: sample_text.pdf[/bold]")
    sample_pdf = sample_dir / "sample_text.pdf"
    if sample_pdf.exists():
        result = detector.detect_pdf_type(sample_pdf)
        metadata = detector.get_pdf_metadata(sample_pdf)
        
        # Page analysis
        console.print("\n[yellow]Page Analysis:[/yellow]")
        for page_info in result['page_analysis'][:2]:  # Show first 2 pages
            console.print(f"  Page {page_info['page_num']}: "
                         f"Text: {page_info['text_length']} chars, "
                         f"Blocks: {page_info['block_count']}, "
                         f"Images: {page_info['image_count']}")
        
        # Metadata
        console.print("\n[yellow]Metadata:[/yellow]")
        console.print(f"  File size: {metadata.get('file_size', 0):,} bytes")
        console.print(f"  Encrypted: {metadata.get('encrypted', False)}")
        console.print(f"  Producer: {metadata.get('producer', 'N/A')}")


def demo_text_extraction():
    """Demo text extraction from PDFs"""
    console.print("\n[bold cyan]===== TEXT EXTRACTION DEMO =====[/bold cyan]\n")
    
    extractor = VectorExtractor()
    sample_pdf = Path("data/raw/samples/sample_text.pdf")
    
    if not sample_pdf.exists():
        console.print("[red]Sample PDF not found![/red]")
        return
    
    # Extract with structure detection
    result = extractor.extract_with_structure(sample_pdf)
    
    # Show statistics
    stats = result['statistics']
    console.print(Panel(
        f"[green]Total Pages:[/green] {result['total_pages']}\n"
        f"[green]Total Blocks:[/green] {stats['total_blocks']}\n"
        f"[green]Total Characters:[/green] {stats['total_characters']:,}\n"
        f"[green]Avg Blocks/Page:[/green] {stats['avg_blocks_per_page']:.1f}",
        title="Extraction Statistics",
        border_style="blue"
    ))
    
    # Show first page content
    console.print("\n[bold]First Page Content:[/bold]")
    first_page = result['pages'][0]
    
    # Group blocks by structure type
    structure_groups = {}
    for block in first_page['blocks']:
        structure_type = block.get('structure_type', 'unknown')
        if structure_type not in structure_groups:
            structure_groups[structure_type] = []
        structure_groups[structure_type].append(block)
    
    # Display blocks by type
    for structure_type, blocks in structure_groups.items():
        console.print(f"\n[yellow]{structure_type.upper()}:[/yellow]")
        for block in blocks[:3]:  # Show first 3 of each type
            text_preview = block['text'][:100] + "..." if len(block['text']) > 100 else block['text']
            console.print(f"  • {text_preview}")
            console.print(f"    [dim]BBox: {block['bbox']}, Font: {block.get('font_size', 'N/A')}pt[/dim]")


def demo_datasheet_extraction():
    """Demo extraction from datasheet PDF"""
    console.print("\n[bold cyan]===== DATASHEET EXTRACTION DEMO =====[/bold cyan]\n")
    
    extractor = VectorExtractor()
    datasheet_pdf = Path("data/raw/samples/sample_datasheet.pdf")
    
    if not datasheet_pdf.exists():
        console.print("[red]Datasheet PDF not found![/red]")
        return
    
    result = extractor.extract_from_pdf(datasheet_pdf)
    
    # Extract table-like content
    console.print("[bold]Extracted Technical Specifications:[/bold]\n")
    
    # Create a table from extracted text
    full_text = result['pages'][0]['full_text']
    
    # Parse table data (simple approach for demo)
    lines = full_text.split('\n')
    table_data = []
    in_table = False
    
    for line in lines:
        if "Parameter" in line and "Value" in line:
            in_table = True
            continue
        if in_table and line.strip():
            if "----" in line:
                continue
            if "Notes:" in line:
                break
            # Try to parse as table row
            parts = line.split()
            if len(parts) >= 2:
                param = parts[0]
                value = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
                unit = parts[-1] if len(parts) > 2 else "-"
                table_data.append((param, value, unit))
    
    # Display as table
    if table_data:
        spec_table = Table(title="Technical Specifications")
        spec_table.add_column("Parameter", style="cyan")
        spec_table.add_column("Value", style="green")
        spec_table.add_column("Unit", style="yellow")
        
        for row in table_data[:8]:  # Show first 8 rows
            spec_table.add_row(*row)
        
        console.print(spec_table)


def demo_mixed_pdf():
    """Demo processing of mixed content PDF"""
    console.print("\n[bold cyan]===== MIXED CONTENT PDF DEMO =====[/bold cyan]\n")
    
    detector = DocumentDetector()
    extractor = VectorExtractor()
    mixed_pdf = Path("data/raw/samples/sample_mixed.pdf")
    
    if not mixed_pdf.exists():
        console.print("[red]Mixed PDF not found![/red]")
        return
    
    # Detect type
    detection = detector.detect_pdf_type(mixed_pdf)
    console.print(f"[bold]Detection Result:[/bold] {detection['type'].value}")
    
    # Extract content
    extraction = extractor.extract_from_pdf(mixed_pdf)
    
    # Show page-by-page analysis
    console.print("\n[bold]Page-by-Page Analysis:[/bold]")
    for page_data in extraction['pages']:
        page_num = page_data['page_num']
        text_length = page_data['char_count']
        block_count = page_data['block_count']
        
        if text_length > 100:
            page_type = "Text Content"
            style = "green"
        else:
            page_type = "Mostly Non-Text (Diagram/Scan)"
            style = "yellow"
        
        console.print(f"  Page {page_num + 1}: [{style}]{page_type}[/{style}]")
        console.print(f"    Characters: {text_length}, Blocks: {block_count}")
        
        if text_length > 0:
            preview = page_data['full_text'][:150] + "..." if len(page_data['full_text']) > 150 else page_data['full_text']
            console.print(f"    Preview: [dim]{preview}[/dim]")


def main():
    """Run all demos"""
    console.print("[bold magenta]" + "="*60 + "[/bold magenta]")
    console.print("[bold magenta]    PHASE 1 MODULES DEMONSTRATION[/bold magenta]")
    console.print("[bold magenta]" + "="*60 + "[/bold magenta]")
    
    # Run demos
    demo_pdf_detection()
    console.print("\n" + "-"*60 + "\n")
    
    demo_text_extraction()
    console.print("\n" + "-"*60 + "\n")
    
    demo_datasheet_extraction()
    console.print("\n" + "-"*60 + "\n")
    
    demo_mixed_pdf()
    
    console.print("\n[bold green][SUCCESS] All demos completed successfully![/bold green]")
    console.print("\n[dim]These modules work completely offline without any API keys.[/dim]")


if __name__ == "__main__":
    main()
