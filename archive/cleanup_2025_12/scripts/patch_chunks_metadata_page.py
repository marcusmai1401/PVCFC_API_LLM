"""
Patch chunks.jsonl to add missing metadata.page field

This script:
1. Backs up the original chunks.jsonl
2. Reads each chunk and adds metadata.page = page_start if missing
3. Writes to a new file
4. Validates the result
5. Optionally replaces the original

Usage:
    python scripts/audit/patch_chunks_metadata_page.py \
        --chunks-jsonl artifacts/ingestion/chunks/chunks.jsonl \
        --output artifacts/ingestion/chunks/chunks_patched.jsonl \
        --backup
"""
import argparse
import json
import shutil
from pathlib import Path
from typing import Dict

from loguru import logger


def patch_chunk(chunk: Dict) -> tuple[Dict, bool]:
    """
    Patch a single chunk to add metadata.page if missing

    Args:
        chunk: Original chunk dict

    Returns:
        Tuple of (patched_chunk, was_patched)
    """
    was_patched = False

    # Ensure metadata exists
    if "metadata" not in chunk:
        chunk["metadata"] = {}

    metadata = chunk["metadata"]

    # If metadata.page is missing, fill from page_start
    if "page" not in metadata or metadata["page"] is None:
        page_start = chunk.get("page_start")
        if page_start is not None:
            metadata["page"] = page_start
            was_patched = True
            logger.debug(
                f"Patched chunk {chunk.get('chunk_id', 'unknown')}: metadata.page = {page_start}"
            )
        else:
            # Last resort: use 1
            metadata["page"] = 1
            was_patched = True
            logger.warning(
                f"Chunk {chunk.get('chunk_id', 'unknown')} has no page_start, defaulting to 1"
            )

    return chunk, was_patched


def patch_chunks_file(input_file: Path, output_file: Path, backup: bool = True) -> Dict:
    """
    Patch chunks file to add missing metadata.page

    Args:
        input_file: Input chunks.jsonl file
        output_file: Output patched file
        backup: Whether to create backup

    Returns:
        Statistics dict
    """
    stats = {
        "total_chunks": 0,
        "patched_chunks": 0,
        "unchanged_chunks": 0,
        "errors": 0,
    }

    # Backup if requested
    if backup:
        backup_file = input_file.with_suffix(".jsonl.backup")
        logger.info(f"Creating backup: {backup_file}")
        shutil.copy2(input_file, backup_file)
        logger.success(f"✅ Backup created: {backup_file}")

    # Process chunks
    logger.info(f"Reading chunks from: {input_file}")
    logger.info(f"Writing patched chunks to: {output_file}")

    with open(input_file, "r", encoding="utf-8") as fin, open(
        output_file, "w", encoding="utf-8"
    ) as fout:
        for line_num, line in enumerate(fin, 1):
            try:
                # Parse chunk
                chunk = json.loads(line)
                stats["total_chunks"] += 1

                # Patch chunk
                patched_chunk, was_patched = patch_chunk(chunk)

                if was_patched:
                    stats["patched_chunks"] += 1
                else:
                    stats["unchanged_chunks"] += 1

                # Write patched chunk
                fout.write(json.dumps(patched_chunk, ensure_ascii=False) + "\n")

                # Progress log every 10k chunks
                if line_num % 10000 == 0:
                    logger.info(f"  Processed {line_num} chunks...")

            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: Invalid JSON - {e}")
                stats["errors"] += 1
                # Write original line to preserve data
                fout.write(line)

            except Exception as e:
                logger.error(f"Line {line_num}: Error processing chunk - {e}")
                stats["errors"] += 1
                # Write original line to preserve data
                fout.write(line)

    return stats


def validate_patched_file(patched_file: Path) -> bool:
    """
    Validate that the patched file has all chunks with metadata.page

    Args:
        patched_file: Path to patched file

    Returns:
        True if valid, False otherwise
    """
    logger.info(f"Validating patched file: {patched_file}")

    total = 0
    missing_page = 0

    with open(patched_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)
                total += 1

                metadata = chunk.get("metadata", {})
                if "page" not in metadata or metadata["page"] is None:
                    missing_page += 1
                    logger.error(f"Line {line_num}: Still missing metadata.page!")

            except json.JSONDecodeError:
                logger.error(f"Line {line_num}: Invalid JSON")
                return False

    if missing_page > 0:
        logger.error(
            f"❌ Validation FAILED: {missing_page}/{total} chunks still missing metadata.page"
        )
        return False

    logger.success(f"✅ Validation PASSED: All {total} chunks have metadata.page")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Patch chunks.jsonl to add missing metadata.page"
    )
    parser.add_argument(
        "--chunks-jsonl",
        type=Path,
        required=True,
        help="Path to input chunks.jsonl file",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Path to output patched file"
    )
    parser.add_argument(
        "--backup", action="store_true", help="Create backup of original file"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace original file with patched version (after validation)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Validate patched file (default: True)",
    )

    args = parser.parse_args()

    # Validate input
    if not args.chunks_jsonl.exists():
        logger.error(f"Input file not found: {args.chunks_jsonl}")
        return 1

    if args.output.exists() and args.output == args.chunks_jsonl:
        logger.error("Output file cannot be the same as input file!")
        return 1

    # Patch chunks
    logger.info("=" * 70)
    logger.info("PATCHING CHUNKS METADATA")
    logger.info("=" * 70)

    stats = patch_chunks_file(
        input_file=args.chunks_jsonl, output_file=args.output, backup=args.backup
    )

    # Print statistics
    logger.info("\n" + "=" * 70)
    logger.info("PATCH STATISTICS")
    logger.info("=" * 70)
    logger.info(f"Total chunks: {stats['total_chunks']}")
    logger.info(f"Patched chunks: {stats['patched_chunks']}")
    logger.info(f"Unchanged chunks: {stats['unchanged_chunks']}")
    logger.info(f"Errors: {stats['errors']}")

    # Validate if requested
    if args.validate:
        logger.info("\n" + "=" * 70)
        logger.info("VALIDATION")
        logger.info("=" * 70)

        if not validate_patched_file(args.output):
            logger.error("❌ Validation failed!")
            return 1

    # Replace original if requested
    if args.replace:
        logger.info("\n" + "=" * 70)
        logger.info("REPLACING ORIGINAL FILE")
        logger.info("=" * 70)

        # Final confirmation
        logger.warning(f"About to replace {args.chunks_jsonl} with {args.output}")

        if args.backup:
            backup_file = args.chunks_jsonl.with_suffix(".jsonl.backup")
            logger.info(f"Backup is available at: {backup_file}")

        # Replace
        shutil.move(str(args.output), str(args.chunks_jsonl))
        logger.success(f"✅ Replaced original file with patched version")

    logger.info("\n" + "=" * 70)
    logger.info("PATCH COMPLETE")
    logger.info("=" * 70)

    if not args.replace:
        logger.info(f"Patched file: {args.output}")
        logger.info(f"To replace original, run with --replace flag")

    return 0


if __name__ == "__main__":
    exit(main())
