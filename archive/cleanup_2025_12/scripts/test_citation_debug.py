"""
Test script to debug citation accuracy with detailed logging
Run this to see the full RAG pipeline logs including context, prompts, and citations
"""
import os
import sys
from pathlib import Path

# Set debug logging level BEFORE importing loguru-using modules
os.environ["LOGURU_LEVEL"] = "DEBUG"

from loguru import logger

# Configure logger to show DEBUG level with nice formatting
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="DEBUG",
    colorize=True,
)

from app.core.config import Settings
from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryTransformer
from app.rag.reranker import Reranker
from app.rag.retriever import HybridRetriever


def test_citation_accuracy():
    """Test citation accuracy for a specific query about Tag No. 06-TE-0256 A/B"""

    # The test query
    query = """I need to configure the alarm settings for the temperature monitoring system on the steam turbine. According to the instrument list, there is a sensor with Tag No. 06-TE-0256 A/B.
Based on the provided documentation, what is the measurement point (i.e., the component being monitored) for this tag number, and what is its corresponding high-temperature alarm (A) setpoint?"""

    # Expected answer for comparison
    expected_answer = """
Based on the documentation, the instrument with Tag No. 06-TE-0256 A/B has the following parameters:
Measurement Point: It monitors the temperature of the Rear Journal Bearing (后径向轴承).
High-Temperature Alarm Setpoint: The alarm (A) is set to trigger at 105 °C.
Source:
The measurement point "Rear Journal Bearing" is identified in the instrument list on page 4 of 6.
The high-temperature alarm setpoint of 105 °C for this specific tag is listed in the function table on page 6 of 6.
"""

    logger.info("=" * 80)
    logger.info("CITATION ACCURACY DEBUG TEST")
    logger.info("=" * 80)
    logger.info(f"Query: {query[:200]}...")
    logger.info("")
    logger.info("Expected Answer Summary:")
    logger.info("  - Measurement Point: Rear Journal Bearing (后径向轴承)")
    logger.info("  - High-Temperature Alarm Setpoint: 105 °C")
    logger.info(
        "  - Correct Sources: page 4 (measurement point) and page 6 (alarm setpoint)"
    )
    logger.info("=" * 80)
    logger.info("")

    # Initialize RAG components
    logger.info("Initializing RAG components with enhanced debug logging...")

    try:
        # Initialize settings
        settings = Settings()

        # Initialize components
        query_transformer = QueryTransformer(enable_hyde=True)
        retriever = HybridRetriever()
        reranker = Reranker()

        # Configure generator with calibrated confidence and citation validation
        generator_config = GeneratorConfig(
            llm_tier="heavy",
            language="en",
            confidence_mode="calibrated",
            enable_citation_validation=True,
            citation_validation_level=2,
            enable_vision_generation=True,  # Enable vision to test full pipeline
            enable_smart_vision_strategy=False,  # Disable smart strategy for consistent testing
        )
        generator = ResponseGenerator(config=generator_config)

        logger.info("Components initialized")
        logger.info("")

    except Exception as e:
        logger.error(f"Failed to initialize components: {e}", exc_info=True)
        return

    # Process query
    logger.info("=" * 80)
    logger.info("STARTING QUERY PROCESSING")
    logger.info("=" * 80)

    try:
        # Step 1: Transform query
        logger.info("Step 1: Query transformation...")
        transformed_query = query_transformer.transform(query=query, language="en")
        logger.info(f"Transformed query: {transformed_query.normalized[:100]}...")
        logger.info("")

        # Step 2: Retrieve documents
        logger.info("Step 2: Hybrid retrieval...")
        retrieved_docs = retriever.search(transformed_query)
        logger.info(f"Retrieved {len(retrieved_docs)} documents")
        logger.info("")

        # Step 3: Rerank
        logger.info("Step 3: Reranking...")
        reranked_docs = reranker.rerank(
            transformed_query.normalized, retrieved_docs, top_k=10
        )
        logger.info(f"Reranked to {len(reranked_docs)} documents")
        logger.info("")

        # Step 4: Generate answer
        logger.info("Step 4: Answer generation (with debug logs)...")
        logger.info("")
        result = generator.generate(
            query=transformed_query,
            retrieved_docs=reranked_docs[:10],  # Top 10
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("QUERY PROCESSING COMPLETE")
        logger.info("=" * 80)
        logger.info("")

        # Display results
        logger.info("GENERATED ANSWER:")
        logger.info("-" * 80)
        logger.info(result.answer)
        logger.info("-" * 80)
        logger.info("")

        logger.info("CITATIONS RETURNED:")
        logger.info("-" * 80)
        citations = result.citations
        if citations:
            for i, cit in enumerate(citations, 1):
                logger.info(f"[{i}] doc_id: {cit.doc_id}")
                logger.info(f"    page: {cit.page}")
                logger.info(f"    source: {cit.source}")
                logger.info(f"    pdf_path: {cit.pdf_path or 'N/A'}")
                logger.info(f"    snippet: {cit.text_snippet[:100]}...")
                logger.info("")
        else:
            logger.warning("No citations found!")
        logger.info("-" * 80)
        logger.info("")

        # Check confidence
        confidence = result.confidence
        logger.info(f"Confidence Score: {confidence:.2f}")

        # Check metadata
        metadata = result.metadata
        if "doc_number_map" in metadata:
            logger.info("")
            logger.info("DOC_NUMBER_MAP (for UI page buttons):")
            logger.info("-" * 80)
            doc_map = metadata["doc_number_map"]
            for doc_num in sorted(doc_map.keys()):
                info = doc_map[doc_num]
                logger.info(f"Doc {doc_num}:")
                logger.info(f"  doc_id: {info.get('doc_id')}")
                logger.info(f"  file_name: {info.get('file_name')}")
                logger.info(
                    f"  pdf_path: {'present' if info.get('pdf_path') else 'MISSING'}"
                )
            logger.info("-" * 80)

        logger.info("")
        logger.info("=" * 80)
        logger.info("ANALYSIS INSTRUCTIONS")
        logger.info("=" * 80)
        logger.info("Please review the logs above to answer:")
        logger.info(
            "1. What context was sent to the LLM? (Check 'Prepared LLM context' logs)"
        )
        logger.info(
            "2. Which documents were mapped to [Doc 1], [Doc 2], etc.? (Check 'Doc mapping summary')"
        )
        logger.info("3. What did the LLM output? (Check 'Answer preview' logs)")
        logger.info("4. What citations were parsed? (Check 'Parsed citations' logs)")
        logger.info("5. Do the parsed citations match the doc_number_map correctly?")
        logger.info("")
        logger.info("Key Questions:")
        logger.info(
            "- Did the retrieval system fetch the correct documents (with pages 4 and 6)?"
        )
        logger.info("- Were those documents ranked high enough to be in the context?")
        logger.info("- Did the LLM cite the correct [Doc X] numbers in its answer?")
        logger.info(
            "- Were those [Doc X] references correctly resolved to doc_id + page + pdf_path?"
        )
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        return


if __name__ == "__main__":
    logger.info("Starting citation accuracy debug test...")
    logger.info("")

    # Run sync function
    test_citation_accuracy()

    logger.info("")
    logger.info("Test complete. Please review the logs above.")
