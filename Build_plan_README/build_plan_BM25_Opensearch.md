# Build Plan: Migrating BM25 to OpenSearch (rag_chunks)

Goal
- Replace offline BM25Okapi (rank-bm25, pickle files) with OpenSearch-backed BM25 search.
- Keep data source from artifacts/index_production/bm25 (documents.json + metadata.json).
- Provide scalable, production-ready keyword search via OpenSearch.
- Optional: integrate with Weaviate to form a hybrid retriever (OpenSearch BM25 + Weaviate semantic).

Assumptions
- OpenSearch is running on http://localhost:9200 (no security).
- We will use a single index: rag_chunks.
- Input files exist:
  - artifacts/index_production/bm25/documents.json
  - artifacts/index_production/bm25/metadata.json
- documents.json length == metadata.json length (N=4,883 in current prod snapshot).

High-level Steps
1) Define index settings + mappings (BM25 similarity, fields, analyzers)
2) Create index rag_chunks
3) Load documents.json + metadata.json
4) Bulk insert into OpenSearch (batched)
5) Implement BM25 search API (multi_match + filters)
6) Optional: Integrate into RAG pipeline hybrid with Weaviate

1) Index design (settings + mappings)
- Use default BM25 with k1=1.2 and b=0.75 (same as offline rank-bm25 config)
- Standard analyzer (supports EN reasonably; VI acceptable for now)
- Primary searchable fields: text (boost), heading (boost), title
- Exact-match fields: doc_id, chunk_id, revision, doc_type, author, file_name
- Numeric fields: page, page_start, page_end, chunk_index, level, table_count
- Boolean fields: has_table, has_torque_data
- Keyword array fields: table_keywords

Suggested Settings/Mapping (JSON)
```json
{
  "settings": {
    "index": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "refresh_interval": "1s",
      "similarity": {
        "default": {
          "type": "BM25",
          "b": 0.75,
          "k1": 1.2
        }
      }
    },
    "analysis": {
      "analyzer": {
        "default": {
          "type": "standard"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "chunk_id": {"type": "keyword"},
      "doc_id": {"type": "keyword"},
      "text": {"type": "text"},
      "heading": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
      "title": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
      "author": {"type": "keyword"},
      "doc_type": {"type": "keyword"},
      "revision": {"type": "keyword"},
      "source_format": {"type": "keyword"},
      "file_name": {"type": "keyword"},
      "chunk_index": {"type": "integer"},
      "parent_chunk_id": {"type": "keyword"},
      "level": {"type": "integer"},
      "page": {"type": "integer"},
      "page_start": {"type": "integer"},
      "page_end": {"type": "integer"},
      "page_nums": {"type": "integer"},
      "has_table": {"type": "boolean"},
      "table_count": {"type": "integer"},
      "table_keywords": {"type": "keyword"},
      "has_torque_data": {"type": "boolean"}
    }
  }
}
```

2) Create index script (Python, opensearch-py)
Dependencies
- pip install opensearch-py tqdm

Script snippet (create_index.py)
```python
from opensearchpy import OpenSearch

INDEX_NAME = "rag_chunks"
OS_HOST = "localhost"
OS_PORT = 9200

INDEX_BODY = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "1s",
            "similarity": {
                "default": {"type": "BM25", "b": 0.75, "k1": 1.2}
            },
        },
        "analysis": {"analyzer": {"default": {"type": "standard"}}},
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "text": {"type": "text"},
            "heading": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
            "title": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
            "author": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "revision": {"type": "keyword"},
            "source_format": {"type": "keyword"},
            "file_name": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "parent_chunk_id": {"type": "keyword"},
            "level": {"type": "integer"},
            "page": {"type": "integer"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "page_nums": {"type": "integer"},
            "has_table": {"type": "boolean"},
            "table_count": {"type": "integer"},
            "table_keywords": {"type": "keyword"},
            "has_torque_data": {"type": "boolean"},
        }
    },
}

client = OpenSearch(
    hosts=[{"host": OS_HOST, "port": OS_PORT}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)

if client.indices.exists(INDEX_NAME):
    print(f"Index '{INDEX_NAME}' already exists")
else:
    resp = client.indices.create(index=INDEX_NAME, body=INDEX_BODY)
    print("Created index:", resp)
```

3) Bulk insert from documents.json + metadata.json
- Input (Windows paths):
  - C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\index_production\\bm25\\documents.json
  - C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\index_production\\bm25\\metadata.json
- Ensure equal lengths and consistent pairing by index.

