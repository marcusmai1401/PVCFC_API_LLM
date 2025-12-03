#!/usr/bin/env python3
"""
Create golden QA v1 by normalizing filtered QA set according to review feedback.
Adds doc_category field, standardizes classification fields, ensures proper distribution.
"""
import argparse
import json

# Add project root to path
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger


class GoldenQACreator:
    """Create standardized golden QA set."""

    def __init__(self):
        self.doc_category_priority = {
            "datasheet": 1,  # Highest priority
            "om": 2,
            "sop": 3,
            "pid": 4,  # Lowest priority
        }

    def load_filtered_qa(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load filtered QA set."""
        qa_list = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                qa_list.append(json.loads(line))

        logger.info(f"Loaded {len(qa_list)} QA pairs from filtered set")
        return qa_list

    def add_doc_category(self, qa: Dict[str, Any]) -> Dict[str, Any]:
        """Add doc_category field based on doc_hints with priority."""
        doc_hints = qa.get("doc_hints", [])

        if not doc_hints:
            # Empty doc_hints (negative cases)
            qa["doc_category"] = None
        else:
            # Select highest priority doc_hint
            prioritized_hints = []
            for hint in doc_hints:
                priority = self.doc_category_priority.get(hint, 999)
                prioritized_hints.append((priority, hint))

            # Sort by priority (lower number = higher priority)
            prioritized_hints.sort()
            qa["doc_category"] = prioritized_hints[0][1]

        return qa

    def standardize_classification(self, qa: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize classification fields: intent, doc_category, type."""
        # Rename 'category' to 'intent' for clarity
        qa["intent"] = qa.pop("category", "lookup")

        # Ensure type field exists (factual|procedural|safety|troubleshooting)
        if "type" not in qa:
            qa["type"] = "factual"

        # doc_category already added by add_doc_category()

        return qa

    def ensure_id_uniqueness(
        self, qa_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Ensure all IDs are unique and normalized to start with 'G'. Uses 4-digit numbering GQ0001."""
        seen_ids = set()
        id_counter = 1
        for qa in qa_list:
            original_id = str(qa.get("id", "")).strip()
            # Normalize first (prefix 'G' if missing)
            normalized_id = (
                original_id
                if (original_id and original_id.startswith("G"))
                else (f"G{original_id}" if original_id else "")
            )
            # If empty or duplicate after normalization, generate new
            if not normalized_id or normalized_id in seen_ids:
                new_id = f"GQ{id_counter:04d}"
                while new_id in seen_ids:
                    id_counter += 1
                    new_id = f"GQ{id_counter:04d}"
                qa["id"] = new_id
            else:
                qa["id"] = normalized_id
            seen_ids.add(qa["id"])
            id_counter += 1
        return qa_list

    def check_distribution(self, qa_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check if distribution meets minimum requirements."""
        distribution = {
            "intent": defaultdict(int),
            "doc_category": defaultdict(int),
            "type": defaultdict(int),
            "language": defaultdict(int),
            "difficulty": defaultdict(int),
        }

        for qa in qa_list:
            distribution["intent"][qa.get("intent", "unknown")] += 1
            distribution["doc_category"][qa.get("doc_category", "none")] += 1
            distribution["type"][qa.get("type", "unknown")] += 1
            distribution["language"][qa.get("language", "unknown")] += 1
            distribution["difficulty"][qa.get("difficulty", "unknown")] += 1

        # Check minimum requirements
        requirements = {"locate": 12, "lookup": 20, "negative": 12, "ambiguous": 8}

        issues = []
        for intent, min_count in requirements.items():
            actual = distribution["intent"][intent]
            if actual < min_count:
                issues.append(f"{intent}: {actual} < {min_count} (minimum)")

        # Check procedural count
        procedural_count = distribution["type"]["procedural"]
        if procedural_count < 8:
            issues.append(f"procedural: {procedural_count} < 8 (minimum)")

        return dict(distribution), issues

    def add_metadata(self, qa_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add metadata for better tracking."""
        for qa in qa_list:
            qa["metadata"] = {
                "version": "v1",
                "created_from": "synthetic_generation",
                "review_status": "pending",
                "priority": self._calculate_priority(qa),
            }

        return qa_list

    def _calculate_priority(self, qa: Dict[str, Any]) -> str:
        """Calculate priority based on intent and confidence."""
        intent = qa.get("intent", "lookup")
        confidence = qa.get("confidence", 0.5)

        if intent == "negative":
            return "high"  # Important for testing false positives
        elif intent == "ambiguous":
            return "high"  # Important for edge case handling
        elif confidence >= 0.9:
            return "high"  # High confidence questions
        elif confidence >= 0.8:
            return "medium"
        else:
            return "low"

    def reorder_fields(self, qa: Dict[str, Any]) -> Dict[str, Any]:
        """Reorder fields for better readability."""
        field_order = [
            "id",
            "query",
            "intent",
            "doc_category",
            "type",
            "difficulty",
            "language",
            "confidence",
            "doc_hints",
            "expected_behavior",
            "expected_answer_snippet",
            "expected_citations",
            "metadata",
        ]

        ordered_qa = {}
        for field in field_order:
            if field in qa:
                ordered_qa[field] = qa[field]

        # Add any remaining fields not in the order
        for key, value in qa.items():
            if key not in ordered_qa:
                ordered_qa[key] = value

        return ordered_qa


def main():
    parser = argparse.ArgumentParser(description="Create Golden QA v1")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("artifacts/qa/filtered_qa_set.jsonl"),
        help="Input filtered QA set",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/qa/golden_pseudo_v1.jsonl"),
        help="Output golden QA v1",
    )

    args = parser.parse_args()

    logger.info(f"Creating Golden QA v1 from {args.input}")

    creator = GoldenQACreator()

    # Load filtered QA
    qa_list = creator.load_filtered_qa(args.input)

    # Apply transformations
    logger.info("Applying transformations...")

    processed_qa = []
    for qa in qa_list:
        # Add doc_category field
        qa = creator.add_doc_category(qa)

        # Standardize classification fields
        qa = creator.standardize_classification(qa)

        # Reorder fields for consistency
        qa = creator.reorder_fields(qa)

        processed_qa.append(qa)

    # Ensure ID uniqueness
    processed_qa = creator.ensure_id_uniqueness(processed_qa)

    # Add metadata
    processed_qa = creator.add_metadata(processed_qa)

    # Check distribution
    distribution, issues = creator.check_distribution(processed_qa)

    # Log distribution analysis
    logger.info("\n🔍 DISTRIBUTION ANALYSIS:")
    for category, counts in distribution.items():
        logger.info(f"  {category.upper()}:")
        # Handle None values in sorting
        sorted_items = sorted(counts.items(), key=lambda x: (x[0] is None, x[0]))
        for key, count in sorted_items:
            display_key = str(key) if key is not None else "none"
            logger.info(f"    {display_key}: {count}")

    if issues:
        logger.warning("\n⚠️  DISTRIBUTION ISSUES:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    else:
        logger.success("\n✅ Distribution meets all requirements!")

    # Save golden QA v1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for qa in processed_qa:
            f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    logger.success(f"\n🎯 Created Golden QA v1: {args.output}")
    logger.info(f"   Total QA pairs: {len(processed_qa)}")
    logger.info(f"   Ready for evaluation pipeline!")


if __name__ == "__main__":
    main()
