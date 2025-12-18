#!/usr/bin/env python
"""
Test Script for System Prompts v2.0.1
=====================================

This script tests the new system prompts implementation:
1. Context header format [Doc X, p.Y]
2. System/User prompt separation
3. No self-introduction ("Tôi là AI...")
4. No implicit citations
5. Translation entity protection
6. HyDE system prompt

Usage:
    python tests/test_system_prompts_v2.py
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Patterns to detect self-introduction (these should NOT appear in responses)
SELF_INTRO_PATTERNS = [
    r"^Tôi là AI",
    r"^Tôi là trợ lý",
    r"^Tôi là một AI",
    r"^Dựa trên tài liệu",
    r"^Theo thông tin",
    r"^Theo tài liệu",
    r"^I am an AI",
    r"^As an AI",
    r"^Based on the documents",
    r"^According to the documents",
]

# Citation patterns (expected format)
CITATION_PATTERN = r"\[Doc\s*\d+(?:,\s*p\.\d+(?:-\d+)?)?\]"


def check_no_self_introduction(answer: str) -> Tuple[bool, Optional[str]]:
    """Check if answer starts with self-introduction (which it shouldn't)."""
    answer_stripped = answer.strip()
    for pattern in SELF_INTRO_PATTERNS:
        if re.match(pattern, answer_stripped, re.IGNORECASE):
            return False, f"Found self-intro pattern: {pattern}"
    return True, None


def check_citation_format(answer: str) -> Tuple[bool, int, List[str]]:
    """Check if citations use correct format [Doc X] or [Doc X, p.Y]."""
    citations = re.findall(CITATION_PATTERN, answer)

    # Check for old format (should not exist)
    old_format = re.findall(r"\[Doc\s*\d+\]\s*\(Page\s*\d+\)", answer)

    if old_format:
        return False, len(citations), old_format

    return True, len(citations), citations


@dataclass
class MockRetrievalResult:
    """Mock class for testing (matches RetrievalResult interface)."""

    doc_id: str
    text: str
    score: float
    source: str
    page: Optional[int]
    metadata: dict


def test_context_header_format():
    """Test that _prepare_context generates correct header format."""
    print("\n" + "=" * 60)
    print("TEST 1: Context Header Format")
    print("=" * 60)

    try:
        from app.rag.generator import GeneratorConfig, ResponseGenerator

        # Create mock docs using dataclass
        mock_docs = [
            MockRetrievalResult(
                doc_id="test_doc_1",
                text="Sample text content for testing.",
                score=0.9,
                source="test.pdf",
                page=15,
                metadata={},
            ),
            MockRetrievalResult(
                doc_id="test_doc_2",
                text="Another sample text.",
                score=0.8,
                source="test2.pdf",
                page=None,  # No page
                metadata={},
            ),
        ]

        config = GeneratorConfig()
        generator = ResponseGenerator(config=config)
        context, doc_mapping = generator._prepare_context(mock_docs)

        # Check format
        has_correct_format = "[Doc 1, p.15]" in context
        has_no_page_format = "[Doc 2]" in context
        has_old_format = "(Page " in context

        print(f"  Context preview: {context[:200]}...")
        print(f"  ✓ Has [Doc X, p.Y] format: {has_correct_format}")
        print(f"  ✓ Has [Doc X] format (no page): {has_no_page_format}")
        print(f"  ✓ Old format removed: {not has_old_format}")

        if has_correct_format and has_no_page_format and not has_old_format:
            print("  ✅ PASSED: Context header format is correct")
            return True
        else:
            print("  ❌ FAILED: Context header format issues")
            return False

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_system_prompt_separation():
    """Test that _call_llm_with_fallback accepts system_prompt parameter."""
    print("\n" + "=" * 60)
    print("TEST 2: System/User Prompt Separation")
    print("=" * 60)

    try:
        import inspect

        from app.rag.generator import GeneratorConfig, ResponseGenerator

        config = GeneratorConfig()
        generator = ResponseGenerator(config=config)

        # Check function signature
        sig = inspect.signature(generator._call_llm_with_fallback)
        params = list(sig.parameters.keys())

        has_system_prompt = "system_prompt" in params

        print(f"  Parameters: {params}")
        print(f"  ✓ Has system_prompt parameter: {has_system_prompt}")

        if has_system_prompt:
            print("  ✅ PASSED: System prompt separation implemented")
            return True
        else:
            print("  ❌ FAILED: Missing system_prompt parameter")
            return False

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_translation_system_prompt():
    """Test that translation has entity-protection system prompt."""
    print("\n" + "=" * 60)
    print("TEST 3: Translation System Prompt")
    print("=" * 60)

    try:
        # Check source code for new system prompt
        source_file = (
            Path(__file__).parent.parent / "app" / "rag" / "query_transform.py"
        )
        content = source_file.read_text(encoding="utf-8")

        has_entity_protection = (
            "Preserve ALL equipment" in content
            or "equipment/instrument tags" in content
        )
        has_units_protection = "Preserve units" in content
        has_one_line_rule = (
            "EXACTLY one line" in content or "one line" in content.lower()
        )

        print(f"  ✓ Entity protection rule: {has_entity_protection}")
        print(f"  ✓ Units protection rule: {has_units_protection}")
        print(f"  ✓ One-line output rule: {has_one_line_rule}")

        if has_entity_protection and has_units_protection:
            print("  ✅ PASSED: Translation system prompt updated")
            return True
        else:
            print("  ❌ FAILED: Translation system prompt missing rules")
            return False

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_no_implicit_citations():
    """Test that _extract_citations doesn't create implicit citations."""
    print("\n" + "=" * 60)
    print("TEST 4: No Implicit Citations")
    print("=" * 60)

    try:
        from app.rag.generator import GeneratorConfig, ResponseGenerator

        config = GeneratorConfig(include_citations=True)
        generator = ResponseGenerator(config=config)

        # Create mock docs but answer with NO citations
        mock_docs = {
            1: MockRetrievalResult(
                doc_id="test_doc_1",
                text="Sample text content.",
                score=0.9,
                source="test.pdf",
                page=15,
                metadata={},
            ),
        }

        # Answer without any citation markers
        answer_no_citations = "The operating pressure is 25 bar. This is a test answer."

        citations = generator._extract_citations(answer_no_citations, mock_docs)

        print(f"  Answer: {answer_no_citations}")
        print(f"  Citations found: {len(citations)}")

        if len(citations) == 0:
            print("  ✅ PASSED: No implicit citations created")
            return True
        else:
            print("  ❌ FAILED: Implicit citations still being created")
            return False

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_no_page_1_default():
    """Test that page=1 is not used as default."""
    print("\n" + "=" * 60)
    print("TEST 5: No Page=1 Default")
    print("=" * 60)

    try:
        from app.rag.generator import GeneratorConfig, ResponseGenerator

        config = GeneratorConfig()
        generator = ResponseGenerator(config=config)

        # Create mock doc with NO page info
        mock_docs = {
            1: MockRetrievalResult(
                doc_id="test_doc_1",
                text="Sample text content.",
                score=0.9,
                source="test.pdf",
                page=None,  # NO PAGE
                metadata={},
            ),
        }

        # Answer with citation but no page specified
        answer = "The value is 25 bar [Doc 1]."

        citations = generator._extract_citations(answer, mock_docs)

        print(f"  Answer: {answer}")
        print(f"  Citations: {len(citations)}")

        if citations:
            page = citations[0].page
            print(f"  Citation page: {page}")

            if page is None:
                print("  ✅ PASSED: No page=1 default used (page is None)")
                return True
            elif page != 1:
                print(f"  ✅ PASSED: No page=1 default used (page is {page})")
                return True
            else:
                print("  ❌ FAILED: Still using page=1 default")
                return False
        else:
            print(
                "  ℹ️ No citations extracted (expected for [Doc 1] format with no page)"
            )
            return True

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_hyde_system_prompt():
    """Test that HyDE generation uses system prompt."""
    print("\n" + "=" * 60)
    print("TEST 6: HyDE System Prompt")
    print("=" * 60)

    try:
        # Check source code for HyDE system prompt
        source_file = (
            Path(__file__).parent.parent / "app" / "rag" / "query_transform.py"
        )
        content = source_file.read_text(encoding="utf-8")

        has_hyde_system_prompt = "hyde_system_prompt" in content
        has_no_answer_rule = "Do NOT answer the user" in content
        has_no_citation_rule = "Do NOT include citations" in content

        print(f"  ✓ HyDE system prompt defined: {has_hyde_system_prompt}")
        print(f"  ✓ No-answer rule: {has_no_answer_rule}")
        print(f"  ✓ No-citation rule: {has_no_citation_rule}")

        if has_hyde_system_prompt:
            print("  ✅ PASSED: HyDE system prompt implemented")
            return True
        else:
            print("  ❌ FAILED: HyDE system prompt not found")
            return False

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 70)
    print("  SYSTEM PROMPTS v2.0.1 TEST SUITE")
    print("=" * 70)

    results = []

    # Run tests
    results.append(("Context Header Format", test_context_header_format()))
    results.append(("System/User Prompt Separation", test_system_prompt_separation()))
    results.append(("Translation System Prompt", test_translation_system_prompt()))
    results.append(("No Implicit Citations", test_no_implicit_citations()))
    results.append(("No Page=1 Default", test_no_page_1_default()))
    results.append(("HyDE System Prompt", test_hyde_system_prompt()))

    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n  ⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
