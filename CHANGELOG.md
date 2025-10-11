# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Internal improvements to documentation and scripts placement.

## [0.6.1] - Bug Fixes & Defensive Improvements (2025-10-11)

### Fixed
- Critical: Fixed negative confidence score bug causing 422 validation errors
  - Root cause: Cross-encoder reranking can return negative scores
  - Solution: Clamp negative/None scores to non-negative before confidence calculation (`max(0, (d.score or 0))`) and final clamp to [0, 1]
- Validation: Added confidence validation with logging in API layer
  - Detect invalid confidence (None, <0, >1), log ERROR with context and clamp for stability

### Added
- Documentation: SYSTEM_ARCHITECTURE.md (complete pipeline description)
- Documentation: CONFIDENCE_DEFENSIVE_IMPROVEMENTS.md (defensive programming guide)

### Changed
- Improved error handling for retrieval score processing
- Enhanced logging for invalid state detection

## [0.6.0] - Hybrid Modern Retrieval (2025-10-11)

### Added
- HybridWeaviateOpenSearchRetriever: Modern hybrid architecture (Weaviate + OpenSearch BM25)
  - Parallel retrieval, RRF fusion, optional BGE reranking
  - Health checks and graceful degradation when a backend fails
- OpenSearch BM25 integration with index `rag_chunks` (4,883 docs)
  - Configurable BM25 params: k1=1.2, b=0.75
  - ENV: OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_INDEX, OPENSEARCH_BM25_K1, OPENSEARCH_BM25_B, OPENSEARCH_TIMEOUT
- Integration tests: `tests/test_hybrid_modern.py` covering creation, health, stats, search, fusion, rerank (optional)
- Documentation updates: README with mode switch, OpenSearch config, known limitations, test guide

### Changed
- IndexManager mode selection simplified:
  - USE_HYBRID_MODERN=true  → Modern Hybrid (Weaviate + OpenSearch)
  - USE_HYBRID_MODERN=false → Legacy Hybrid (FAISS + BM25 offline)
  - Weaviate-only mode removed (Modern Hybrid degrades gracefully if OpenSearch is unavailable)
- Consistent retriever_type naming: "hybrid_legacy" (was "faiss")
- HybridRetriever.get_statistics enhanced to report OpenSearch details when applicable

### Fixed
- OpenSearch statistics reporting consistency
- Minor logging improvements for mode banners and health output

### Known issues
- Weaviate SDK filter limitation: some versions do not accept `where` in `near_vector()`. The system degrades to OpenSearch results. Recommend upgrading `weaviate-client` or adjusting filter application strategy.

## [0.5.0] - Phase 4: Weaviate Integration (2025-10-10)

### Added
- **Weaviate Vector Database Integration**
  - Replaced FAISS with Weaviate for production-grade vector search
  - Implemented `WeaviateRetriever` with gRPC support for high performance
  - Added Weaviate health checks and connection management
  - Created ingestion pipeline (`phase1_index_to_weaviate.py`) for data migration
  - Docker Compose setup for easy Weaviate deployment
  - Environment configuration for Weaviate connection settings

- **BGE CrossEncoder Reranking** (Phase 3)
  - Integrated BAAI/bge-reranker-base for semantic reranking
  - Multi-level reranking support: chunk, document, and page level
  - Configurable aggregation methods (max, mean, top3_mean)
  - Graceful degradation when reranking fails

### Changed
- **Retrieval Architecture Refactored**
  - Unified retriever interface supporting both HybridRetriever (FAISS) and WeaviateRetriever
  - Dynamic retriever selection based on `WEAVIATE_ENABLED` flag
  - Improved IndexManager with support for multiple backend types
  - Updated system status API to report Weaviate vs FAISS mode

- **Embedding Service Enhanced**
  - Fixed embedding task type configuration (removed inline comments from .env)
  - Proper method naming (`embed_texts` vs `get_embeddings`)
  - Improved batch processing and error handling

### Fixed
- Weaviate query building for v4 client compatibility
- Metadata extraction from Weaviate MetadataReturn objects
- Embedding service configuration parsing from environment variables
- Retrieval details logging for UI display in Weaviate mode

## [0.4.0] - Phase 3: Advanced Reranking (2025-10-09)

