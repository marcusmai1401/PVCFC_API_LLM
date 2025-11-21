from opensearchpy import OpenSearch

client = OpenSearch(['http://localhost:9200'])

query = {
    'query': {
        'bool': {
            'must': [
                {'match': {'text': '17800'}},
                {'match': {'text': 'performance curve'}}
            ]
        }
    },
    'size': 5,
    '_source': ['doc_id', 'page', 'file_name', 'text']
}

result = client.search(index='rag_chunks', body=query)
total = result['hits']['total']['value']

print(f'✅ Found {total} chunks with "17800" and "performance curve"\n')

if result['hits']['hits']:
    print('Top results:')
    for i, hit in enumerate(result['hits']['hits'], 1):
        source = hit['_source']
        text_preview = source.get('text', '')[:200]
        print(f'\n{i}. {source.get("file_name")} (page {source.get("page")})')
        print(f'   Score: {hit["_score"]:.2f}')
        print(f'   Text: {text_preview}...')
