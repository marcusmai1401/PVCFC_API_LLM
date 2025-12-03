#!/usr/bin/env python
"""Quick script to check OpenSearch index status"""
from opensearchpy import OpenSearch

client = OpenSearch(hosts=[{'host': 'localhost', 'port': 9200}])

# Check if index exists
print('Checking indices...')
indices = client.cat.indices(format='json')
for idx in indices:
    print(f"  - {idx['index']}: {idx['docs.count']} docs")

# Check rag_chunks specifically
if client.indices.exists(index='rag_chunks'):
    count = client.count(index='rag_chunks')
    print(f"\nrag_chunks total docs: {count['count']}")
    
    # Sample a document to see structure
    result = client.search(index='rag_chunks', body={'size': 1})
    if result['hits']['hits']:
        doc = result['hits']['hits'][0]['_source']
        print(f"\nSample doc keys: {list(doc.keys())}")
        if 'metadata' in doc:
            print(f"Metadata keys: {list(doc['metadata'].keys())}")
            meta = doc['metadata']
            print(f"\nSample metadata:")
            print(f"  doc_id: {meta.get('doc_id', 'N/A')}")
            print(f"  filename: {meta.get('filename', 'N/A')}")
            print(f"  category: {meta.get('category', 'N/A')}")
else:
    print('\nrag_chunks index does not exist!')
