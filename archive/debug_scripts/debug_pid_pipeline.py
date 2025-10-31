"""
Multi-Layer Debug Script for P&ID Pipeline
Debugs a failed query through all 6 layers to identify exact failure point
"""
import sys

sys.path.insert(0, ".")

import json
from typing import Dict, Optional

import requests
from opensearchpy import OpenSearch


def parse_tag_components(tag: str) -> Dict:
    """Parse tag into components"""
    parts = tag.split()
    if len(parts) >= 3:
        unit = parts[0]
        prefix = parts[1]
        suffix_raw = parts[2]
        # Extract suffix (digits only) and variant (letter)
        suffix = suffix_raw.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        variant = suffix_raw[len(suffix) :] if len(suffix_raw) > len(suffix) else None

        return {
            "unit": unit,
            "prefix": prefix,
            "suffix": suffix,
            "variant": variant,
            "raw": tag,
        }
    return {}


def layer1_opensearch_direct(tag: str, expected_page: int) -> Dict:
    """Layer 1: Direct OpenSearch query on pvcfc_pid_tags"""

    print("\n" + "=" * 80)
    print("LAYER 1: OpenSearch Direct Query")
    print("=" * 80)

    components = parse_tag_components(tag)
    if not components:
        return {"status": "PARSE_ERROR", "error": "Cannot parse tag"}

    print(f"Parsed components: {components}")

    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}], http_compress=True, timeout=10
    )

    # Query using nested paths (after fix)
    query_body = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"parts.unit.keyword": components["unit"]}},
                    {"term": {"parts.prefix.keyword": components["prefix"]}},
                    {"term": {"parts.suffix.keyword": components["suffix"]}},
                ]
            }
        },
        "size": 10,
    }

    print(f"Query body: {json.dumps(query_body, indent=2)}")

    try:
        response = client.search(index="pvcfc_pid_tags", body=query_body)
        hits = response["hits"]["hits"]

        print(f"\nResults: {len(hits)} hits")

        if hits:
            for i, hit in enumerate(hits[:3], 1):
                source = hit["_source"]
                print(
                    f"  {i}. Tag: {source.get('tag')}, Page: {source.get('page')}, Score: {hit['_score']:.2f}"
                )
                print(f"     Bbox: {source.get('bbox', [])[:4]}...")

            # Check expected page
            pages = [h["_source"].get("page") for h in hits]
            if expected_page in pages:
                print(
                    f"\nStatus: PASS - Expected page {expected_page} found in results"
                )
                return {"status": "PASS", "hits": len(hits), "pages": pages}
            else:
                print(
                    f"\nStatus: FAIL - Expected page {expected_page} NOT in results: {pages}"
                )
                return {"status": "FAIL", "hits": len(hits), "pages": pages}
        else:
            print("\nStatus: FAIL - No results from OpenSearch")
            return {"status": "FAIL", "hits": 0, "error": "No results"}

    except Exception as e:
        print(f"\nStatus: ERROR - {e}")
        return {"status": "ERROR", "error": str(e)}


def layer2_tags_retriever(tag: str, expected_page: int) -> Dict:
    """Layer 2: OpenSearchTagsRetriever.search_by_components()"""

    print("\n" + "=" * 80)
    print("LAYER 2: Tags Retriever (search_by_components)")
    print("=" * 80)

    try:
        from app.rag.indexers.opensearch_tags_retriever import OpenSearchTagsRetriever

        retriever = OpenSearchTagsRetriever(index_name="pvcfc_pid_tags")
        components = parse_tag_components(tag)

        print(f"Calling: search_by_components({components})")

        results = retriever.search_by_components(
            unit=components.get("unit"),
            prefix=components.get("prefix"),
            suffix=components.get("suffix"),
            variant=components.get("variant"),
        )

        print(f"\nResults: {len(results)}")

        if results:
            for i, r in enumerate(results[:3], 1):
                print(
                    f"  {i}. Tag: {r.get('text')}, Page: {r.get('page')}, Score: {r.get('score', 0):.2f}"
                )

            pages = [r.get("page") for r in results]
            if expected_page in pages:
                print(f"\nStatus: PASS")
                return {"status": "PASS", "results": len(results), "pages": pages}
            else:
                print(f"\nStatus: FAIL - Expected page {expected_page} not found")
                return {"status": "FAIL", "results": len(results), "pages": pages}
        else:
            print("\nStatus: FAIL - No results")
            return {"status": "FAIL", "results": 0}

    except Exception as e:
        print(f"\nStatus: ERROR - {e}")
        import traceback

        traceback.print_exc()
        return {"status": "ERROR", "error": str(e)}


