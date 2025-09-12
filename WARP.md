# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a **Vietnamese and English technical documentation RAG (Retrieval-Augmented Generation) system** for PVCFC that provides intelligent querying of technical documents including P&ID diagrams, equipment datasheets, and operational procedures. The system uses advanced RAG architecture with hybrid retrieval (FAISS + BM25), cross-encoder reranking, and forced citation generation.

**Core Capabilities:**
- Multi-format document processing (vector PDFs, scanned PDFs)
- Intelligent chunking with hierarchical structure  
- Hybrid search with semantic and keyword matching
- Three main API endpoints: `/ask`, `/locate`, `/report`
- Citation-backed answers with source traceability

## Development Phases & Architecture

The project follows a 4-phase development plan:

### Phase 0: Foundation & Setup
```bash
# Initial setup commands
make dev          # Create venv and install dependencies
make run          # Start FastAPI server
make test         # Run tests
make smoke        # Test LLM connectivity
```

### Phase 1: Document Ingestion & Indexing
```bash
# Document processing commands
make ingest-pilot       # Ingest pilot documents
make build-index        # Build FAISS + BM25 indices
make clean-processed    # Clean processed data for rebuild

# Manual ingest commands
python tools/ingest.py --source data/raw --doc-id PVCFC-PID-04000-v1
python tools/build_index.py --faiss artifacts/index/faiss --bm25 artifacts/index/bm25
```

### Phase 2: RAG Pipeline & APIs
Core RAG components:
- **Query Transformation**: HyDE (Hypothetical Document Expansion)
- **Hybrid Retrieval**: FAISS (semantic) + BM25 (keyword) → RRF fusion
- **Reranking**: Cross-encoder for relevance scoring
- **Generation**: LLM with forced citations
- **Verification**: Chain-of-Verification (CoVe) for accuracy

### Phase 3: Evaluation & Demo UI
```bash
make demo               # Launch Streamlit demo UI
make eval               # Run full evaluation pipeline
make eval-retrieval     # Retrieval-only evaluation
make export-logs        # Export logs to CSV/JSON
make mine-hardcases     # Extract difficult cases for improvement
```

### Phase 4: Optimization & Production
```bash
make build              # Build production Docker image
make compose-up         # Start with docker-compose
make scan               # Security vulnerability scan
make sbom               # Generate Software Bill of Materials
make backup-index       # Backup search indices
make restore-index      # Restore from backup
make release            # Tag and release version
```

## Key Architecture Components

### Directory Structure (Planned)
```
app/
├── api/routers/           # FastAPI endpoints (ask.py, locate.py, report.py)
├── core/                  # Config, logging, LLM factory, caching
├── rag/                   # RAG pipeline components
│   ├── query_transform.py # Query preprocessing and HyDE
│   ├── retriever.py      # Hybrid search (FAISS + BM25)
│   ├── reranker.py       # Cross-encoder reranking
│   ├── generator.py      # Answer generation with citations
│   └── cove.py          # Chain-of-Verification
├── services/             # Business logic (locator, reporter)
└── deps/                # Dependency injection (indices, loaders)

data/
├── raw/                  # Input documents
├── staging/             # Processing intermediates
└── processed/           # Final Markdown + metadata

artifacts/
├── index/               # FAISS and BM25 search indices
└── eval/               # Evaluation reports and metrics

tools/                   # CLI utilities for ingestion, evaluation
```

### Technology Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Document Processing**: unstructured.io, PyMuPDF, pytesseract
- **Search**: FAISS (vector), BM25 (keyword), cross-encoder reranking  
- **LLM Integration**: OpenAI, Gemini (configurable)
- **Evaluation**: RAGAs framework, custom metrics
- **UI Demo**: Streamlit with PDF preview and citation highlighting
- **Monitoring**: Prometheus, OpenTelemetry, Grafana dashboards

## Development Workflow

### Setting Up Development Environment
```bash
# Clone and setup
git clone <repo>
cd Code-API_LLM_PVCFC
make dev                 # Creates venv and installs dependencies
cp .env.example .env     # Configure environment variables
make run                 # Start development server
```

### Environment Variables (Critical)
```env
APP_ENV=local|dev|prod
LLM_PROVIDER=openai|gemini|none
OPENAI_API_KEY=sk-...    # Required for OpenAI
GEMINI_API_KEY=...       # Required for Gemini
API_PORT=8000
LOG_LEVEL=INFO
```

### Core Development Commands
```bash
# Health check
curl http://localhost:8000/healthz

# Run specific phase operations
python tools/ingest.py --help        # Document ingestion
python tools/eval_retrieval.py       # Retrieval evaluation
python tools/eval_e2e.py            # End-to-end evaluation

# Testing
pytest tests/                        # Unit tests
pytest tests/test_health.py         # Health endpoint test
make smoke                          # LLM connectivity test
```

## API Endpoints

