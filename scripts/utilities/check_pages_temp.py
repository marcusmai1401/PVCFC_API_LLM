from opensearchpy import OpenSearch

client = OpenSearch(['http://localhost:9200'])
doc_id = 'DOCID_K06101_CO2_COMPRESSOR_HITACHI_K06101_CO2_COMPRESSOR_HITACHI_Data_003_3N4-S427434_b6a8d1dc'

query = {
    'query': {'term': {'doc_id.keyword': doc_id}},
    'size': 0,
    'aggs': {'pages': {'terms': {'field': 'page', 'size': 20}}}
}

result = client.search(index='rag_chunks', body=query)
total = result['hits']['total']['value']

print(f'Total chunks for this doc: {total}')
print('\nPages with chunks:')
buckets = result.get('aggregations', {}).get('pages', {}).get('buckets', [])
for b in buckets:
    print(f"  Page {int(b['key'])}: {b['doc_count']} chunks")