def layer3_pid_enhancer(query: str) -> Dict:
    """Layer 3: PIDQueryEnhancer.enhance()"""

    print("\n" + "=" * 80)
    print("LAYER 3: PID Query Enhancer")
    print("=" * 80)

    try:
        from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

        enhancer = PIDQueryEnhancer()

        print(f"Input query: '{query}'")

        enhanced = enhancer.enhance(query)

        print(f"\nEnhanced result:")
        print(f"  Strategy: {enhanced.get('strategy')}")
        print(f"  Query type: {enhanced.get('query_type')}")
        print(f"  Tags: {enhanced.get('tags', [])}")
        print(f"  Components: {enhanced.get('components', {})}")

        # Check if components detected
        has_components = enhanced.get("components") or enhanced.get("tags")

        if has_components:
            print(f"\nStatus: PASS - Components detected")
            return {"status": "PASS", "enhanced": enhanced}
        else:
            print(f"\nStatus: FAIL - No components detected")
            return {"status": "FAIL", "enhanced": enhanced}

    except Exception as e:
        print(f"\nStatus: ERROR - {e}")
        import traceback

        traceback.print_exc()
        return {"status": "ERROR", "error": str(e)}


def layer4_hybrid_retriever(query: str, expected_page: int) -> Dict:
    """Layer 4: HybridWithTagsRetriever.search()"""

    print("\n" + "=" * 80)
    print("LAYER 4: Hybrid With Tags Retriever")
    print("=" * 80)

    try:
        from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever
        from app.rag.query_transform import QueryTransformer

        # Transform query
        transformer = QueryTransformer(enable_hyde=False)
        transformed = transformer.transform(query, query_type_override="pid")

        print(f"Transformed query: '{transformed.normalized}'")

        # Search
        retriever = HybridWithTagsRetriever()
        results = retriever.search(transformed, top_k=10)

        print(f"\nResults: {len(results)}")

        if results:
            for i, r in enumerate(results[:5], 1):
                print(
                    f"  {i}. Page: {r.page}, Score: {r.score:.2f}, Source: {r.source}"
                )
                print(f"     Text: {r.text[:80]}...")

            pages = [r.page for r in results]
            if expected_page in pages:
                print(f"\nStatus: PASS")
                return {"status": "PASS", "results": len(results), "pages": pages}
            else:
                print(f"\nStatus: FAIL")
                return {"status": "FAIL", "results": len(results), "pages": pages}
        else:
            print("\nStatus: FAIL - No results")
            return {"status": "FAIL", "results": 0}

    except Exception as e:
        print(f"\nStatus: ERROR - {e}")
        import traceback

        traceback.print_exc()
        return {"status": "ERROR", "error": str(e)}


