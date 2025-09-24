#!/usr/bin/env python
"""Test text chunker module"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger

from app.ingestion.text_chunker import TextChunker


def test_chunker():
    logger.info("Testing Text Chunker")
    chunker = TextChunker(chunk_size=500, chunk_overlap=100)

    sample_text = (
        """
    This is a sample text for testing the chunker. It contains multiple sentences
    and paragraphs to test the semantic chunking strategy.

    This is the second paragraph with more content. The chunker should handle
    paragraph boundaries properly and create overlapping chunks when configured.
    """
        * 5
    )  # Make it longer

    chunks = chunker.chunk_text(sample_text, doc_id="test_doc")
    logger.info(f"✅ Created {len(chunks)} chunks from {len(sample_text)} chars")

    if chunks:
        logger.info(f"   First chunk: {chunks[0].text[:50]}...")

    return True


if __name__ == "__main__":
    test_chunker()
