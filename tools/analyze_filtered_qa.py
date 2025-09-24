#!/usr/bin/env python3
"""
Analyze the filtered QA set to show detailed statistics and insights.
"""
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path


def main():
    # Load filtered QA data
    qa_file = Path("artifacts/qa/filtered_qa_set.jsonl")
    with open(qa_file, "r", encoding="utf-8") as f:
        qa_data = [json.loads(line) for line in f]

    print(f"=== PHÂN TÍCH BỘ QA CHẤT LƯỢNG CAO ({len(qa_data)} câu hỏi) ===\n")

    # Collect statistics
    categories = defaultdict(int)
    types = defaultdict(int)
    languages = defaultdict(int)
    difficulties = defaultdict(int)
    behaviors = defaultdict(int)
    entities_found = set()

    for qa in qa_data:
        categories[qa["category"]] += 1
        types[qa["type"]] += 1
        languages[qa["language"]] += 1
        difficulties[qa["difficulty"]] += 1
        behaviors[qa["expected_behavior"]] += 1

        # Find entities in questions
        patterns = [
            r"[A-Z]{2,3}\d{5,6}",  # Equipment IDs like KT06101
            r"[A-Z]{2,3}-\d{3,5}",  # Tags like FT-101
            r"[A-Z]{1,3}V-?\d{3,5}",  # Valve tags like XV-101
            r"[PTFILQ][TIC]-?\d{3,5}",  # Instrument tags
        ]
        for pattern in patterns:
            matches = re.findall(pattern, qa["query"])
            entities_found.update(matches)

    # Print category distribution with examples
    print("📊 PHÂN PHỐI THEO CATEGORY:")
    for cat, count in sorted(categories.items()):
        examples = [qa for qa in qa_data if qa["category"] == cat][:2]
        print(f"  {cat.upper():11} : {count:2d} ({count/len(qa_data)*100:.1f}%)")
        for ex in examples:
            query = ex["query"]
            display_query = query[:55] + "..." if len(query) > 55 else query
            print(f"    - {display_query}")
        print()

    # Print expected behaviors
    print("🎯 EXPECTED BEHAVIORS:")
    for behavior, count in sorted(behaviors.items()):
        print(f"  {behavior:30} : {count:2d}")

    # Print unique entities covered
    print(f"\n🔧 UNIQUE ENTITIES COVERED: {len(entities_found)}")
    entity_list = sorted(list(entities_found))
    for i in range(0, len(entity_list), 8):
        chunk = entity_list[i : i + 8]
        print("  " + "  ".join(f"{entity:8}" for entity in chunk))

    # Confidence score distribution
    confidence_scores = [qa.get("confidence", 0.0) for qa in qa_data]
    print(f"\n📈 CONFIDENCE SCORE DISTRIBUTION:")
    print(f"  Average: {statistics.mean(confidence_scores):.2f}")
    print(f"  Min: {min(confidence_scores):.2f}")
    print(f"  Max: {max(confidence_scores):.2f}")

    # High-value question analysis
    print(f"\n🌟 HIGH-VALUE QUESTIONS (by expected behaviors):")

    unit_questions = [
        qa for qa in qa_data if "value_with_unit" in qa.get("expected_behavior", "")
    ]
    location_questions = [
        qa for qa in qa_data if "location" in qa.get("expected_behavior", "")
    ]
    procedural_questions = [
        qa for qa in qa_data if "steps" in qa.get("expected_behavior", "")
    ]
    negative_questions = [
        qa for qa in qa_data if "should_not_answer" == qa.get("expected_behavior", "")
    ]
    clarification_questions = [
        qa for qa in qa_data if "clarification" in qa.get("expected_behavior", "")
    ]

    print(f"  - Questions with unit values: {len(unit_questions)}")
    print(f"  - Location questions: {len(location_questions)}")
    print(f"  - Procedural questions: {len(procedural_questions)}")
    print(f"  - Negative test cases: {len(negative_questions)}")
    print(f"  - Clarification requests: {len(clarification_questions)}")

    # Document hints analysis
    print(f"\n📚 DOCUMENT HINTS ANALYSIS:")
    doc_hints_count = defaultdict(int)
    for qa in qa_data:
        for hint in qa.get("doc_hints", []):
            doc_hints_count[hint] += 1

    for doc_type, count in sorted(doc_hints_count.items()):
        print(f"  {doc_type:10} : {count:2d} questions expect this doc type")

    # Sample questions by category
    print(f"\n🔍 SAMPLE QUESTIONS BY CATEGORY:")

    sample_categories = ["lookup", "locate", "negative", "ambiguous"]
    for cat in sample_categories:
        cat_questions = [qa for qa in qa_data if qa["category"] == cat]
        print(f"\n  {cat.upper()} ({len(cat_questions)} questions):")

        for i, qa in enumerate(cat_questions[:3]):  # Show first 3
            query = qa["query"]
            behavior = qa.get("expected_behavior", "N/A")
            confidence = qa.get("confidence", 0.0)

            print(f"    {i+1}. {query}")
            print(f"       → Behavior: {behavior} (conf: {confidence:.1f})")


if __name__ == "__main__":
    main()
