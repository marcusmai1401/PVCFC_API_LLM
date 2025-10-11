# OpenSearch BM25 Migration Scripts

Scripts để migrate BM25 index từ offline rank-bm25 sang OpenSearch production-ready search.

## 📋 Overview

Thư mục này chứa các scripts để:
1. Tạo index `rag_chunks` trên OpenSearch với BM25 similarity
2. Bulk insert dữ liệu từ artifacts/index_production/bm25
3. Test và verify search functionality

## 🚀 Quick Start

### 1. Tạo Index

```bash
python scripts/opensearch/create_rag_chunks_index.py
```

Options:
- `--delete-if-exists`: Xóa index cũ nếu tồn tại

### 2. Insert Data

```bash
# Dry run (preview without inserting)
python scripts/opensearch/bulk_insert_to_opensearch.py --dry-run

# Actual insert
python scripts/opensearch/bulk_insert_to_opensearch.py --batch-size 1000
```

Options:
- `--dry-run`: Preview 5 records đầu tiên
- `--batch-size N`: Số documents per batch (default: 1000)

### 3. Test Search

```bash
# Single query
python scripts/opensearch/test_opensearch_search.py "CO2 compressor" --top-k 10

# Test suite
python scripts/opensearch/test_opensearch_search.py --test-suite
```

## 📊 Index Schema

### Settings
- **BM25 parameters**: k1=1.2, b=0.75 (matching offline rank-bm25)
- **Shards**: 1 (sufficient for current data size)
- **Replicas**: 0 (single node setup)
- **Analyzer**: Standard (good for EN/VI text)

### Mapped Fields

#### Core Identifiers
- `chunk_id` (keyword) - Unique chunk identifier
- `doc_id` (keyword) - Document identifier

#### Searchable Text (with field boosts)
- `text` (text) - Main content, boost=3
- `heading` (text) - Section headings, boost=2
- `title` (text) - Document title, boost=1

#### Metadata
- `doc_type` (keyword) - Document type (Manual, Data, etc.)
- `revision`, `author`, `source_format`, `file_name` (keyword)
- `chunk_index`, `level` (integer)

#### Page Information (critical for citations)
- `page`, `page_start`, `page_end`, `page_nums` (integer)

#### Table Metadata
- `has_table` (boolean)
- `table_count` (integer)
- `table_keywords` (keyword array)
- `has_torque_data` (boolean)

## 📈 Performance

### Indexing Speed
- **4,883 documents** indexed in ~1 second
- **Throughput**: ~5,169 docs/second
- **Store size**: ~6.5 MB (with compression)

### Search Performance
- **Avg latency**: 50-150ms for top-10 queries
- **Highlighting**: Enabled with 2 fragments per field
- **Filters**: Support doc_type, page ranges, doc_ids

## 🔍 Search Examples

### Basic Search
```python
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)

body = {
    "size": 10,
    "query": {
        "multi_match": {
            "query": "CO2 compressor",
            "fields": ["text^3", "heading^2", "title"],
            "type": "best_fields"
        }
    },
    "highlight": {"fields": {"text": {}}}
}

results = client.search(index="rag_chunks", body=body)
```

### Filtered Search
```python
body = {
    "query": {
        "bool": {
            "must": [
                {"multi_match": {"query": "torque", "fields": ["text^3", "heading^2"]}}
            ],
            "filter": [
                {"terms": {"doc_type": ["Manual", "Data"]}},
                {"range": {"page": {"gte": 1, "lte": 100}}}
            ]
        }
    }
}
```

## 🔧 Troubleshooting

### Index doesn't exist
```bash
python scripts/opensearch/create_rag_chunks_index.py
```

### Connection refused
```bash
# Check if OpenSearch is running
curl http://localhost:9200

# Start OpenSearch
docker-compose up -d opensearch
```

### Verify document count
```bash
curl http://localhost:9200/rag_chunks/_count
# Should return: {"count":4883}
```

## 📝 Notes

### Data Source
- **Documents**: `artifacts/index_production/bm25/documents.json`
- **Metadata**: `artifacts/index_production/bm25/metadata.json`
- **Count**: 4,883 chunks from production ingestion

### BM25 Configuration
- **k1=1.2**: Term frequency saturation (standard)
- **b=0.75**: Length normalization (standard)
- Matches offline rank-bm25 parameters for consistency

### Field Boosts
Current configuration:
- `text^3` - Highest boost (main content)
- `heading^2` - Medium boost (section headers)
- `title^1` - Default boost (document titles)

Adjust these in the search query based on your relevance needs.

### Analyzer
Uses **standard** analyzer which:
- Tokenizes on word boundaries
- Lowercases tokens
- Removes stop words (optional)
- Works reasonably well for both EN and VI

For better Vietnamese support, consider adding a custom analyzer with Vietnamese-specific tokenization in future iterations.

## 🎯 Next Steps

1. **Integration**: Create `OpenSearchBM25Retriever` class
2. **Hybrid Search**: Combine with Weaviate semantic search
3. **Config**: Add environment variables (OPENSEARCH_ENABLED, etc.)
4. **Testing**: Compare results with offline BM25 for data parity
5. **Monitoring**: Set up OpenSearch dashboards for index health

## 📚 References

- [OpenSearch Python Client](https://opensearch.org/docs/latest/clients/python-low-level/)
- [BM25 Similarity](https://opensearch.org/docs/latest/search-plugins/similarity/)
- [Index Management](https://opensearch.org/docs/latest/api-reference/index-apis/index/)
