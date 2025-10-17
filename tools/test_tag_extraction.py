#!/usr/bin/env python
"""
Test Tag Extraction on Single PDF
Quick test tool for CAD-like tag extraction pipeline

Usage:
    python tools/test_tag_extraction.py --pdf "path/to/cad.pdf" --doc-id "test_001"
"""

import argparse
import sys
from pathlib import (  # Force reload .env`nload_dotenv(override=True)
    Path`nfrom,
    dotenv,
    import,
    load_dotenv`n`n,
)

from loguru import logger
from rich.console import Console
from rich.json import JSON

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_config
from app.ingestion.tags.orchestrator import TagExtractionOrchestrator


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test tag extraction on single PDF")
    parser.add_argument("--pdf", type=Path, required=True, help="Path to PDF file")
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Document ID (default: filename without extension)",
    )
    parser.add_argument(
        "--enable-crops",
        action="store_true",
        help="Generate bbox crops (default: lazy mode)",
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        logger.error(f"PDF file not found: {args.pdf}")
        sys.exit(1)

    # Default doc_id from filename
    if args.doc_id is None:
        args.doc_id = args.pdf.stem

    console = Console()

    console.print("\n" + "=" * 80, style="cyan")
    console.print("CAD-LIKE TAG EXTRACTION TEST", style="cyan bold")
    console.print("=" * 80 + "\n", style="cyan")

    console.print(f"PDF: {args.pdf}", style="yellow")
    console.print(f"Doc ID: {args.doc_id}", style="yellow")
    console.print(f"Generate crops: {args.enable_crops}\n", style="yellow")

    # Initialize orchestrator
    try:
        orchestrator = TagExtractionOrchestrator(
            enable_crops=args.enable_crops,
            lazy_crops=not args.enable_crops,
        )

        if not orchestrator.enabled:
            console.print(
                "[red]Tag extraction is disabled![/red]", style="bold"
            )
            console.print(
                "Enable with: ENABLE_PID_TAGS=true in .env", style="yellow"
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Failed to initialize orchestrator: {e}[/red]")
        sys.exit(1)

    # Process document
    console.print("Processing...\n", style="cyan")

    try:
        result = orchestrator.process_document(args.pdf, args.doc_id)

        if result is None:
            console.print("[yellow]Document is not CAD-like[/yellow]", style="bold")
            console.print("No tags extracted.\n")
            sys.exit(0)

        # Display results
        console.print("[green bold]✓ Processing complete![/green bold]\n")

        console.print("Results:", style="cyan bold")
        console.print(JSON(json.dumps(result, indent=2)))

        # Check artifacts
        config = get_config()

        console.print("\nArtifacts created:", style="cyan bold")

        # Tags file
        tags_file = config.ENTITIES_DIR / "tags.jsonl"
        if tags_file.exists():
            console.print(f"  [green]✓[/green] {tags_file}")
        else:
            console.print(f"  [red]✗[/red] {tags_file} (not found)")

        # Crops directory
        if args.enable_crops:
            crops_count = len(list(config.CROPS_DIR.glob("*.png")))
            console.print(f"  [green]✓[/green] {config.CROPS_DIR} ({crops_count} PNG files)")

        # Telemetry log
        log_file = config.LOGS_DIR / "tag_extraction_telemetry.jsonl"
        if log_file.exists():
            console.print(f"  [green]✓[/green] {log_file}")

        console.print("\n" + "=" * 80 + "\n", style="cyan")

        sys.exit(0)

    except Exception as e:
        console.print(f"[red bold]✗ Processing failed: {e}[/red bold]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