def layer5_api_call(query: str, expected_page: int) -> Dict:
    """Layer 5: Full API /ask endpoint"""

    print("\n" + "=" * 80)
    print("LAYER 5: API /ask Endpoint")
    print("=" * 80)

    payload = {
        "query": query,
        "query_type": "pid",
        "language": "vi",
        "max_context": 8,
        "execution_mode": "production",
    }

    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post("http://localhost:8000/ask", json=payload, timeout=120)

        if response.ok:
            data = response.json()
            citations = data.get("citations", [])

            print(f"\nResponse:")
            print(f"  Citations: {len(citations)}")
            print(f"  Confidence: {data.get('confidence', 0):.2f}")
            print(f"  Latency: {data.get('meta', {}).get('latency_ms')}ms")

            if citations:
                print(f"\n  Top citations:")
                for i, c in enumerate(citations[:5], 1):
                    print(
                        f"    {i}. Page: {c.get('page')}, Bbox: {'YES' if c.get('bbox') else 'NO'}"
                    )

                pages = [c.get("page") for c in citations]
                if expected_page in pages[:5]:
                    print(f"\nStatus: PASS")
                    return {"status": "PASS", "response": data}
                else:
                    print(f"\nStatus: FAIL - Expected page not in top-5")
                    return {"status": "FAIL", "response": data}
            else:
                print("\nStatus: FAIL - No citations")
                return {"status": "FAIL", "response": data}
        else:
            print(f"\nStatus: ERROR - HTTP {response.status_code}")
            return {"status": "ERROR", "error": response.text[:500]}

    except Exception as e:
        print(f"\nStatus: ERROR - {e}")
        return {"status": "ERROR", "error": str(e)}


def debug_query(tag: str, expected_page: int, query_text: str):
    """Debug a single failed query through all layers"""

    print("\n" + "#" * 80)
    print(f"# DEBUG PIPELINE FOR: {tag} (Expected Page: {expected_page})")
    print("#" * 80)

    results = {}

    # Run all layers
    results["layer1"] = layer1_opensearch_direct(tag, expected_page)
    results["layer2"] = layer2_tags_retriever(tag, expected_page)
    results["layer3"] = layer3_pid_enhancer(query_text)
    results["layer4"] = layer4_hybrid_retriever(query_text, expected_page)
    results["layer5"] = layer5_api_call(query_text, expected_page)

    # Analysis
    print("\n" + "=" * 80)
    print("DEBUG ANALYSIS")
    print("=" * 80)

    layer_status = {k: v.get("status") for k, v in results.items()}
    print(f"Layer Status: {layer_status}")

    # Identify failure point
    if results["layer1"]["status"] != "PASS":
        print("\nFAILURE POINT: Layer 1 - OpenSearch Direct")
        print("DIAGNOSIS: Tag not in index or wrong search query")
        print("ACTION: Check if tag was extracted and indexed correctly")
    elif results["layer2"]["status"] != "PASS":
        print("\nFAILURE POINT: Layer 2 - Tags Retriever")
        print("DIAGNOSIS: search_by_components() not working")
        print("ACTION: Check OpenSearchTagsRetriever implementation")
    elif results["layer3"]["status"] != "PASS":
        print("\nFAILURE POINT: Layer 3 - PID Enhancer")
        print("DIAGNOSIS: Query enhancement not detecting components")
        print("ACTION: Check PIDQueryEnhancer.enhance() logic")
    elif results["layer4"]["status"] != "PASS":
        print("\nFAILURE POINT: Layer 4 - Hybrid Retriever")
        print("DIAGNOSIS: Tags results not making it to final output")
        print("ACTION: Check HybridWithTagsRetriever fusion logic")
    elif results["layer5"]["status"] != "PASS":
        print("\nFAILURE POINT: Layer 5 - API Response")
        print("DIAGNOSIS: Results lost in API response formatting")
        print("ACTION: Check ask.py citation extraction")
    else:
        print("\nAll layers PASS individually but E2E fails")
        print("DIAGNOSIS: Possible race condition or caching issue")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python debug_pid_pipeline.py <tag> <expected_page> [query_text]")
        print(
            'Example: python debug_pid_pipeline.py "04 PSV 3926" 41 "Tìm cho tôi tag name 04 PSV 3926 trong bản vẽ P&ID"'
        )
        sys.exit(1)

    tag = sys.argv[1]
    expected_page = int(sys.argv[2])
    query_text = sys.argv[3] if len(sys.argv) > 3 else f"Tìm tag {tag}"

    debug_query(tag, expected_page, query_text)
