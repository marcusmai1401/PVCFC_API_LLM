"""
Validate chunks data quality before re-indexing

Checks:
1. Required fields present
2. Data types correct
3. Tags quality for CAD-like documents
4. Page consistency
5. Missing values
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from loguru import logger


class ChunkValidator:
    def __init__(self, chunks_file: Path):
        self.chunks_file = chunks_file
        self.errors = []
        self.warnings = []
        self.stats = defaultdict(int)

    def load_chunks(self, sample_size: int = None) -> List[dict]:
        """Load chunks from JSONL file"""
        chunks = []
        logger.info(f"Loading chunks from {self.chunks_file}")

        with open(self.chunks_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    chunk = json.loads(line)
                    chunks.append(chunk)
                except json.JSONDecodeError as e:
                    self.errors.append(f"Line {line_num}: Invalid JSON - {e}")

        self.stats["total_chunks"] = len(chunks)
        logger.info(f"Loaded {len(chunks)} chunks")

        if sample_size and sample_size < len(chunks):
            logger.info(f"Sampling {sample_size} random chunks for validation")
            chunks = random.sample(chunks, sample_size)
            self.stats["sampled_chunks"] = sample_size

        return chunks

    def validate_required_fields(self, chunks: List[dict]):
        """Check that all required fields are present"""
        logger.info("Validating required fields...")

        required_root = ["chunk_id", "text", "doc_id", "page_start", "page_end"]
        required_metadata = ["page", "doc_type"]

        for i, chunk in enumerate(chunks):
            # Check root fields
            for field in required_root:
                if field not in chunk:
                    self.errors.append(f"Chunk {i}: Missing root field '{field}'")
                elif chunk[field] is None:
                    self.errors.append(f"Chunk {i}: Root field '{field}' is None")

            # Check metadata fields
            metadata = chunk.get("metadata", {})
            if not metadata:
                self.errors.append(f"Chunk {i}: Missing 'metadata' object")
                continue

            for field in required_metadata:
                if field not in metadata:
                    self.errors.append(f"Chunk {i}: Missing metadata field '{field}'")
                elif metadata[field] is None:
                    self.warnings.append(f"Chunk {i}: metadata.{field} is None")

        self.stats["required_field_checks"] = len(chunks)

    def validate_data_types(self, chunks: List[dict]):
        """Check data types are correct"""
        logger.info("Validating data types...")

        for i, chunk in enumerate(chunks):
            # Check integers
            if "page_start" in chunk and not isinstance(chunk["page_start"], int):
                self.errors.append(
                    f"Chunk {i}: page_start is not int: {type(chunk['page_start'])}"
                )
            if "page_end" in chunk and not isinstance(chunk["page_end"], int):
                self.errors.append(
                    f"Chunk {i}: page_end is not int: {type(chunk['page_end'])}"
                )
            if (
                "chunk_index" in chunk
                and chunk["chunk_index"] is not None
                and not isinstance(chunk["chunk_index"], int)
            ):
                self.errors.append(
                    f"Chunk {i}: chunk_index is not int: {type(chunk['chunk_index'])}"
                )

            # Check strings
            if "chunk_id" in chunk and not isinstance(chunk["chunk_id"], str):
                self.errors.append(
                    f"Chunk {i}: chunk_id is not str: {type(chunk['chunk_id'])}"
                )
            if "doc_id" in chunk and not isinstance(chunk["doc_id"], str):
                self.errors.append(
                    f"Chunk {i}: doc_id is not str: {type(chunk['doc_id'])}"
                )
            if "text" in chunk and not isinstance(chunk["text"], str):
                self.errors.append(f"Chunk {i}: text is not str: {type(chunk['text'])}")

            # Check metadata types
            metadata = chunk.get("metadata", {})
            if (
                "page" in metadata
                and metadata["page"] is not None
                and not isinstance(metadata["page"], int)
            ):
                self.errors.append(
                    f"Chunk {i}: metadata.page is not int: {type(metadata['page'])}"
                )
            if (
                "tags" in metadata
                and metadata["tags"] is not None
                and not isinstance(metadata["tags"], list)
            ):
                self.errors.append(
                    f"Chunk {i}: metadata.tags is not list: {type(metadata['tags'])}"
                )
            if (
                "tags_raw" in metadata
                and metadata["tags_raw"] is not None
                and not isinstance(metadata["tags_raw"], list)
            ):
                self.errors.append(
                    f"Chunk {i}: metadata.tags_raw is not list: {type(metadata['tags_raw'])}"
                )

    def validate_page_consistency(self, chunks: List[dict]):
        """Check page_start matches metadata.page"""
        logger.info("Validating page consistency...")

        inconsistent = 0
        for i, chunk in enumerate(chunks):
            page_start = chunk.get("page_start")
            metadata_page = chunk.get("metadata", {}).get("page")

            if page_start is not None and metadata_page is not None:
                if page_start != metadata_page:
                    self.warnings.append(
                        f"Chunk {i}: page_start ({page_start}) != metadata.page ({metadata_page})"
                    )
                    inconsistent += 1

        self.stats["page_inconsistencies"] = inconsistent
        logger.info(f"Found {inconsistent} page inconsistencies")

    def validate_tags_quality(self, chunks: List[dict]):
        """Check tags quality for CAD-like documents"""
        logger.info("Validating tags quality...")

        cad_chunks = [
            c for c in chunks if c.get("metadata", {}).get("doc_type") == "CAD-like"
        ]
        non_cad_chunks = [
            c for c in chunks if c.get("metadata", {}).get("doc_type") != "CAD-like"
        ]

        self.stats["cad_chunks"] = len(cad_chunks)
        self.stats["non_cad_chunks"] = len(non_cad_chunks)

        # Check CAD-like documents have tags
        cad_with_tags = 0
        cad_without_tags = 0

        for chunk in cad_chunks:
            tags = chunk.get("metadata", {}).get("tags", [])
            if tags:
                cad_with_tags += 1
            else:
                cad_without_tags += 1

        self.stats["cad_with_tags"] = cad_with_tags
        self.stats["cad_without_tags"] = cad_without_tags

        if cad_without_tags > 0:
            self.warnings.append(
                f"{cad_without_tags}/{len(cad_chunks)} CAD-like chunks have no tags"
            )

        # Sample tags from CAD documents
        sample_tags = []
        for chunk in cad_chunks[:10]:
            tags = chunk.get("metadata", {}).get("tags", [])
            if tags:
                sample_tags.extend(tags[:3])

        logger.info(f"Sample tags from CAD documents: {sample_tags[:20]}")
        self.stats["sample_tags"] = len(sample_tags)

    def check_doc_type_distribution(self, chunks: List[dict]):
        """Count doc_type distribution"""
        logger.info("Checking doc_type distribution...")

        doc_types = defaultdict(int)
        for chunk in chunks:
            doc_type = chunk.get("metadata", {}).get("doc_type", "unknown")
            doc_types[doc_type] += 1

        for doc_type, count in doc_types.items():
            self.stats[f"doc_type_{doc_type}"] = count
            logger.info(f"  {doc_type}: {count}")

    def check_missing_values(self, chunks: List[dict]):
        """Check for None/null values in important fields"""
        logger.info("Checking for missing values...")

        fields_to_check = {
            "doc_id": 0,
            "page_start": 0,
            "page_end": 0,
            "metadata.page": 0,
            "metadata.doc_type": 0,
        }

        for chunk in chunks:
            if chunk.get("doc_id") is None:
                fields_to_check["doc_id"] += 1
            if chunk.get("page_start") is None:
                fields_to_check["page_start"] += 1
            if chunk.get("page_end") is None:
                fields_to_check["page_end"] += 1

            metadata = chunk.get("metadata", {})
            if metadata.get("page") is None:
                fields_to_check["metadata.page"] += 1
            if metadata.get("doc_type") is None:
                fields_to_check["metadata.doc_type"] += 1

        for field, count in fields_to_check.items():
            if count > 0:
                self.errors.append(f"{count} chunks have None value in '{field}'")
                self.stats[f"missing_{field}"] = count

    def generate_report(self) -> Dict:
        """Generate validation report"""
        return {
            "status": "PASS" if len(self.errors) == 0 else "FAIL",
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": dict(self.stats),
        }


def main():
    parser = argparse.ArgumentParser(description="Validate chunks data quality")
    parser.add_argument(
        "--chunks-jsonl", type=Path, required=True, help="Path to chunks JSONL file"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=500,
        help="Number of chunks to sample for validation (default: 500, 0=all)",
    )
    parser.add_argument(
        "--output", type=Path, help="Output validation report to JSON file"
    )

    args = parser.parse_args()

    if not args.chunks_jsonl.exists():
        logger.error(f"Chunks file not found: {args.chunks_jsonl}")
        return 1

    # Validate
    validator = ChunkValidator(args.chunks_jsonl)

    sample_size = args.sample_size if args.sample_size > 0 else None
    chunks = validator.load_chunks(sample_size=sample_size)

    if not chunks:
        logger.error("No chunks loaded!")
        return 1

    # Run validations
    validator.validate_required_fields(chunks)
    validator.validate_data_types(chunks)
    validator.validate_page_consistency(chunks)
    validator.validate_tags_quality(chunks)
    validator.check_doc_type_distribution(chunks)
    validator.check_missing_values(chunks)

    # Generate report
    report = validator.generate_report()

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION REPORT")
    logger.info("=" * 70)
    logger.info(f"Status: {report['status']}")
    logger.info(f"Errors: {len(report['errors'])}")
    logger.info(f"Warnings: {len(report['warnings'])}")
    logger.info("")

    if report["errors"]:
        logger.error("ERRORS:")
        for error in report["errors"][:20]:  # Show first 20
            logger.error(f"  - {error}")
        if len(report["errors"]) > 20:
            logger.error(f"  ... and {len(report['errors']) - 20} more errors")

    if report["warnings"]:
        logger.warning("WARNINGS:")
        for warning in report["warnings"][:20]:  # Show first 20
            logger.warning(f"  - {warning}")
        if len(report["warnings"]) > 20:
            logger.warning(f"  ... and {len(report['warnings']) - 20} more warnings")

    logger.info("")
    logger.info("STATS:")
    for key, value in report["stats"].items():
        logger.info(f"  {key}: {value}")

    # Save report
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"\nReport saved to: {args.output}")

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    exit(main())
