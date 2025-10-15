"""
Check Instrument List chunks directly from OpenSearch
"""
try:
    from opensearchpy import OpenSearch

    # Connect to OpenSearch
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=30,
    )

    # Search for Instrument List chunks
    doc_id_pattern = "DOCID_KT06101_TURBINE_HTC_KT06101_TURBINE_HTC_Instrument_116_3N4"

    query = {
        "query": {"bool": {"must": [{"wildcard": {"doc_id": f"*{doc_id_pattern}*"}}]}},
        "size": 100,
        "_source": ["doc_id", "chunk_id", "text", "page", "metadata"],
    }

    print("=" * 80)
    print("SEARCHING OPENSEARCH FOR INSTRUMENT LIST CHUNKS")
    print("=" * 80)
    print(f"Index: rag_chunks")
    print(f"Filter: doc_id contains '{doc_id_pattern}'")
    print()

    response = client.search(index="rag_chunks", body=query)
    hits = response["hits"]["hits"]

    print(f"Found {len(hits)} chunks")
    print()

    # Check for Tag number patterns
    tag_patterns = ["06-TE-0256", "06 TE 0256", "06TE0256", "0256", "TE-0256"]

    for i, hit in enumerate(hits, 1):
        source = hit["_source"]
        text = source.get("text", "")
        page = source.get("page", "?")

        # Check if Tag appears in text
        found_patterns = []
        text_upper = text.upper().replace("-", " ").replace("_", " ")

        for pattern in tag_patterns:
            pattern_norm = pattern.upper().replace("-", " ").replace("_", " ")
            if pattern_norm in text_upper:
                found_patterns.append(pattern)

        if found_patterns or page in [4, 5, 6]:
            print(f"Chunk #{i} (page {page}):")
            print(f"  Length: {len(text)} chars")
            if found_patterns:
                print(f"  ✅ FOUND patterns: {', '.join(found_patterns)}")
            print(f"  Preview: {text[:300]}...")
            print()

    # Summary
    chunks_with_tag = sum(
        1
        for hit in hits
        if any(
            p.upper().replace("-", " ")
            in hit["_source"].get("text", "").upper().replace("-", " ")
            for p in tag_patterns
        )
    )

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total chunks: {len(hits)}")
    print(f"Chunks with Tag pattern: {chunks_with_tag}")
    print()

    if chunks_with_tag == 0:
        print("❌ Tag number '06-TE-0256' NOT FOUND in any chunk!")
        print("\nThis confirms the OCR/chunking issue:")
        print("  - Either Tag was not OCR'd correctly")
        print("  - Or Tag was split across multiple chunks")
        print("  - Or pages 4-6 were not indexed at all")
    else:
        print(f"✅ Tag found in {chunks_with_tag} chunk(s)")
        print("\nBut retrieval still fails, so the issue is:")
        print("  - BM25 tokenization doesn't match query format")
        print("  - Or other documents have higher scores")
        print("  - Or Tag needs metadata extraction for exact match")

except ImportError:
    print("❌ opensearchpy not installed. Please install: pip install opensearch-py")
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nMake sure:")
    print("  - OpenSearch is running (docker-compose up)")
    print("  - Index 'rag_chunks' exists")
    print("  - Data has been ingested")
