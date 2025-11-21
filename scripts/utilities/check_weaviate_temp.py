import weaviate

client = weaviate.connect_to_local()
collection = client.collections.get('Chunk')

doc_id = 'DOCID_K06101_CO2_COMPRESSOR_HITACHI_K06101_CO2_COMPRESSOR_HITACHI_Data_003_3N4-S427434_b6a8d1dc'

result = collection.query.fetch_objects(
    filters=weaviate.classes.query.Filter.by_property('doc_id').equal(doc_id),
    limit=10
)

print(f'Found {len(result.objects)} chunks in Weaviate for this doc')

if result.objects:
    print('\nSample chunks:')
    for i, obj in enumerate(result.objects[:3], 1):
        page = obj.properties.get('page')
        text = obj.properties.get('text', '')
        print(f'\n  Chunk {i} (Page {page}):')
        print(f'    Text: {text[:200]}...' if len(text) > 200 else f'    Text: {text}')

client.close()