### Added
- **IEEE-Style Citation Feature**
  - Automatic conversion of `[Doc X, p.Y]` citations to IEEE-style `[n]` format
  - Interactive References section with numbered bibliography
  - Clickable PDF page links that open documents at exact pages
  - New `/api/pdf/open` endpoint for direct PDF viewing in browser
  - PDF fallback to image rendering with visual indicators (⚠️ icon)
  - Configurable toggle to switch between IEEE and traditional citation formats
  - Backend doc_number_map metadata export for citation mapping
  - Comprehensive unit test suite (9 tests, 100% pass rate)
  - Complete documentation in `docs/IEEE_CITATION_FEATURE.md`

### Changed
- Updated `app/rag/generator.py` to export document mapping metadata
- Enhanced `streamlit_app/components/query_lab_improved.py` with citation conversion logic
- Modified Query Lab UI to display 7 tabs instead of 8 (removed duplicate Citations tab)
- Improved citation display with file names extracted from PDF paths

### Fixed
- Citation deduplication when same document is referenced multiple times
- Page number aggregation for documents cited across multiple pages
- Graceful handling of missing PDF files with automatic fallback

## [0.3.0] - Phase 2: Enhanced Retrieval (2025-10-08)

### Added
- **Hybrid Retrieval Pipeline**
  - BM25 keyword search with configurable parameters (k1=1.2, b=0.75)
  - FAISS semantic search with embedding cache
  - Reciprocal Rank Fusion (RRF) for result merging
  - HyDE (Hypothetical Document Embeddings) support
  - Degrade mode: BM25-only fallback when FAISS fails

- **Vision Integration**
  - Multimodal generation with Gemini Vision models
  - Automatic page selection from retrieval results
  - PDF page rendering to JPEG for Vision input
  - Vision gating based on document availability

- **Query Transformation**
  - Query normalization and intent detection
  - Metadata filter extraction
  - Multi-language support (EN/VI)

### Changed
- Improved embedding service with batch processing
- Enhanced citation extraction with confidence scores
- Better error handling and graceful degradation

## [0.2.0] - Phase 1: Core RAG Pipeline (2025-10-05)

### Added
- **Document Ingestion**
  - PDF processing with PyMuPDF
  - OCR support for scanned documents (Tesseract)
  - Semantic chunking with overlap
  - Content deduplication (SHA1 hash)
  - Metadata extraction and enrichment

- **Index Building**
  - BM25 index construction
  - FAISS vector index with 768D embeddings
  - Production index building tools
  - Index statistics and validation

- **FastAPI Backend**
  - `/ask` endpoint for Q&A with citations
  - `/locate` endpoint for document search
  - `/index-stats` for index monitoring
  - Health check and metrics endpoints
  - Logging and tracing middleware

- **Streamlit UI**
  - Query Lab for testing and debugging
  - System Status dashboard
  - Citation display with PDF links
  - Multi-language support

### Infrastructure
- Docker support for deployment
- Environment-based configuration
- Comprehensive logging with Loguru
- Rate limiting and caching

## [0.1.0] - Initial Setup (2025-09-15)

### Added
- Project structure and dependencies
- Basic configuration management
- Development environment setup
- Initial documentation

---

## Release Notes

### Phase 4: Weaviate Integration (2025-10-10)

Major upgrade replacing FAISS with Weaviate vector database for production-ready vector search.

**Key Improvements:**
- 🚀 **Production-grade vector database** with Weaviate
- ⚡ **High performance** with gRPC support
- 🔄 **Seamless migration** from FAISS to Weaviate
- 📊 **Better monitoring** with health checks and stats
- 🎯 **BGE reranking** for improved relevance

**Migration Guide:**
1. Set `WEAVIATE_ENABLED=true` in `.env`
2. Run `docker-compose -f docker-compose-weaviate.yml up -d`
3. Execute `python scripts/phase1_index_to_weaviate.py` to migrate data
4. Restart API: `python -m uvicorn app.main:app --reload`

**Documentation:**
- [Weaviate Setup Guide](docs/guides/WEAVIATE_SETUP_GUIDE.md)
- [Weaviate Quickstart](docs/guides/WEAVIATE_QUICKSTART.md)
- [Phase 4 Completion Summary](docs/completion/PHASE4_COMPLETION_SUMMARY.md)

### IEEE Citation Feature v1.0.0 (2025-10-09)

Enhances citation handling with IEEE-style formatting and interactive PDF navigation.

**Key Benefits:**
- 📚 Professional IEEE-style citation format
- 🔗 One-click navigation to cited PDF pages
- ⚙️ Flexible configuration via UI toggle
- 🛡️ Robust error handling and fallbacks

**Documentation:** See [docs/implementation/IEEE_CITATION_IMPLEMENTATION_SUMMARY.md](docs/implementation/IEEE_CITATION_IMPLEMENTATION_SUMMARY.md)