### POST /ask - Question Answering
Processes natural language questions and returns answers with citations.

**Request:**
```json
{
  "query": "Áp suất vận hành tối đa của KT06101?",
  "filters": {
    "doc_category": ["datasheet", "om"],
    "doc_id": ["PVCFC-KT06101-datasheet-v1"]
  },
  "hyde": true,
  "max_context": 8,
  "language": "vi"
}
```

**Response:**
```json
{
  "answer": "...(markdown with headers)...",
  "citations": [
    {"doc_id": "PVCFC-KT06101-datasheet-v1", "page": 12, "bbox": [100,220,380,270]}
  ],
  "context_used": ["chunk_id1", "chunk_id2"],
  "meta": {"latency_ms": 2300, "model": "gpt-*-*", "k": 8}
}
```

### POST /locate - Entity Location
Finds specific equipment tags or entities within technical drawings.

**Request:**
```json
{
  "query": "KT06101",
  "filters": {
    "doc_category": ["pid"],
    "doc_id": ["PVCFC-PID-04000-v1"]
  }
}
```

### POST /report - Multi-section Reports
Generates structured technical reports from multiple sub-queries.

## Testing Strategy

### Evaluation Metrics
- **Retrieval**: Recall@k, MRR@k, nDCG@k
- **Answer Quality**: Faithfulness, Context Precision/Recall (RAGAs)
- **Citations**: Citation precision ≥ 95%, recall ≥ 90%
- **Performance**: Latency p50/p95, token usage, cost analysis

### Quality Thresholds
- Retrieval Recall@5 ≥ 70% (datasheets/SOPs), Recall@10 ≥ 80% overall
- Answer Faithfulness ≥ 0.8
- Citation precision ≥ 95%, recall ≥ 90%
- End-to-end latency p95 < 8s

### Golden Dataset Requirements
Minimum 120 QA pairs covering:
- **Document types**: P&ID, datasheet, SOP, OM (≥25-30 questions each)
- **Query types**: parameter lookup, entity location, procedures, safety, negative cases
- **Languages**: Primarily Vietnamese with 10-20% English for robustness
- **Difficulty**: Easy/Medium/Hard (roughly 1/3 each)

## Specialized Features

### Document Processing Pipeline
1. **Format Detection**: Automatically identifies vector vs scanned PDFs
2. **Multi-modal Parsing**: PyMuPDF for vector, unstructured.io + OCR for scanned
3. **Table Extraction**: Preserves technical specifications and parameter tables
4. **Tag Normalization**: Standardizes equipment tags (KT06101, line numbers)
5. **Unit Conversion**: Normalizes engineering units (bar↔MPa, °C↔K)

### RAG Pipeline Optimizations
- **HyDE**: Generates hypothetical documents to bridge semantic gaps
- **Hierarchical Chunking**: Small-to-big strategy with parent expansion
- **RRF Fusion**: Combines semantic and keyword search results
- **Cross-encoder Reranking**: Final relevance scoring before generation
- **Forced Citations**: Ensures all answers are source-grounded

### Operational Monitoring
```bash
# View system health
curl http://localhost:8000/healthz

# Check metrics (when Prometheus is running)  
curl http://localhost:9090/metrics

# View application logs
tail -f logs/requests.jsonl
```

## Security Considerations

- **Secrets Management**: Never commit API keys; use environment variables or secret managers
- **Input Validation**: All API inputs validated via Pydantic schemas
- **Rate Limiting**: 60 requests/minute with burst capacity
- **Container Security**: Non-root user, read-only filesystem, minimal attack surface
- **Data Privacy**: PII detection and masking in logs; retention policies

## Production Deployment

### Docker Operations
```bash
# Build production image
make build

# Run with docker-compose (includes Redis, monitoring)
make compose-up

# Security scanning
make scan    # Vulnerability assessment
make sbom    # Generate software bill of materials
```

### Backup and Recovery
```bash
# Backup search indices and manifests
make backup-index

# Restore from backup
make restore-index

# Verify system after restore
make smoke
```

## Troubleshooting Common Issues

### LLM Connection Issues
- Verify API keys are properly set in environment
- Check `make smoke` for connectivity
- Review rate limits and quotas

### Document Processing Failures
- Ensure Tesseract is installed for OCR functionality
- Check file permissions for `data/raw/` directory
- Verify PDF formats are supported

### Search Index Problems
- Rebuild indices: `make clean-processed && make build-index`
- Check FAISS index integrity and BM25 corpus consistency
- Verify document chunking parameters

### Performance Issues
- Monitor cache hit rates (should be ≥30% for repeated queries)
- Check memory usage during index loading
- Review query complexity and context window sizes

---

**Important Notes:**
- This system is designed for Vietnamese and English technical documentation
- All answers must include source citations for auditability
- The system refuses to answer when insufficient evidence is available
- Regular evaluation against golden datasets is critical for maintaining quality
