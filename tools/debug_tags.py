import os
import sys
from pathlib import Path

from loguru import logger

# Setup paths
PROJECT_ROOT = Path.cwd()
sys.path.append(str(PROJECT_ROOT))

# Set env vars BEFORE importing config
os.environ["ARTIFACTS_DIR"] = str(PROJECT_ROOT / "debug_output")
os.environ["ENTITIES_DIR"] = str(PROJECT_ROOT / "debug_output" / "entities")
os.environ["LAYOUT_DIR"] = str(PROJECT_ROOT / "debug_output" / "page_layout")
os.environ["CROPS_DIR"] = str(PROJECT_ROOT / "debug_output" / "crops")
os.environ["LOGS_DIR"] = str(PROJECT_ROOT / "debug_output" / "logs")
os.environ["ENABLE_PID_TAGS"] = "true"
os.environ["GATE_MODE"] = "always"  # Force enable to ensure it runs

from app.config.pipeline_config import get_config
from app.ingestion.tags.orchestrator import TagExtractionOrchestrator


def test_tag_extraction():
    logger.info("Starting Tag Extraction Test")

    # Initialize orchestrator
    orchestrator = TagExtractionOrchestrator(enable_crops=False)

    # Find the debug PDF
    debug_input = PROJECT_ROOT / "debug_input"
    pdf_files = list(debug_input.glob("*.pdf"))

    if not pdf_files:
        logger.error("No PDF found in debug_input")
        return

    pdf_path = pdf_files[0]
    doc_id = "TEST_DOC_001"

    logger.info(f"Processing {pdf_path}")

    # Run extraction
    result = orchestrator.process_document(pdf_path, doc_id)

    logger.info(f"Result: {result}")

    # Check output
    tags_file = Path(os.environ["ENTITIES_DIR"]) / "tags.jsonl"
    if tags_file.exists():
        logger.info(f"Tags file created at {tags_file}")
        with open(tags_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            logger.info(f"Found {len(lines)} tags")
            if lines:
                logger.info(f"Sample: {lines[0].strip()}")
    else:
        logger.error("Tags file NOT created")


if __name__ == "__main__":
    test_tag_extraction()
