#!/usr/bin/env python3
"""
Filter and select best QA candidates from synthetic generation.
Prioritizes high confidence, diverse entities, balanced categories.
"""
import argparse
import json

# Add project root to path
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger


class QAFilter:
    """Filter QA candidates based on quality criteria."""

    def __init__(self):
        self.entity_coverage = defaultdict(int)  # Track entity usage
        self.category_counts = defaultdict(int)  # Track category balance
        self.selected_entities = set()  # Entities already covered

    def load_candidates(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load QA candidates from JSONL file."""
        candidates = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                candidates.append(json.loads(line))

        logger.info(f"Loaded {len(candidates)} QA candidates")
        return candidates

    def analyze_entity_coverage(
        self, candidates: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Analyze which entities are covered by questions."""
        entity_patterns = [
            r"[A-Z]{2,3}\d{5,6}",  # Equipment IDs like KT06101
            r"[A-Z]{2,3}-\d{3,5}",  # Tags like FT-101
            r"[A-Z]{1,3}V-?\d{3,5}",  # Valve tags like XV-101
            r"[PTFILQ][TIC]-?\d{3,5}",  # Instrument tags
        ]

        import re

        entity_usage = defaultdict(int)

        for qa in candidates:
            query = qa["query"]
            # Extract entities from query
            for pattern in entity_patterns:
                matches = re.findall(pattern, query)
                for match in matches:
                    entity_usage[match] += 1

        return dict(entity_usage)

    def score_candidate(
        self, qa: Dict[str, Any], entity_usage: Dict[str, int]
    ) -> float:
        """Score a QA candidate based on multiple criteria."""
        score = 0.0

        # Base confidence score (0-1)
        score += qa.get("confidence", 0.5) * 0.4

        # Category priority weights
        category_weights = {
            "lookup": 1.0,  # High priority - main RAG function
            "locate": 0.9,  # Important for P&ID
            "negative": 0.8,  # Important for testing
            "ambiguous": 0.7,  # Good edge cases
        }
        score += category_weights.get(qa["category"], 0.5) * 0.2

        # Type priority weights
        type_weights = {
            "factual": 1.0,
            "procedural": 0.8,
            "safety": 0.9,
            "troubleshooting": 0.7,
        }
        score += type_weights.get(qa["type"], 0.5) * 0.1

        # Difficulty balance (prefer medium, then easy, then hard)
        difficulty_weights = {"medium": 1.0, "easy": 0.8, "hard": 0.9}
        score += difficulty_weights.get(qa["difficulty"], 0.5) * 0.1

        # Language preference (slight preference for Vietnamese)
        if qa["language"] == "vi":
            score += 0.05

        # Entity coverage bonus
        query = qa["query"]
        has_specific_entity = any(
            entity in query
            for entity in entity_usage.keys()
            if entity_usage[entity] <= 3  # Prefer less common entities
        )
        if has_specific_entity:
            score += 0.15

        return score

    def ensure_category_balance(
        self, candidates: List[Dict[str, Any]], target_count: int
    ) -> List[Dict[str, Any]]:
        """Ensure balanced representation across categories."""
        # Target distribution
        target_distribution = {
            "lookup": 0.5,  # 50% lookup questions
            "locate": 0.25,  # 25% location questions
            "negative": 0.15,  # 15% negative cases
            "ambiguous": 0.10,  # 10% ambiguous cases
        }

        # Calculate target counts per category
        category_targets = {
            cat: int(target_count * ratio) for cat, ratio in target_distribution.items()
        }

        # Group candidates by category
        by_category = defaultdict(list)
        for qa in candidates:
            by_category[qa["category"]].append(qa)

        # Sort each category by score
        entity_usage = self.analyze_entity_coverage(candidates)
        for category in by_category:
            by_category[category].sort(
                key=lambda x: self.score_candidate(x, entity_usage), reverse=True
            )

        # Select balanced set
        selected = []
        for category, target in category_targets.items():
            available = by_category[category]
            selected.extend(available[:target])
            logger.info(f"Selected {min(len(available), target)} {category} questions")

        # Fill remaining slots with best remaining candidates
        remaining_slots = target_count - len(selected)
        if remaining_slots > 0:
            remaining = []
            for category, candidates_list in by_category.items():
                start_idx = category_targets[category]
                remaining.extend(candidates_list[start_idx:])

            # Sort remaining by score and take best
            remaining.sort(
                key=lambda x: self.score_candidate(x, entity_usage), reverse=True
            )
            selected.extend(remaining[:remaining_slots])
            logger.info(f"Added {remaining_slots} additional high-scoring questions")

        return selected[:target_count]

    def ensure_entity_diversity(
        self, candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Ensure good coverage of different entities."""
        import re

        # Extract entities from each candidate
        entity_patterns = [
            r"[A-Z]{2,3}\d{5,6}",  # Equipment IDs
            r"[A-Z]{2,3}-\d{3,5}",  # Tags
            r"[A-Z]{1,3}V-?\d{3,5}",  # Valve tags
            r"[PTFILQ][TIC]-?\d{3,5}",  # Instrument tags
        ]

        entities_covered = set()
        filtered_candidates = []

        for qa in candidates:
            query = qa["query"]
            qa_entities = set()

            for pattern in entity_patterns:
                matches = re.findall(pattern, query)
                qa_entities.update(matches)

            # Prioritize questions with new entities or no specific entities
            if not qa_entities or not qa_entities.issubset(entities_covered):
                filtered_candidates.append(qa)
                entities_covered.update(qa_entities)
            elif len(filtered_candidates) < len(candidates) * 0.8:  # Allow some overlap
                filtered_candidates.append(qa)

        logger.info(
            f"Ensured diversity: {len(entities_covered)} unique entities covered"
        )
        return filtered_candidates

    def add_expected_answers(
        self, candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Add expected answer hints for better evaluation."""
        for qa in candidates:
            category = qa["category"]
            query = qa["query"].lower()

            # Add answer expectations based on category and content
            if category == "negative":
                qa["expected_answer_snippet"] = "Không có thông tin"
                qa["expected_behavior"] = "should_not_answer"

            elif category == "ambiguous":
                qa["expected_answer_snippet"] = "Vui lòng làm rõ"
                qa["expected_behavior"] = "should_ask_clarification"

            elif "áp suất" in query or "pressure" in query:
                qa["expected_answer_snippet"] = "bar|psi|kPa|MPa"
                qa["expected_behavior"] = "should_provide_value_with_unit"

            elif "nhiệt độ" in query or "temperature" in query:
                qa["expected_answer_snippet"] = "°C|K|°F"
                qa["expected_behavior"] = "should_provide_value_with_unit"

            elif "vị trí" in query or "location" in query or "nằm ở đâu" in query:
                qa["expected_answer_snippet"] = "tọa độ|grid|section"
                qa["expected_behavior"] = "should_provide_location"

            elif "quy trình" in query or "procedure" in query:
                qa["expected_answer_snippet"] = "bước|step|procedure"
                qa["expected_behavior"] = "should_provide_steps"

            elif "an toàn" in query or "safety" in query:
                qa["expected_answer_snippet"] = "cảnh báo|warning|precaution"
                qa["expected_behavior"] = "should_provide_safety_info"

            else:
                qa["expected_behavior"] = "should_provide_specific_answer"

        return candidates


def main():
    parser = argparse.ArgumentParser(description="Filter QA candidates")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("artifacts/qa/synthetic_qa_candidates.jsonl"),
        help="Input JSONL file with QA candidates",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/qa/filtered_qa_set.jsonl"),
        help="Output JSONL file with filtered QA set",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=50,
        help="Target number of QA pairs to select",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.6, help="Minimum confidence threshold"
    )

    args = parser.parse_args()

    logger.info(f"Filtering QA candidates from {args.input}")

    # Load candidates
    filter_engine = QAFilter()
    candidates = filter_engine.load_candidates(args.input)

    # Apply confidence filter
    high_confidence = [
        qa for qa in candidates if qa.get("confidence", 0.0) >= args.min_confidence
    ]
    logger.info(f"After confidence filter: {len(high_confidence)} candidates")

    # Ensure entity diversity
    diverse_candidates = filter_engine.ensure_entity_diversity(high_confidence)
    logger.info(f"After diversity filter: {len(diverse_candidates)} candidates")

    # Ensure category balance
    balanced_candidates = filter_engine.ensure_category_balance(
        diverse_candidates, args.target_count
    )
    logger.info(f"After balance filter: {len(balanced_candidates)} candidates")

    # Add expected answers
    final_candidates = filter_engine.add_expected_answers(balanced_candidates)

    # Save filtered set
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for qa in final_candidates:
            f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    # Print final summary
    logger.info(f"\n🎯 FILTERED QA SET SUMMARY:")

    categories = defaultdict(int)
    types = defaultdict(int)
    languages = defaultdict(int)
    difficulties = defaultdict(int)

    for qa in final_candidates:
        categories[qa["category"]] += 1
        types[qa["type"]] += 1
        languages[qa["language"]] += 1
        difficulties[qa["difficulty"]] += 1

    print(f"\n📊 Final Distribution:")
    print(f"Categories: {dict(categories)}")
    print(f"Types: {dict(types)}")
    print(f"Languages: {dict(languages)}")
    print(f"Difficulties: {dict(difficulties)}")
    print(f"\n✅ Saved {len(final_candidates)} high-quality QA pairs to: {args.output}")


if __name__ == "__main__":
    main()
