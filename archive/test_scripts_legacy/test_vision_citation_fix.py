"""
Test script to verify vision citations are correctly mapped to actual PDF pages shown
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.deps.indices import get_index_manager
from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import HybridRetriever


def test_vision_citations():
    """Test that vision citations point to correct pages"""

    # Initialize components
    print("Initializing retriever and generator...")
    index_mgr = get_index_manager()
    retriever = HybridRetriever(
        bm25_index=index_mgr.bm25_index, faiss_index=index_mgr.faiss_index
    )

    config = GeneratorConfig(
        llm_tier="heavy", language="en", enable_vision_generation=True
    )
    generator = ResponseGenerator(config=config)

    # Test query about torque table
    query = TransformedQuery(
        original="During the installation procedure for the condensing turbine, after the back grouting has been finished for at least 72 hours, according to Table: Tightened torque for anchor bolt, what is the specified final tightening torque for an M42 anchor bolt?",
        normalized="during installation procedure for condensing turbine, after back grouting finished at least 72 hours, according table tightened torque for anchor bolt, what is specified final tightening torque for m42 anchor bolt",
        intent=QueryIntent.ASK,
        language="en",
    )

    print("\nSearching for documents...")
    results = retriever.search(query, k_bm25=50, k_faiss=50)
    print(f"Found {len(results)} results")

    # Take top 20 for generation
    top_results = results[:20]

    print("\nGenerating answer with vision...")
    answer = generator.generate(query, top_results)

    print("\n" + "=" * 80)
    print("ANSWER:")
    print("=" * 80)
    print(answer.answer)

    print("\n" + "=" * 80)
    print("CITATIONS:")
    print("=" * 80)
    for i, citation in enumerate(answer.citations, 1):
        print(f"\n[{i}] Doc ID: {citation.doc_id}")
        print(f"    Source: {citation.source}")
        print(f"    Page: {citation.page}")
        if hasattr(citation, "pdf_path") and citation.pdf_path:
            # Extract filename from path
            filename = os.path.basename(citation.pdf_path)
            print(f"    PDF: {filename}")
        print(f"    Snippet: {citation.text_snippet[:100]}...")

    # Check if citation points to the correct document
    print("\n" + "=" * 80)
    print("VALIDATION:")
    print("=" * 80)

    correct_file = "KT06101_Installation instruction.pdf"
    correct_page = 15  # Based on your description

    found_correct = False
    for citation in answer.citations:
        if hasattr(citation, "pdf_path") and citation.pdf_path:
            filename = os.path.basename(citation.pdf_path)
            if correct_file in filename and citation.page == correct_page:
                found_correct = True
                print(f"✓ Found correct citation: {filename}, page {citation.page}")
                break

    if not found_correct:
        print(f"✗ Expected citation to {correct_file} page {correct_page} not found!")
        print("This may still be correct if the table is on a different page.")

    # Check vision metadata
    if answer.metadata and "vision_generation" in answer.metadata:
        vision_meta = answer.metadata["vision_generation"]
        print(f"\nVision pages used: {len(vision_meta.get('pages_used', []))}")
        for page_info in vision_meta.get("pages_used", [])[:5]:
            filename = os.path.basename(page_info.get("pdf_path", ""))
            page_num = page_info.get("page", "?")
            print(f"  - {filename}, page {page_num}")


if __name__ == "__main__":
    try:
        test_vision_citations()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