Script snippet (bulk_insert.py)
```python
import json
from pathlib import Path
from typing import Iterator

from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

INDEX_NAME = "rag_chunks"
DOCS_PATH = Path("artifacts/index_production/bm25/documents.json")
META_PATH = Path("artifacts/index_production/bm25/metadata.json")

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)

def load_data():
    with open(DOCS_PATH, "r", encoding="utf-8") as f:
        documents = json.load(f)
    with open(META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    assert len(documents) == len(metadata), "documents and metadata length mismatch"
    return documents, metadata


def normalize_record(text: str, meta: dict) -> dict:
    # Derive 'page' if not present
    page = meta.get("page")
    if page is None:
        if meta.get("page_start") is not None and meta.get("page_end") is not None:
            page = meta.get("page_start")
        else:
            page = 1

    doc = {
        "text": text or "",
        "chunk_id": meta.get("chunk_id"),
        "doc_id": meta.get("doc_id"),
        "chunk_index": meta.get("chunk_index", 0),
        "parent_chunk_id": meta.get("parent_chunk_id"),
        "heading": meta.get("heading"),
        "title": meta.get("title"),
        "author": meta.get("author"),
        "level": meta.get("level"),
        "doc_type": meta.get("doc_type"),
        "revision": meta.get("revision"),
        "source_format": meta.get("source_format"),
        "file_name": meta.get("file_name"),
        "page": page,
        "page_start": meta.get("page_start"),
        "page_end": meta.get("page_end"),
        "page_nums": (meta.get("page_nums")[0] if meta.get("page_nums") else None),
        "has_table": meta.get("has_table"),
        "table_count": meta.get("table_count"),
        "table_keywords": meta.get("table_keywords", []),
        "has_torque_data": meta.get("has_torque_data"),
    }
    return doc


def actions_generator(documents, metadata) -> Iterator[dict]:
    for i, (text, meta) in enumerate(zip(documents, metadata)):
        body = normalize_record(text, meta)
        _id = body.get("chunk_id") or f"rag_{i}"
        yield {
            "_op_type": "index",
            "_index": INDEX_NAME,
            "_id": _id,
            "_source": body,
        }


def main():
    documents, metadata = load_data()
    total = len(documents)
    print(f"Indexing {total} documents to '{INDEX_NAME}'...")

    # Faster bulk indexing: disable autorefresh during bulk and refresh at the end
    client.indices.put_settings(index=INDEX_NAME, body={"index": {"refresh_interval": -1}})

    success, errors = helpers.bulk(
        client,
        actions_generator(documents, metadata),
        index=INDEX_NAME,
        chunk_size=1000,
        request_timeout=120,
        refresh=False,
    )

    # Restore refresh
    client.indices.put_settings(index=INDEX_NAME, body={"index": {"refresh_interval": "1s"}})
    client.indices.refresh(index=INDEX_NAME)

    print(f"Bulk done. success={success}, errors={len(errors) if isinstance(errors, list) else errors}")
    count = client.count(index=INDEX_NAME)["count"]
    print(f"Index '{INDEX_NAME}' now has {count} docs")


if __name__ == "__main__":
    main()
```

4) BM25 search via OpenSearch
- Use multi_match across text^3, heading^2, title
- Optional filters: doc_type, doc_id, page range, revision, etc.

Script snippet (search_opensearch.py)
```python
from typing import List, Optional
from opensearchpy import OpenSearch

INDEX_NAME = "rag_chunks"

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)

def bm25_search(query: str, top_k: int = 20, filters: Optional[dict] = None):
    must = [{
        "multi_match": {
            "query": query,
            "fields": ["text^3", "heading^2", "title"],
            "type": "best_fields",
            "operator": "and"
        }
    }]

    filter_clauses = []
    if filters:
        if filters.get("doc_type"):
            filter_clauses.append({"terms": {"doc_type": filters["doc_type"]}})
        if filters.get("doc_ids"):
            filter_clauses.append({"terms": {"doc_id": filters["doc_ids"]}})
        if filters.get("page_min") or filters.get("page_max"):
            rng = {}
            if filters.get("page_min") is not None:
                rng["gte"] = filters["page_min"]
            if filters.get("page_max") is not None:
                rng["lte"] = filters["page_max"]
            filter_clauses.append({"range": {"page": rng}})

    body = {
        "size": top_k,
        "query": {
            "bool": {
                "must": must,
                "filter": filter_clauses,
            }
        },
        "highlight": {"fields": {"text": {}}}
    }

    resp = client.search(index=INDEX_NAME, body=body)
    hits = resp["hits"]["hits"]

    results = []
    for h in hits:
        src = h.get("_source", {})
        results.append({
            "chunk_id": src.get("chunk_id"),
            "doc_id": src.get("doc_id"),
            "text": src.get("text"),
            "score": h.get("_score", 0.0),
            "page": src.get("page"),
            "metadata": src,
            "highlight": h.get("highlight", {}).get("text", [])
        })
    return results

if __name__ == "__main__":
    out = bm25_search("CO2 compressor", top_k=10)
    for i, r in enumerate(out, 1):
        print(f"{i:02d}. score={r['score']:.4f} doc={r['doc_id']} page={r['page']} text={r['text'][:100]}...")
```

