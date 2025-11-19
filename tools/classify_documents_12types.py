#!/usr/bin/env python
"""
Document Classification Batch Runner (12 Types)
================================================

Classifies all ingested documents into 12 categories using:
1. Rule-based classification (fast, high confidence cases)
2. Gemini 2.5 Flash LLM (for ambiguous cases)

Output:
- artifacts/classification/document_types_12.jsonl
- artifacts/classification/classification_summary.txt

Usage:
    python tools/classify_documents_12types.py
    python tools/classify_documents_12types.py --dry-run
    python tools/classify_documents_12types.py --limit 10
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.classification.document_type_12 import (
    DocumentType12,
    DocumentType12Result,
    apply_rule_based_classification,
    get_doc_type_display_name,
    should_use_llm,
)
from app.services.document_type_12_llm import DocumentType12LLM
from tools.extract_metadata import (
    extract_doc_type,
    extract_equipment_id,
    extract_equipment_type,
    extract_vendor,
)


class DocumentClassifier12:
    """
    Batch classifier for 12-type document classification
    """

    def __init__(
        self,
        doc_id_map_path: Path,
        markdown_dir: Optional[Path] = None,
        confidence_threshold: float = 0.6,
        llm_skip_threshold: float = 0.85,
        dry_run: bool = False,
    ):
        """
        Initialize batch classifier

        Args:
            doc_id_map_path: Path to doc_id_map.json
            markdown_dir: Optional path to markdown directory for first-page text
            confidence_threshold: Minimum confidence for LLM results (below this -> UNKNOWN)
            llm_skip_threshold: Rule-based confidence to skip LLM (above this -> use rule only)
            dry_run: If True, don't call LLM (for testing)
        """
        self.doc_id_map_path = doc_id_map_path
        self.markdown_dir = markdown_dir
        self.confidence_threshold = confidence_threshold
        self.llm_skip_threshold = llm_skip_threshold
        self.dry_run = dry_run

        # Initialize LLM classifier (unless dry run)
        self.llm_classifier = None if dry_run else DocumentType12LLM()

        # Load doc_id_map
        self.doc_id_map = self._load_doc_id_map()

        # Statistics
        self.stats = {
            "total": 0,
            "rule_only": 0,
            "llm_only": 0,
            "rule_llm": 0,
            "unknown": 0,
            "low_confidence": [],
            "by_category": Counter(),
        }

    def _load_doc_id_map(self) -> Dict[str, str]:
        """Load doc_id to pdf_path mapping"""
        logger.info(f"Loading doc_id_map from {self.doc_id_map_path}")

        with open(self.doc_id_map_path, "r", encoding="utf-8") as f:
            doc_map = json.load(f)

        logger.info(f"Loaded {len(doc_map)} documents")
        return doc_map

    def _load_first_page_text(self, doc_id: str) -> Optional[str]:
        """
        Load full text from markdown file if available

        Args:
            doc_id: Document ID

        Returns:
            Full markdown text (no truncation), or None if not available
        """
        if not self.markdown_dir or not self.markdown_dir.exists():
            return None

        md_file = self.markdown_dir / f"{doc_id}.md"
        if not md_file.exists():
            return None

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Return full content (no truncation)
                return content if content else None
        except Exception as e:
            logger.warning(f"Could not read markdown for {doc_id}: {e}")
            return None

    def classify_document(self, doc_id: str, pdf_path: str) -> DocumentType12Result:
        """
        Classify a single document

        Args:
            doc_id: Document ID
            pdf_path: Path to PDF file

        Returns:
            DocumentType12Result with classification
        """
        path_obj = Path(pdf_path)
        filename = path_obj.name

        # Extract path metadata
        path_metadata = {
            "equipment_type": extract_equipment_type(pdf_path),
            "doc_type": extract_doc_type(pdf_path),
            "equipment_id": extract_equipment_id(pdf_path),
            "vendor": extract_vendor(pdf_path),
        }

        logger.debug(f"Doc {doc_id}: path_metadata = {path_metadata}")

        # FORCE LLM for ALL documents (rule-based disabled)
        use_llm = True

        # Initialize result variables
        final_doc_type = DocumentType12.UNKNOWN
        final_confidence = 0.0
        method = "llm_only"
        raw_llm_doc_type = None
        reasoning = "LLM classification"

        # Call LLM (unless dry run)
        if use_llm and not self.dry_run:
            logger.info(f"Doc {doc_id}: Calling LLM (no rule-based)")

            # Load first page text if available
            first_page_text = self._load_first_page_text(doc_id)

            # Call LLM
            llm_doc_type, llm_confidence, llm_reasoning = self.llm_classifier.classify(
                filename=filename,
                file_path=pdf_path,
                first_page_text=first_page_text,
                path_metadata=path_metadata,
                confidence_threshold=self.confidence_threshold,
            )

            raw_llm_doc_type = llm_doc_type.value

            # Use LLM result directly (no rule-based fallback)
            final_doc_type = llm_doc_type
            final_confidence = llm_confidence
            method = "llm_only"
            reasoning = llm_reasoning

        elif use_llm and self.dry_run:
            # Dry run mode - mark as would-call-LLM
            method = "would_call_llm"
            reasoning = "Dry run - LLM would be called"

        # Create result (parent_category and sub_category auto-derived in __post_init__)
        result = DocumentType12Result(
            doc_id=doc_id,
            pdf_path=pdf_path,
            doc_type_12=final_doc_type.value,
            parent_category="",  # Will be auto-derived from doc_type_12
            confidence=final_confidence,
            method=method,
            raw_llm_doc_type=raw_llm_doc_type,
            reasoning=reasoning,
        )

        # Update statistics
        self.stats["total"] += 1
        if method == "rule_only":
            self.stats["rule_only"] += 1
        elif method == "llm_only":
            self.stats["llm_only"] += 1
        elif method == "rule_llm":
            self.stats["rule_llm"] += 1

        if final_doc_type == DocumentType12.UNKNOWN:
            self.stats["unknown"] += 1

        if final_confidence < self.confidence_threshold:
            self.stats["low_confidence"].append(
                (doc_id, final_confidence, final_doc_type.value)
            )

        self.stats["by_category"][final_doc_type.value] += 1

        return result

    def classify_all(self, limit: Optional[int] = None) -> List[DocumentType12Result]:
        """
        Classify all documents in doc_id_map

        Args:
            limit: Optional limit on number of documents to process (for testing)

        Returns:
            List of DocumentType12Result
        """
        results = []

        doc_items = list(self.doc_id_map.items())
        if limit:
            doc_items = doc_items[:limit]
            logger.info(f"Processing limited to {limit} documents")

        logger.info(f"Starting classification of {len(doc_items)} documents...")

        for doc_id, pdf_path in tqdm(doc_items, desc="Classifying documents"):
            try:
                result = self.classify_document(doc_id, pdf_path)
                results.append(result)

                # Log progress every 10 documents
                if len(results) % 10 == 0:
                    logger.info(
                        f"Progress: {len(results)}/{len(doc_items)} - "
                        f"Rule: {self.stats['rule_only']}, "
                        f"LLM: {self.stats['llm_only']}, "
                        f"Unknown: {self.stats['unknown']}"
                    )

            except Exception as e:
                logger.error(f"Failed to classify {doc_id}: {e}", exc_info=True)
                # Create error result
                results.append(
                    DocumentType12Result(
                        doc_id=doc_id,
                        pdf_path=pdf_path,
                        doc_type_12=DocumentType12.UNKNOWN.value,
                        parent_category=DocumentType12.UNKNOWN.value,
                        confidence=0.0,
                        method="error",
                        reasoning=f"Error: {str(e)}",
                    )
                )

        logger.info(f"Classification complete: {len(results)} documents processed")
        return results

    def save_results(self, results: List[DocumentType12Result], output_path: Path):
        """
        Save classification results to JSONL file

        Args:
            results: List of DocumentType12Result
            output_path: Path to output JSONL file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving results to {output_path}")

        with open(output_path, "w", encoding="utf-8") as f:
            for result in results:
                json_line = json.dumps(result.to_dict(), ensure_ascii=False)
                f.write(json_line + "\n")

        logger.info(f"Saved {len(results)} results")

    def generate_summary_report(self, output_path: Path):
        """
        Generate human-readable summary report

        Args:
            output_path: Path to output text file
        """
        logger.info(f"Generating summary report to {output_path}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("Document Classification Summary (12 Types)\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Total documents processed: {self.stats['total']}\n")
            f.write(f"Rule-only classifications: {self.stats['rule_only']}\n")
            f.write(f"LLM-only classifications: {self.stats['llm_only']}\n")
            f.write(f"Rule+LLM classifications: {self.stats['rule_llm']}\n")
            f.write(f"Unknown classifications: {self.stats['unknown']}\n\n")

            f.write("-" * 80 + "\n")
            f.write("Documents by Category:\n")
            f.write("-" * 80 + "\n")

            for doc_type, count in sorted(
                self.stats["by_category"].items(), key=lambda x: x[1], reverse=True
            ):
                display_name = get_doc_type_display_name(doc_type)
                percentage = (
                    (count / self.stats["total"] * 100)
                    if self.stats["total"] > 0
                    else 0
                )
                f.write(f"{display_name:30s} : {count:3d} ({percentage:5.1f}%)\n")

            f.write("\n")
            f.write("-" * 80 + "\n")
            f.write(f"Low Confidence Cases (< {self.confidence_threshold}):\n")
            f.write("-" * 80 + "\n")

            if self.stats["low_confidence"]:
                for doc_id, confidence, doc_type in self.stats["low_confidence"]:
                    display_name = get_doc_type_display_name(doc_type)
                    f.write(f"{doc_id:60s} : {display_name:25s} ({confidence:.2f})\n")
            else:
                f.write("None\n")

            f.write("\n")
            f.write("=" * 80 + "\n")

        logger.info("Summary report generated")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Classify documents into 12 types using rule-based + LLM approach"
    )
    parser.add_argument(
        "--doc-id-map",
        type=Path,
        default=Path("artifacts/ingestion/doc_id_map.json"),
        help="Path to doc_id_map.json (default: artifacts/ingestion/doc_id_map.json)",
    )
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=Path("artifacts/ingestion/markdown"),
        help="Path to markdown directory for first-page text (default: artifacts/ingestion/markdown)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/classification/document_types_12.jsonl"),
        help="Output JSONL file (default: artifacts/classification/document_types_12.jsonl)",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("artifacts/classification/classification_summary.txt"),
        help="Output summary report file (default: artifacts/classification/classification_summary.txt)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of documents to process (for testing)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.6,
        help="Minimum confidence threshold for LLM results (default: 0.6)",
    )
    parser.add_argument(
        "--llm-skip-threshold",
        type=float,
        default=0.85,
        help="Rule confidence threshold to skip LLM (default: 0.85)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't call LLM, only test rule-based classification",
    )

    args = parser.parse_args()

    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | {message}",
        level="INFO",
    )

    # Check if doc_id_map exists
    if not args.doc_id_map.exists():
        logger.error(f"doc_id_map not found: {args.doc_id_map}")
        sys.exit(1)

    # Initialize classifier
    classifier = DocumentClassifier12(
        doc_id_map_path=args.doc_id_map,
        markdown_dir=args.markdown_dir if args.markdown_dir.exists() else None,
        confidence_threshold=args.confidence_threshold,
        llm_skip_threshold=args.llm_skip_threshold,
        dry_run=args.dry_run,
    )

    # Classify all documents
    results = classifier.classify_all(limit=args.limit)

    # Save results
    classifier.save_results(results, args.output)

    # Generate summary report
    classifier.generate_summary_report(args.summary)

    logger.success(f"Classification complete! Results saved to {args.output}")
    logger.success(f"Summary report saved to {args.summary}")


if __name__ == "__main__":
    main()
