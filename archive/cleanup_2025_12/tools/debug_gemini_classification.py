#!/usr/bin/env python
"""
Debug Gemini Classification
Test Gemini response for specific documents to understand empty responses
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.services.document_type_12_llm import DocumentType12LLM

# Configure logger for debug
logger.remove()
logger.add(sys.stderr, level="DEBUG")


def test_performance_curve_doc():
    """Test the Performance Curve document that failed"""

    doc_id = "DOCID_003_3N4-S4274345_Expected_Performance_Curve_of_Compressor_Rev.01_70b4ad0d"
    pdf_path = "D:\\Data_Raw\\003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"
    filename = "003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"

    # Load markdown if available
    markdown_path = Path(f"artifacts/ingestion/markdown/{doc_id}.md")
    first_page_text = None

    if markdown_path.exists():
        with open(markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
            first_page_text = content[:1500]
            logger.info(f"Loaded markdown: {len(first_page_text)} chars")

    # Initialize classifier
    classifier = DocumentType12LLM()

    # Test 1: Without first page text
    logger.info("\n" + "=" * 80)
    logger.info("Test 1: Classification WITHOUT first page text")
    logger.info("=" * 80)

    doc_type, confidence, reasoning = classifier.classify(
        filename=filename,
        file_path=pdf_path,
        first_page_text=None,
        confidence_threshold=0.6,
    )

    logger.success(f"Result: {doc_type.value} (confidence={confidence:.2f})")
    logger.info(f"Reasoning: {reasoning}")

    # Test 2: With first page text
    if first_page_text:
        logger.info("\n" + "=" * 80)
        logger.info("Test 2: Classification WITH first page text")
        logger.info("=" * 80)

        doc_type, confidence, reasoning = classifier.classify(
            filename=filename,
            file_path=pdf_path,
            first_page_text=first_page_text,
            confidence_threshold=0.6,
        )

        logger.success(f"Result: {doc_type.value} (confidence={confidence:.2f})")
        logger.info(f"Reasoning: {reasoning}")

    # Test 3: With cleaned first page text (remove special chars)
    if first_page_text:
        logger.info("\n" + "=" * 80)
        logger.info("Test 3: Classification WITH CLEANED first page text")
        logger.info("=" * 80)

        # Remove non-ASCII characters
        import re

        cleaned_text = re.sub(r"[^\x00-\x7F]+", " ", first_page_text)

        logger.info(f"Original text length: {len(first_page_text)}")
        logger.info(f"Cleaned text length: {len(cleaned_text)}")

        doc_type, confidence, reasoning = classifier.classify(
            filename=filename,
            file_path=pdf_path,
            first_page_text=cleaned_text,
            confidence_threshold=0.6,
        )

        logger.success(f"Result: {doc_type.value} (confidence={confidence:.2f})")
        logger.info(f"Reasoning: {reasoning}")


def test_direct_gemini_call():
    """Test direct Gemini API call to see detailed response"""
    from google import genai
    from google.genai import types

    from app.core.config import settings

    logger.info("\n" + "=" * 80)
    logger.info("Test 4: Direct Gemini API call with detailed response inspection")
    logger.info("=" * 80)

    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = """You are a technical document classifier.

Classify this document into ONE of these 12 categories:
1. P&ID
2. Management of Change
3. Root Cause Analysis
4. Technical Data
5. Maintenance History
6. Material Partlist
7. Datasheet
8. Operation Instruction
9. Maintenance Instruction
10. Other Technical Document
11. Inventory
12. Pictures

Document: "Expected Performance Curve of Compressor_Rev.01.pdf"

Response (JSON only):
{
    "doc_type": "category name",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}"""

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
    config = types.GenerateContentConfig(temperature=0.1, max_output_tokens=300)

    try:
        response = client.models.generate_content(
            model="models/gemini-2.5-flash", contents=contents, config=config
        )

        logger.info(f"Response type: {type(response)}")
        logger.info(
            f"Response attributes: {[a for a in dir(response) if not a.startswith('_')]}"
        )

        # Check candidates
        if hasattr(response, "candidates") and response.candidates:
            logger.info(f"Number of candidates: {len(response.candidates)}")
            for i, candidate in enumerate(response.candidates):
                logger.info(f"\nCandidate {i}:")
                logger.info(
                    f"  - Attributes: {[a for a in dir(candidate) if not a.startswith('_')]}"
                )

                # Check finish_reason
                if hasattr(candidate, "finish_reason"):
                    logger.info(f"  - Finish reason: {candidate.finish_reason}")

                # Check safety ratings
                if hasattr(candidate, "safety_ratings"):
                    logger.info(f"  - Safety ratings: {candidate.safety_ratings}")

                # Check content
                if hasattr(candidate, "content"):
                    logger.info(f"  - Has content: {candidate.content is not None}")
                    if candidate.content and hasattr(candidate.content, "parts"):
                        logger.info(
                            f"  - Number of parts: {len(candidate.content.parts)}"
                        )
                        for j, part in enumerate(candidate.content.parts):
                            if hasattr(part, "text"):
                                logger.info(
                                    f"    Part {j} text length: {len(part.text) if part.text else 0}"
                                )

        # Try to extract text
        if hasattr(response, "text") and response.text:
            logger.success(f"Successfully got text: {response.text[:200]}")
        else:
            logger.warning("No text in response")

    except Exception as e:
        logger.error(f"Direct API call failed: {e}", exc_info=True)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DEBUGGING GEMINI CLASSIFICATION FOR PERFORMANCE CURVE DOCUMENT")
    print("=" * 80 + "\n")

    try:
        test_performance_curve_doc()
        test_direct_gemini_call()
    except Exception as e:
        logger.error(f"Debug script failed: {e}", exc_info=True)

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80 + "\n")
