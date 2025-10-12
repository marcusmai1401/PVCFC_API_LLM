# P2: Storage & Indexing Schema

**Date**: 2025-10-02
**Phase**: P2 (Storage & Indexing)
**Status**: 🔨 IN PROGRESS

---

## 📝 Overview

P2 implements durable, versioned storage for chunks and embeddings using Parquet format with JSON manifests for lineage tracking.

---

## 🗄️ Parquet Schema

### Chunks Table

```python
{
    # Identifiers
    "chunk_id": string,              # Unique chunk ID
    "doc_id": string,                # Source document ID
    "page": int32,                   # Page number (nullable)
    "chunk_index": int32,            # Chunk sequence number

    # Content
    "text": string,                  # Chunk text content
    "content_hash": string,          # SHA256 hash for dedup

    # Chunking metadata
    "chunk_type": string,            # "text", "table", "pid", "mixed"
    "token_count": int32,            # Estimated tokens
    "char_count": int32,             # Character count

    # Embeddings
    "embedding": list<float>,        # 768D vector (nullable)
    "embedding_model": string,       # "gemini-embedding-001"
    "embedding_timestamp": timestamp,

    # P&ID specific (nullable)
    "equipment_tags": list<string>,  # ["P-101", "HX-202"]
    "bbox_data": string,             # JSON string with bbox list

    # Headers/structure (nullable)
    "headers": list<string>,         # Section headers
    "section_header": string,        # Parent section

    # Provenance
    "created_at": timestamp,
    "ingestion_version": string,     # "v1.2.3"
}
```

### Why Parquet?

- **Columnar**: Efficient for analytics and filtering
- **Compressed**: ~10x smaller than JSON (Snappy/ZSTD)
- **Typed**: Schema enforcement
- **Fast**: Predicate pushdown, skip unnecessary reads
- **Compatible**: Works with Pandas, Polars, DuckDB, Spark

---

## 📋 Manifest JSON Structure

### Ingestion Manifest (`manifest.json`)

```json
{
    "version": "1.0.0",
    "ingestion_id": "ingest_20251002_130000",
    "created_at": "2025-10-02T13:00:00Z",
    "config": {
        "chunk_size": 900,
        "chunk_overlap": 140,
        "embedding_model": "gemini-embedding-001",
        "embedding_dim": 768,
        "dedup_enabled": true
    },
    "source": {
        "data_dir": "D:\\Data_Raw",
        "total_files": 150,
        "processed_files": 21,
        "quarantined_files": 129
    },
    "chunks": {
        "total_chunks": 3791,
        "unique_chunks": 3245,
        "duplicate_chunks": 546,
        "avg_tokens_per_chunk": 875
    },
    "embeddings": {
        "total_embedded": 3245,
        "cache_hits": 546,
        "api_calls": 2699,
        "total_cost_usd": 0.54
    },
    "artifacts": {
        "chunks_parquet": "artifacts/ingestion/chunks_v1.parquet",
        "embeddings_parquet": "artifacts/ingestion/embeddings_v1.parquet",
        "manifest": "artifacts/ingestion/manifest_v1.json",
        "checksum_sha256": "abc123..."
    },
    "lineage": {
        "parent_version": null,
        "incremental": false
    }
}
```

### Index Manifest (`index_manifest.json`)

```json
{
    "version": "1.0.0",
    "index_id": "idx_20251002_140000",
    "created_at": "2025-10-02T14:00:00Z",
    "source_ingestion": "ingest_20251002_130000",
    "bm25": {
        "index_file": "artifacts/index_production/bm25/bm25_index.pkl",
        "documents_file": "artifacts/index_production/bm25/documents.json",
        "metadata_file": "artifacts/index_production/bm25/metadata.json",
        "total_documents": 3791,
        "vocab_size": 12543,
        "avg_doc_len": 217.5,
        "checksum": "def456..."
    },
    "faiss": {
        "index_file": "artifacts/index_production/faiss/faiss.index",
        "texts_file": "artifacts/index_production/faiss/texts.json",
        "metadatas_file": "artifacts/index_production/faiss/metadatas.json",
        "index_type": "IndexFlatIP",
        "dimension": 768,
        "total_vectors": 3245,
        "l2_normalized": true,
        "checksum": "ghi789..."
    }
}
```

---

## 📂 Directory Structure

```
artifacts/
├── ingestion/
│   ├── chunks_v1.parquet           # Main chunks table
│   ├── manifest_v1.json            # Ingestion manifest
│   ├── dedup_cache.txt             # Content hash cache
│   └── cache/
│       └── embeddings.sqlite       # Embedding cache
│
├── index_production/
│   ├── bm25/
│   │   ├── bm25_index.pkl
│   │   ├── documents.json
│   │   └── metadata.json
│   │
│   ├── faiss/
│   │   ├── faiss.index
│   │   ├── texts.json
│   │   └── metadatas.json
│   │
│   └── index_manifest.json         # Index metadata
│
└── versions/
    ├── v1/                          # Version snapshots
    │   ├── chunks_v1.parquet
    │   └── manifest_v1.json
    └── v2/
        ├── chunks_v2.parquet
        └── manifest_v2.json
```

---

## 🔄 Versioning Strategy

### Version Identifier

Format: `v{major}.{minor}.{patch}` or timestamp-based `v_20251002_130000`

### Incremental Ingestion

```json
{
    "lineage": {
        "parent_version": "v1",
        "incremental": true,
        "added_chunks": 245,
        "updated_chunks": 12,
        "deleted_chunks": 5
    }
}
```

### Version-Aware Retrieval

```python
# Load specific version
retriever = Retriever(index_version="v1")

# Load latest version (default)
retriever = Retriever(index_version="latest")
```

---

## 🎯 Design Goals

1. **Durability**: All data persisted to disk (Parquet + JSON)
2. **Versioning**: Full lineage tracking, rollback capability
3. **Performance**: Fast read/write with Parquet columnar format
4. **Compatibility**: Integrates with existing BM25/FAISS builders
5. **Observability**: Detailed manifests with metrics

---

## 🔧 Implementation Plan

### Phase 1: Writers
- Parquet writer for chunks
- Manifest JSON writer
- Checksum computation

### Phase 2: Integration
- Adapt BM25 builder to read from Parquet
- Adapt FAISS builder to read from Parquet
- Version tracking in indices

### Phase 3: Testing
- End-to-end ingestion → indexing → retrieval
- Version rollback test
- Performance benchmark

---

**Status**: ✅ Design Complete
**Ready for**: Implementation
**Owner**: Agent Mode (Warp AI)
