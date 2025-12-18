import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(os.getcwd())
sys.path.insert(0, str(project_root))

from app.rag.indexers.opensearch_bm25_retriever import create_opensearch_retriever
from app.services.deep_search import DeepSearchService


def test_search():
    print("Initializing OpenSearch client...")
    retriever = create_opensearch_retriever()
    client = retriever.client

    service = DeepSearchService(opensearch_client=client)

    keyword = "KT06101"
    print(f"Searching for: {keyword}")

    try:
        # Manually execute search to inspect raw response
        query = service._build_aggregation_query(keyword, {}, 5)
        raw_response = service._execute_search(query)

        buckets = (
            raw_response.get("aggregations", {})
            .get("unique_documents", {})
            .get("buckets", [])
        )
        if buckets:
            first_hit = (
                buckets[0].get("doc_info", {}).get("hits", {}).get("hits", [])[0]
            )
            source = first_hit.get("_source", {})

            with open("debug_output.txt", "w", encoding="utf-8") as f:
                f.write("--- RAW SOURCE KEYS ---\n")
                f.write(str(list(source.keys())) + "\n")
                f.write("\n--- RAW SOURCE SAMPLE ---\n")
                f.write(str(source) + "\n")

            print("Debug output written to debug_output.txt")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_search()
