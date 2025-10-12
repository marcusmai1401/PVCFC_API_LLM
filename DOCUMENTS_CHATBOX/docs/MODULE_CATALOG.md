# MODULE CATALOG - PVCFC RAG SYSTEM

**Version**: 1.0.0
**Date**: 2025-10-12
**Purpose**: Chi tiết catalog của tất cả modules, classes, và functions

---

## 📋 MỤC LỤC

1. [API Layer (`app/api/`)](#1-api-layer-appapi)
2. [RAG Pipeline (`app/rag/`)](#2-rag-pipeline-apprag)
3. [Services (`app/services/`)](#3-services-appservices)
4. [Ingestion (`app/ingestion/`)](#4-ingestion-appingestion)
5. [Storage (`app/storage/`)](#5-storage-appstorage)
6. [Core (`app/core/`)](#6-core-appcore)
7. [Utils (`app/utils/`)](#7-utils-apputils)
8. [Tools (`tools/`)](#8-tools-tools)
9. [Scripts (`scripts/`)](#9-scripts-scripts)

---

## 1. API LAYER (`app/api/`)

### 1.1 Routers

#### `app/api/routers/ask.py`

**Purpose**: Handle Q&A requests với RAG pipeline

**Endpoints**:
- `POST /api/ask` - Main Q&A endpoint

**Key Functions**:
```python
async def ask_endpoint(
    request: AskRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings)
) -> AskResponse:
    """
    Process Q&A request with full RAG pipeline

    Flow:
    1. Transform query
    2. Hybrid retrieval
    3. Optional BGE reranking
    4. Generation (text or vision)
    5. Citation extraction & validation
    6. Response building

    Args:
        request: AskRequest with query, language, max_context, enable_vision
        retriever: Injected retriever instance
        settings: Injected settings

    Returns:
        AskResponse with answer, citations, confidence, metadata
    """
```

**Request Schema**:
```python
class AskRequest(BaseModel):
    query: str
    language: str = "vi"  # vi|en
    max_context: int = 8  # Max chunks to use
    enable_vision_generation: bool = False
    filters: Optional[Dict] = None  # equipment_id, doc_type, etc.
```

**Response Schema**:
```python
class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: float  # [0, 1]
    meta: ResponseMetadata
    warnings: Optional[List[str]]
```

---

#### `app/api/routers/locate.py`

**Purpose**: Document & page location

**Endpoints**:
- `POST /api/locate` - Find documents containing specific content

**Key Functions**:
```python
async def locate_endpoint(
    request: LocateRequest,
    retriever: HybridRetriever = Depends(get_retriever)
) -> LocateResponse:
    """
    Locate documents and pages containing query

    Returns:
    - List of matching documents
    - Page numbers where content appears
    - Relevance scores
    """
```

---

#### `app/api/routers/report.py`

**Purpose**: Generate formatted reports

**Endpoints**:
- `POST /api/report` - Generate report from query + answer

**Key Functions**:
```python
async def report_endpoint(
    request: ReportRequest,
    reporter: ReportService = Depends(get_reporter)
) -> ReportResponse:
    """
    Generate formatted report (Markdown/Docx)

    Includes:
    - Query
    - Answer
    - Citations with full references
    - Metadata (timestamp, trace_id)
    """
```

---

#### `app/api/routers/health.py`

**Purpose**: Health checks & system status

**Endpoints**:
- `GET /healthz` - Basic health check
- `GET /health/detailed` - Detailed health with component status

**Key Functions**:
```python
async def health_check() -> HealthResponse:
    """
    Check system health

    Returns:
    - status: healthy|degraded|unhealthy
    - components: LLM, retriever, indices
    - timestamp
    """
```

---

#### `app/api/routers/config.py`

**Purpose**: Runtime configuration management

**Endpoints**:
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration (admin)

---

#### `app/api/endpoints/pdf_renderer.py`

**Purpose**: PDF page rendering

**Endpoints**:
- `GET /api/pdf/open` - Open PDF at specific page in browser
- `GET /api/pdf/render` - Render PDF page as image

**Key Functions**:
```python
async def render_pdf_page(
    pdf_path: str,
    page: int,
    dpi: int = 200
) -> Response:
    """
    Render PDF page to JPEG

    Args:
        pdf_path: Path to PDF file
        page: Page number (1-based)
        dpi: Resolution (default 200)

    Returns:
        JPEG image response
    """
```

---

## 2. RAG PIPELINE (`app/rag/`)

### 2.1 Retrieval

#### `app/rag/hybrid_weaviate_opensearch_retriever.py`

**Purpose**: Modern Hybrid retrieval (Phase 5)

**Key Classes**:
```python
class HybridWeaviateOpenSearchRetriever:
    """
    Modern Hybrid retriever with Weaviate + OpenSearch

    Features:
    - Parallel retrieval from Weaviate (semantic) and OpenSearch (BM25)
    - RRF fusion (Reciprocal Rank Fusion)
    - Health checks with graceful degradation
    - Optional BGE CrossEncoder reranking
    """

    def __init__(
        self,
        weaviate_client: WeaviateClient,
        opensearch_client: OpenSearch,
        embedding_service: EmbeddingService,
        config: RetrieverConfig
    ):
        """Initialize retriever with backends"""

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 50,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """
        Parallel hybrid search with RRF fusion

        Process:
        1. Parallel: Weaviate search + OpenSearch search
        2. RRF fusion: Merge and rank results
        3. Optional: BGE reranking
        4. Return top-k results

        Graceful degradation:
        - If Weaviate fails → use OpenSearch only
        - If OpenSearch fails → use Weaviate only
        - If both fail → raise error
        """

    def check_health(self) -> Dict:
        """
        Check health of both backends

        Returns:
        - overall_status: healthy|degraded|critical
        - weaviate_status: healthy|unhealthy
        - opensearch_status: healthy|unhealthy
        - details: error messages if any
        """
```

**RRF Fusion Algorithm**:
```python
def reciprocal_rank_fusion(
    results_a: List[Result],
    results_b: List[Result],
    k: int = 60
) -> List[Result]:
    """
    RRF formula: score(d) = Σ (1 / (k + rank_i(d)))

    Args:
        results_a: Results from retriever A (e.g., Weaviate)
        results_b: Results from retriever B (e.g., OpenSearch)
        k: RRF constant (default 60)

    Returns:
        Merged and ranked results
    """
```

---

#### `app/rag/weaviate_retriever.py`

**Purpose**: Weaviate-only retriever (Phase 4)

**Key Classes**:
```python
class WeaviateRetriever:
    """
    Weaviate vector database retriever

    Features:
    - gRPC support for high performance
    - Auto-detection of embedding dimension
    - Batch query support
    - Filter support (doc_id, page, metadata)
    """

    def search(
        self,
        query: str,
        limit: int = 50,
        where_filter: Optional[Dict] = None
    ) -> List[SearchResult]:
        """
        Semantic search in Weaviate

        Process:
        1. Embed query → 768D vector
        2. near_vector search with optional filters
        3. Convert distance → similarity score
        4. Return results with metadata
        """
```

---

#### `app/rag/retriever.py`

**Purpose**: Legacy Hybrid retriever (FAISS + BM25)

**Key Classes**:
```python
class HybridRetriever:
    """
    Legacy hybrid retriever with FAISS + offline BM25

    Use case: Fallback mode, offline development
    """
```

---

### 2.2 Reranking

#### `app/rag/reranker.py`

**Purpose**: BGE CrossEncoder reranking

**Key Classes**:
```python
class BGEReranker:
    """
    BGE CrossEncoder reranker (BAAI/bge-reranker-base)

    Features:
    - Multi-level reranking: chunk, document, page
    - Aggregation methods: max, mean, top3_mean
    - Graceful fallback to score-based ranking
    """

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 10,
        level: str = "chunk",
        aggregation: str = "max"
    ) -> List[SearchResult]:
        """
        Rerank search results using CrossEncoder

        Args:
            query: User query
            results: Search results to rerank
            top_k: Number of results to return
            level: Reranking level (chunk|doc|page)
            aggregation: Score aggregation method

        Returns:
            Reranked results sorted by relevance
        """
```

**Reranking Levels**:
- **chunk**: Rerank individual chunks (default)
- **doc**: Aggregate chunk scores per document
- **page**: Aggregate chunk scores per page

**Aggregation Methods**:
- **max**: Take maximum score across chunks
- **mean**: Average score across chunks
- **top3_mean**: Average of top 3 chunk scores

---

### 2.3 Generation

#### `app/rag/generator.py`

**Purpose**: Answer generation with LLM

**Key Classes**:
```python
class Generator:
    """
    Answer generator with text and vision support

    Features:
    - Strategy selection (text vs vision)
    - Citation extraction from LLM response
    - Post-validation with CiteFix-lite
    - Confidence calculation
    """

    def generate(
        self,
        query: str,
        retrieved_docs: List[SearchResult],
        enable_vision: bool = False
    ) -> GenerationResult:
        """
        Generate answer with citations

        Process:
        1. Select strategy (text or vision)
        2. Build prompt with context
        3. Call LLM (Gemini Pro/Flash)
        4. Extract citations from response
        5. Validate citations (CiteFix-lite)
        6. Calculate confidence

        Returns:
            GenerationResult with answer, citations, metadata
        """

    def _text_generation(
        self,
        query: str,
        context: str
    ) -> Tuple[str, List[Citation]]:
        """
        Text-only generation with Gemini Flash

        Prompt format:
        Based on the following context documents, answer the question.

        Context:
        [Doc 1] {text}
        [Doc 2] {text}
        ...

        Question: {query}

        Instructions:
        - Provide a concise, accurate answer
        - Include citations in format: [Doc N, p.X]
        - Only use information from the provided context

        Answer:
        """

    def _vision_generation(
        self,
        query: str,
        retrieved_docs: List[SearchResult],
        doc_id_map: Dict
    ) -> Tuple[str, List[Citation]]:
        """
        Vision generation with Gemini 2.5 Pro

        Process:
        1. Select pages to render (max 10)
        2. Render PDF pages → JPEG @ DPI=200
        3. Build multimodal prompt (text + images)
        4. Call Gemini Vision API
        5. Extract citations

        Page selection:
        - If page_start & page_end: full range (clamped to max 10)
        - If page only: ±2 window (page-2 to page+2)
        - Clamp to [1, total_pages]
        - Deduplicate by (pdf_path, page)
        """
```

---

### 2.4 Citation Handling

#### `app/rag/citation_retriever.py`

**Purpose**: Extract and rank citations

**Key Classes**:
```python
class CitationRetriever:
    """
    Citation extraction and ranking

    Features:
    - Extract citations from LLM response
    - Rank by relevance
    - Enrich with metadata (pdf_path, snippets)
    - Optional CiteFix-lite validation
    """

    def extract_citations(
        self,
        answer: str,
        doc_mapping: Dict[int, SearchResult]
    ) -> List[Citation]:
        """
        Extract citations from answer text

        Pattern: [Doc X, p.Y] or [Doc X, pp.Y-Z]

        Returns:
            List of Citation objects with doc_id, page, pdf_path
        """
```

---

#### `app/rag/citation_validator.py`

**Purpose**: CiteFix-lite validation

**Key Classes**:
```python
class CitationValidator:
    """
    CiteFix-lite: Citation validation to prevent hallucinations

    Validation Levels:
    - Level 1: Basic (doc_exists + page_valid) - ~1-5ms
    - Level 2: Full (+ text verification + snippets) - ~10-30ms
    - Level 3: Semantic (+ NLI entailment) - ~100-500ms (future)
    """

    def validate(
        self,
        citation: Citation,
        query: str,
        context_docs: List[SearchResult],
        validation_level: int = 2
    ) -> ValidationResult:
        """
        Validate citation

        Checks:
        1. Document exists in corpus
        2. Page number is valid (within total_pages)
        3. Text on page matches cited text
        4. Snippets found on page
        5. (Level 3) Semantic entailment

        Returns:
            ValidationResult with:
            - is_valid: bool
            - confidence: float [0, 1]
            - errors: List[ValidationError]
            - suggested_page: Optional[int] (if neighbor page better)
        """
```

**Validation Result Schema**:
```python
class ValidationResult:
    is_valid: bool
    confidence: float  # [0, 1]
    errors: List[ValidationError]
    checks: Dict[str, Any]  # Detailed check results
    metadata: Dict[str, Any]  # Additional info
    suggested_page: Optional[int]  # Better page if found
```

---

### 2.5 Query Processing

#### `app/rag/query_transform.py`

**Purpose**: Query preprocessing and transformation

**Key Classes**:
```python
class QueryTransformer:
    """
    Query transformation pipeline

    Features:
    - Normalization (lowercase, whitespace)
    - Intent detection (ASK|LOCATE|EXPLAIN|REPORT)
    - Filter extraction (equipment_id, doc_type)
    - Query expansion (optional)
    - HyDE (Hypothetical Document Embeddings)
    """

    def transform(
        self,
        query: str,
        enable_hyde: bool = False
    ) -> TransformedQuery:
        """
        Transform query

        Process:
        1. Normalize text
        2. Detect intent
        3. Extract filters (regex patterns)
        4. Optional: HyDE expansion

        Returns:
            TransformedQuery with:
            - normalized: str
            - intent: QueryIntent
            - filters: Dict[str, Any]
            - hyde_queries: List[str]
        """
```

**Intent Types**:
```python
class QueryIntent(Enum):
    ASK = "ask"              # Question-answering
    LOCATE = "locate"        # Document search
    EXPLAIN = "explain"      # Detailed explanation
    REPORT = "report"        # Generate report
    UNKNOWN = "unknown"      # Fallback
```

---

#### `app/rag/hyde.py`

**Purpose**: HyDE (Hypothetical Document Embeddings)

**Key Classes**:
```python
class HyDEGenerator:
    """
    Generate hypothetical documents for query expansion

    Concept: Generate a document that would answer the query,
             then use that document for retrieval
    """

    def generate_hypothetical_doc(
        self,
        query: str,
        num_docs: int = 1
    ) -> List[str]:
        """
        Generate hypothetical documents

        Prompt:
        Write a technical document paragraph that would answer: {query}

        Returns:
            List of hypothetical document texts
        """
```

---

## 3. SERVICES (`app/services/`)

### 3.1 LLM Service

#### `app/services/llm_client.py`

**Purpose**: LLM API client (Gemini/OpenAI)

**Key Classes**:
```python
class LLMClient:
    """
    Unified LLM client supporting multiple providers

    Providers:
    - Gemini (gemini-2.5-pro, gemini-2.5-flash)
    - OpenAI (gpt-4o, gpt-4o-mini) - optional
    """

    def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        images: Optional[List[bytes]] = None
    ) -> LLMResponse:
        """
        Generate response from LLM

        Args:
            prompt: Text prompt
            model: Model name
            temperature: Sampling temperature [0, 2]
            max_tokens: Max output tokens
            images: Optional images for vision models

        Returns:
            LLMResponse with text, model, finish_reason
        """
```

**Response Schema**:
```python
class LLMResponse:
    text: str
    model: str
    finish_reason: str  # stop|length|content_filter
    usage: TokenUsage
    latency_ms: float
```

---

### 3.2 Embedding Service

#### `app/services/embedding.py`

**Purpose**: Text embedding service

**Key Classes**:
```python
class EmbeddingService:
    """
    Embedding service with batch processing

    Providers:
    - Gemini (gemini-embedding-001, 768D)
    - OpenAI (text-embedding-3-small, 1536D)
    - Local (sentence-transformers)
    """

    def embed_texts(
        self,
        texts: List[str],
        task_type: str = "retrieval_document",
        batch_size: int = 256
    ) -> List[np.ndarray]:
        """
        Embed texts in batches

        Args:
            texts: List of texts to embed
            task_type: Embedding task type
            batch_size: Batch size for API calls

        Returns:
            List of embedding vectors (768D or 1536D)

        Performance:
        - Batching: 256 texts per API call
        - Concurrency: 8 concurrent requests
        - Rate limiting: 10 requests/second
        - Caching: LRU cache for query embeddings
        """
```

---

## 4. INGESTION (`app/ingestion/`)

### 4.1 PDF Processing

#### `app/ingestion/pdf_processor.py`

**Purpose**: PDF parsing and text extraction

**Key Classes**:
```python
class PDFProcessor:
    """
    PDF processing with OCR fallback

    Features:
    - Vector text extraction (PyMuPDF)
    - OCR fallback (Tesseract/PaddleOCR)
    - Table extraction (pdfplumber)
    - Metadata extraction
    """

    def process_pdf(
        self,
        pdf_path: str,
        enable_ocr: bool = True,
        extract_tables: bool = True
    ) -> ProcessedDocument:
        """
        Process PDF document

        Process:
        1. Try vector text extraction (PyMuPDF)
        2. If no text: OCR with Tesseract/PaddleOCR
        3. Extract tables (pdfplumber)
        4. Extract metadata (equipment_id, doc_type)
        5. Generate doc_id (SHA256)

        Returns:
            ProcessedDocument with:
            - doc_id: str
            - text: str
            - tables: List[Table]
            - metadata: Dict
            - source_format: "vector"|"scan"
        """
```

---

### 4.2 Chunking

#### `app/ingestion/chunkers/text_chunker.py`

**Purpose**: Text chunking strategies

**Key Classes**:
```python
class TextChunker:
    """
    Character-based text chunking

    Strategy: Fixed size with overlap
    """

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        page_breaks: Optional[List[int]] = None
    ) -> List[Chunk]:
        """
        Chunk text with page tracking

        Args:
            text: Full document text
            doc_id: Document ID
            chunk_size: Characters per chunk
            chunk_overlap: Overlap between chunks
            page_breaks: Character positions of page breaks

        Returns:
            List of Chunk objects with:
            - chunk_id: str
            - text: str
            - doc_id: str
            - page: Optional[int]
            - page_start: Optional[int]
            - page_end: Optional[int]
            - metadata: Dict
        """
```

---

### 4.3 Deduplication

#### `app/ingestion/dedup.py`

**Purpose**: Content deduplication

**Key Functions**:
```python
def deduplicate_chunks(
    chunks: List[Chunk]
) -> List[Chunk]:
    """
    Deduplicate chunks by content_hash

    Algorithm:
    1. Group chunks by content_hash (SHA1 of normalized text)
    2. For each group, select best representative:
       Priority: vector > scan > newer > shorter_path
    3. Return deduplicated chunks

    Benefits:
    - Reduce index size
    - Faster retrieval
    - No duplicate results
    """
```

---

## 5. STORAGE (`app/storage/`)

### 5.1 Version Management

#### `app/storage/version_manager.py`

**Purpose**: Version control for ingestion artifacts

**Key Classes**:
```python
class VersionManager:
    """
    Version control system for RAG artifacts

    Features:
    - Create version snapshots
    - List versions with metadata
    - Compare versions (diffs)
    - Rollback to previous versions
    - Version lineage tracking
    """

    def create_version(
        self,
        version_id: str,
        description: str,
        artifacts: Dict[str, str],
        tags: List[str] = []
    ) -> Version:
        """
        Create version snapshot

        Args:
            version_id: Unique version identifier
            description: Human-readable description
            artifacts: Dict of artifact paths
            tags: Version tags (e.g., "production", "test")

        Process:
        1. Copy artifacts to version directory
        2. Generate manifest with metadata
        3. Update version history
        4. Mark as current version

        Returns:
            Version object
        """

    def compare_versions(
        self,
        version_a: str,
        version_b: str
    ) -> VersionDiff:
        """
        Compare two versions

        Returns:
            VersionDiff with:
            - added_docs: List[str]
            - removed_docs: List[str]
            - modified_docs: List[str]
            - chunk_count_diff: int
        """
```

---

## 6. CORE (`app/core/`)

### 6.1 Configuration

#### `app/core/config.py`

**Purpose**: Application configuration

**Key Classes**:
```python
class Settings(BaseSettings):
    """
    Application settings from environment variables

    Categories:
    - App: APP_ENV, API_PORT, LOG_LEVEL
    - LLM: LLM_PROVIDER, LLM_MODEL_HEAVY, LLM_MODEL_LIGHT
    - Embedding: EMBEDDING_PROVIDER, EMBEDDING_MODEL
    - Retrieval: USE_HYBRID_MODERN, WEAVIATE_*, OPENSEARCH_*
    - Reranking: ENABLE_BGE_RERANK, BGE_*
    - Vision: VISION_MODEL, VISION_MAX_PAGES_TOTAL, PDF_RENDER_DPI
    """
```

---

### 6.2 Logging

#### `app/core/logging.py`

**Purpose**: Structured logging with Loguru

**Key Functions**:
```python
def setup_logging(
    level: str = "INFO",
    log_dir: str = "artifacts/logs"
):
    """
    Setup Loguru logging

    Features:
    - JSON structured logs
    - Rotation: 100MB per file
    - Retention: 30 days
    - Backtrace for errors
    - Colorized console output
    """
```

---

### 6.3 Metrics

#### `app/core/metrics.py`

**Purpose**: Prometheus metrics

**Key Metrics**:
```python
# Query metrics
rag_query_total = Counter(...)
rag_query_latency_seconds = Histogram(...)
rag_query_confidence = Histogram(...)

# Retrieval metrics
rag_retrieval_latency_seconds = Histogram(...)
rag_retrieval_results_count = Histogram(...)

# Generation metrics
rag_generation_latency_seconds = Histogram(...)
rag_generation_tokens = Histogram(...)
```

---

## 7. UTILS (`app/utils/`)

### 7.1 Text Processing

#### `app/utils/text_utils.py`

**Key Functions**:
```python
def normalize_text(text: str) -> str:
    """Normalize text for deduplication"""

def extract_equipment_id(text: str) -> Optional[str]:
    """Extract equipment ID using regex: \bKT?\d{5}\b"""

def infer_doc_type(path: str, text: str) -> Optional[str]:
    """Infer document type from path and content"""
```

---

### 7.2 Page Utils

#### `app/utils/page_utils.py`

**Key Functions**:
```python
def calculate_page_from_position(
    position: int,
    page_breaks: List[int]
) -> int:
    """Calculate page number from character position"""

def get_page_range(
    page: int,
    window: int = 2,
    total_pages: Optional[int] = None
) -> Tuple[int, int]:
    """Get page range: [page - window, page + window]"""
```

---

## 8. TOOLS (`tools/`)

### 8.1 Ingestion Tool

#### `tools/ingest.py`

**Purpose**: Main ingestion pipeline

**Usage**:
```bash
python tools/ingest.py \
  --source-dir D:\Data_Raw \
  --output-dir artifacts/ingestion_production \
  --workers 4 \
  --enable-ocr --ocr-lang "vie+eng" \
  --extract-tables \
  --create-version \
  --version-id v1.0 \
  --version-description "Production baseline"
```

**Key Arguments**:
- `--source-dir`: Source directory (recursive scan)
- `--output-dir`: Output directory for artifacts
- `--workers`: Number of parallel workers
- `--enable-ocr`: Enable OCR for scanned PDFs
- `--ocr-lang`: OCR language(s)
- `--extract-tables`: Extract tables from PDFs
- `--chunk-size`: Chunk size (default 1000)
- `--chunk-overlap`: Chunk overlap (default 200)
- `--create-version`: Create version snapshot after ingestion
- `--version-id`: Version identifier
- `--version-description`: Version description
- `--version-tags`: Version tags (space-separated)

---

### 8.2 Build Production Indices

#### `tools/ops/build_production_indices.py`

**Purpose**: Build BM25 and FAISS indices

**Usage**:
```bash
python tools/ops/build_production_indices.py
```

**Process**:
1. Load chunks from `artifacts/ingestion_production/chunks.jsonl`
2. Build BM25 index → `artifacts/index_production/bm25/`
3. Embed chunks → Build FAISS index → `artifacts/index_production/faiss/`

---

### 8.3 Production Ingestion

#### `tools/ops/run_production_ingest.py`

**Purpose**: Run production ingestion with versioning

**Usage**:
```bash
python tools/ops/run_production_ingest.py
```

**Features**:
- Automatic versioning with `production_baseline` version ID
- Progress tracking
- Error handling
- Post-ingestion validation

---

## 9. SCRIPTS (`scripts/`)

### 9.1 Weaviate Scripts

#### `scripts/phase1_index_to_weaviate.py`

**Purpose**: Ingest chunks to Weaviate

**Usage**:
```bash
python scripts/phase1_index_to_weaviate.py
```

---

#### `scripts/weaviate/test_weaviate_search.py`

**Purpose**: Test Weaviate search

**Usage**:
```bash
python scripts/weaviate/test_weaviate_search.py "CO2 compressor"
```

---

### 9.2 OpenSearch Scripts

#### `scripts/opensearch/create_rag_chunks_index.py`

**Purpose**: Create OpenSearch index

---

#### `scripts/opensearch/bulk_insert_to_opensearch.py`

**Purpose**: Bulk insert chunks to OpenSearch

---

#### `scripts/opensearch/test_opensearch_search.py`

**Purpose**: Test OpenSearch BM25 search

---

### 9.3 Diagnostic Scripts

#### `scripts/diagnostics/deep_diagnostic.py`

**Purpose**: Deep diagnostic for retrieval

**Usage**:
```bash
python scripts/diagnostics/deep_diagnostic.py --query "K06101"
```

---

#### `scripts/diagnostics/check_pdf_pages.py`

**Purpose**: Check PDF page count and structure

---

## 📚 RELATED DOCUMENTATION

- [PROJECT_MASTERY_GUIDE.md](PROJECT_MASTERY_GUIDE.md) - Comprehensive project guide
- [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) - Visual architecture diagrams
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) - Detailed architecture description

---

**Last Updated**: 2025-10-12
**Version**: 1.0.0
**Status**: ✅ Complete