REST alternative (curl)
```bash
curl -X POST "http://localhost:9200/rag_chunks/_search" -H "Content-Type: application/json" -d '{
  "size": 10,
  "query": {
    "bool": {
      "must": [
        {"multi_match": {"query": "CO2 compressor", "fields": ["text^3", "heading^2", "title"], "type": "best_fields", "operator": "and"}}
      ],
      "filter": []
    }
  },
  "highlight": {"fields": {"text": {}}}
}'
```

5) Optional: Integrate with RAG pipeline (Hybrid: OpenSearch BM25 + Weaviate)
- Add settings (app/core/config.py):
  - OPENSEARCH_ENABLED=true
  - OPENSEARCH_HOST=localhost
  - OPENSEARCH_PORT=9200
  - OPENSEARCH_INDEX=rag_chunks
- Implement a retriever class OpenSearchBM25Retriever with search(transformed_query)
- Hybrid aggregator: combine OpenSearch results with Weaviate results using RRF (reuse existing _reciprocal_rank_fusion logic from HybridRetriever)

Retriever sketch (pseudo-code)
```python
class OpenSearchBM25Retriever:
    def __init__(self, host="localhost", port=9200, index_name="rag_chunks"):
        self.client = OpenSearch(hosts=[{"host": host, "port": port}], http_compress=True, use_ssl=False, verify_certs=False)
        self.index = index_name

    def search(self, transformed_query, top_k=50):
        results = bm25_search(transformed_query.normalized, top_k=top_k, filters=transformed_query.filters.dict() if transformed_query.filters else None)
        # Convert to RetrievalResult objects expected by generator
        converted = []
        for r in results:
            converted.append(RetrievalResult(
                chunk_id=r["chunk_id"],
                text=r["text"],
                score=float(r["score"]),
                source="opensearch",
                metadata=r["metadata"],
                doc_id=r["doc_id"],
                page=r.get("page"),
            ))
        return converted
```

Hybrid aggregator (Weaviate + OpenSearch)
- Reuse existing HybridRetriever fusion logic
- Replace BM25Indexer with OpenSearchBM25Retriever, and FAISS with WeaviateRetriever
- Keep BGE rerank at aggregator level (avoid double reranking)

6) Validation & Tuning Checklist
- Data parity
  - Verify doc count: GET /rag_chunks/_count equals len(documents.json)
  - Spot-check several queries: compare top hits vs offline BM25Okapi
- Performance
  - Batch size: 1,000 for bulk is good; adjust based on machine (Windows SSD ok)
  - refresh_interval: -1 during bulk, restore after; do indices.refresh at end
- Relevance
  - Field boosts: text^3, heading^2, title^1 (adjust per corpus)
  - Operator: "and" yields precision; switch to "or" if recall is too low
  - Consider phrase queries (match_phrase) for exact technical terms
- Similarity params
  - BM25 k1=1.2, b=0.75; consider tuning for your corpus
- Analyzer
  - Standard analyzer is acceptable; can add custom analyzers later (Vietnamese, synonyms)

7) Rollout plan
- Create rag_chunks in a dev namespace
- Bulk load and validate
- Add retriever integration behind OPENSEARCH_ENABLED flag
- Canary switch pipeline to OpenSearch BM25 for a subset of traffic
- Monitor latency and relevance, iterate boosts/analyzers

8) Backout plan
- Keep offline bm25_index.pkl as fallback (unchanged)
- Maintain toggle to switch BM25 backend (offline vs OpenSearch) via config
- If needed, drop rag_chunks index and recreate

Command Summary
- Create index: python create_index.py
- Bulk insert: python bulk_insert.py
- Search test: python search_opensearch.py "CO2 compressor"

Notes
- No auth assumed (security disabled). If enabling later, opensearch-py supports basic auth and SSL.
- Differences from offline rank-bm25 scoring are expected due to analyzer/tokenization differences.
- Weaviate hybrid integration remains unchanged except BM25 source now uses OpenSearch.
