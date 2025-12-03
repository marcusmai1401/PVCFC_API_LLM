"""Debug why OpenSearch query by doc_id returns 0 results"""

from opensearchpy import OpenSearch

client = OpenSearch(["http://localhost:9200"])

# Our target doc_id
doc_id = "DOCID_K06101_CO2_COMPRESSOR_HITACHI_K06101_CO2_COMPRESSOR_HITACHI_Data_003_3N4-S427434_b6a8d1dc"

print("Testing different query approaches:\n")

# Approach 1: Term query with .keyword
print("1. Term query with .keyword:")
query1 = {"query": {"term": {"doc_id.keyword": doc_id}}, "size": 1}
result1 = client.search(index="rag_chunks", body=query1)
print(f"   Results: {result1['hits']['total']['value']}")

# Approach 2: Term query without .keyword
print("\n2. Term query without .keyword:")
query2 = {"query": {"term": {"doc_id": doc_id}}, "size": 1}
result2 = client.search(index="rag_chunks", body=query2)
print(f"   Results: {result2['hits']['total']['value']}")

# Approach 3: Match query
print("\n3. Match query:")
query3 = {"query": {"match": {"doc_id": doc_id}}, "size": 1}
result3 = client.search(index="rag_chunks", body=query3)
print(f"   Results: {result3['hits']['total']['value']}")

# Approach 4: Prefix search to find similar doc_ids
print("\n4. Prefix search (first 50 chars):")
prefix = doc_id[:50]
query4 = {"query": {"prefix": {"doc_id.keyword": prefix}}, "size": 5}
result4 = client.search(index="rag_chunks", body=query4)
print(f"   Results: {result4['hits']['total']['value']}")
if result4["hits"]["hits"]:
    print("   Sample doc_ids:")
    for hit in result4["hits"]["hits"][:3]:
        print(f"     - {hit['_source']['doc_id']}")

# Approach 5: Search by filename instead
print("\n5. Search by file_name:")
filename = "003_3N4-S4274344 Expected Performance Curve of Compressor_Rev.01.pdf"
query5 = {"query": {"match": {"file_name": filename}}, "size": 5}
result5 = client.search(index="rag_chunks", body=query5)
print(f"   Results: {result5['hits']['total']['value']}")
if result5["hits"]["hits"]:
    print("   Sample doc_ids from this file:")
    for hit in result5["hits"]["hits"][:3]:
        print(f"     - {hit['_source']['doc_id']}")
        print(f"       Page: {hit['_source'].get('page')}")

# Approach 6: Check index mapping
print("\n6. Check doc_id field mapping:")
mapping = client.indices.get_mapping(index="rag_chunks")
doc_id_mapping = mapping["rag_chunks"]["mappings"]["properties"].get("doc_id", {})
print(f"   Type: {doc_id_mapping.get('type', 'N/A')}")
print(f"   Fields: {list(doc_id_mapping.get('fields', {}).keys())}")
