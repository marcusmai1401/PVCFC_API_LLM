"""
Re-classify a single document that failed during batch classification
Includes retry logic to handle rate limit errors
"""
import json
import sys
import time
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.classification.document_type_12 import DocumentType12, DocumentType12Result
from app.services.document_type_12_llm import DocumentType12LLM
from tools.extract_metadata import (
    extract_doc_type,
    extract_equipment_id,
    extract_equipment_type,
    extract_vendor,
)


def reclassify_single_document(
    doc_id: str,
    max_retries: int = 3,
    retry_delay: int = 60,
):
    """
    Re-classify a single document with retry logic

    Args:
        doc_id: Document ID to classify
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds to wait between retries
    """
    # Load doc_id_map
    doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    if doc_id not in doc_id_map:
        logger.error(f"Document ID not found: {doc_id}")
        return None

    pdf_path = doc_id_map[doc_id]
    logger.info(f"Re-classifying: {doc_id}")
    logger.info(f"PDF path: {pdf_path}")

    # Load markdown text
    markdown_dir = Path("artifacts/ingestion/markdown")
    md_file = markdown_dir / f"{doc_id}.md"

    first_page_text = None
    if md_file.exists():
        with open(md_file, "r", encoding="utf-8") as f:
            first_page_text = f.read()
        logger.info(f"Loaded markdown text: {len(first_page_text)} chars")
    else:
        logger.warning(f"No markdown file found for {doc_id}")

    # Extract metadata
    path_metadata = {
        "equipment_type": extract_equipment_type(pdf_path),
        "doc_type": extract_doc_type(pdf_path),
        "equipment_id": extract_equipment_id(pdf_path),
        "vendor": extract_vendor(pdf_path),
    }
    logger.info(f"Path metadata: {path_metadata}")

    # Initialize LLM classifier
    llm_classifier = DocumentType12LLM()

    # Retry loop
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries}...")

            # Classify with LLM
            doc_type_12, confidence, reasoning = llm_classifier.classify(
                filename=Path(pdf_path).name,
                file_path=pdf_path,
                first_page_text=first_page_text,
                path_metadata=path_metadata,
                confidence_threshold=0.6,
            )

            # Create result
            result = DocumentType12Result(
                doc_id=doc_id,
                pdf_path=pdf_path,
                doc_type_12=doc_type_12.value,
                parent_category="",  # Auto-derived
                confidence=confidence,
                method="llm_only",
                raw_llm_doc_type=doc_type_12.value,
                reasoning=reasoning,
            )

            logger.success(f"✅ Classification successful!")
            logger.info(f"   Type: {doc_type_12.value}")
            logger.info(f"   Parent: {result.parent_category}")
            logger.info(f"   Sub: {result.sub_category}")
            logger.info(f"   Confidence: {confidence:.2%}")
            logger.info(f"   Reasoning: {reasoning}")

            # Update manifest
            update_manifest(result)

            return result

        except Exception as e:
            error_msg = str(e)

            # Check if it's a rate limit error
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Rate limit hit. Waiting {retry_delay} seconds before retry..."
                    )
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"❌ Max retries reached. Classification failed.")
                    return None
            else:
                # Other error - don't retry
                logger.error(f"❌ Classification failed: {e}", exc_info=True)
                return None

    return None


def update_manifest(result: DocumentType12Result):
    """Update the classification manifest with new result"""
    manifest_path = Path("artifacts/classification/document_types_12.jsonl")

    # Read all results
    results = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    # Find and update the result
    found = False
    for i, existing in enumerate(results):
        if existing["doc_id"] == result.doc_id:
            results[i] = result.to_dict()
            found = True
            logger.info(f"Updated existing entry in manifest")
            break

    if not found:
        logger.warning(f"Document not found in manifest, appending...")
        results.append(result.to_dict())

    # Write back
    with open(manifest_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    logger.success(f"✅ Manifest updated: {manifest_path}")


if __name__ == "__main__":
    import sys

    # Get doc_id from command line or use default failed doc
    if len(sys.argv) > 1:
        doc_id = sys.argv[1]
    else:
        # Default: the failed doc from classification
        doc_id = "DOCID_K06101_CO2_COMPRESSOR_HITACHI_K06101_CO2_COMPRESSOR_HITACHI_Manual_MANUAL_COMPRE_88d35c5c"

    logger.info("=" * 80)
    logger.info("Re-classify Single Document")
    logger.info("=" * 80)

    result = reclassify_single_document(
        doc_id=doc_id,
        max_retries=3,
        retry_delay=60,  # Wait 60 seconds between retries
    )

    if result:
        logger.success("✅ Re-classification complete!")
    else:
        logger.error("❌ Re-classification failed!")
        sys.exit(1)
