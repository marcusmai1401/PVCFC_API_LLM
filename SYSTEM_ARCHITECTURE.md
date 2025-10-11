# SYSTEM ARCHITECTURE - PVCFC RAG SYSTEM

**Version**: 0.6.1
**Last Updated**: 2025-10-11
**Document**: Complete Pipeline & Architecture Description

---

## 📋 MỤC LỤC

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Data Flow - Luồng dữ liệu hoàn chỉnh](#2-data-flow---luồng-dữ-liệu-hoàn-chỉnh)
3. [Phase 1: Document Ingestion](#3-phase-1-document-ingestion)
4. [Phase 2: Indexing & Storage](#4-phase-2-indexing--storage)
5. [Phase 3: Query Processing](#5-phase-3-query-processing)
6. [Phase 4: Hybrid Retrieval](#6-phase-4-hybrid-retrieval)
7. [Phase 5: Reranking](#7-phase-5-reranking)
8. [Phase 6: Answer Generation](#8-phase-6-answer-generation)
9. [Phase 7: Response Building](#9-phase-7-response-building)
10. [Components Deep Dive](#10-components-deep-dive)
11. [Error Handling & Resilience](#11-error-handling--resilience)
12. [Performance & Optimization](#12-performance--optimization)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Mục tiêu

Hệ thống RAG (Retrieval-Augmented Generation) phục vụ tra cứu, trích xuất và hỏi-đáp kỹ thuật trên tài liệu PVCFC với:
- ✅ **Độ tin cậy cao**: Citations có doc_id + page number
- ✅ **Multimodal**: Hỗ trợ cả text và vision (PDF pages)
- ✅ **Production-ready**: Weaviate + OpenSearch, defensive programming
- ✅ **Scalable**: Xử lý hàng nghìn tài liệu, hỗ trợ mở rộng

### 1.2 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI + Python 3.11 | API server |
| **Vector DB** | Weaviate (gRPC) | Semantic search |
| **Keyword Search** | OpenSearch (BM25) | Keyword search |
| **LLM** | Gemini 2.5 Pro/Flash | Generation |
| **Embedding** | Gemini Embedding 001 (768D) | Text vectorization |
| **Reranker** | BGE CrossEncoder | Result reranking |
| **OCR** | Tesseract (vie+eng) | Scanned PDF processing |
| **UI** | Streamlit | Testing & debugging |
| **Monitoring** | Loguru + Metrics | Logging & observability |

### 1.3 Architecture Diagram

```
┌─────────────┐
│  Documents  │  (PDF files in D:\Data_Raw)
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────────────────────────────┐
│              OFFLINE PIPELINE (Build Time)              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌────────────┐    ┌──────────┐    ┌──────────────┐   │
│  │  Ingest    │ →  │  Chunk   │ →  │   Dedup      │   │
│  │  (OCR)     │    │          │    │  (content)   │   │
│  └────────────┘    └──────────┘    └──────────────┘   │
│         │                                    │          │
│         ↓                                    ↓          │
│  ┌────────────┐                   ┌──────────────┐    │
│  │doc_id_map  │                   │  chunks.jsonl│    │
│  │   .json    │                   │              │    │
│  └────────────┘                   └──────┬───────┘    │
│                                           │            │
│                    ┌──────────────────────┴────────┐  │
│                    ↓                               ↓  │
│         ┌────────────────┐              ┌────────────────┐
│         │  Weaviate DB   │              │  OpenSearch    │
│         │  (Vector 768D) │              │  (BM25 Index)  │
│         └────────────────┘              └────────────────┘
│                                                         │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│               ONLINE PIPELINE (Query Time)              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐                                          │
│  │  Query   │  "What is K06101 max pressure?"          │
│  └────┬─────┘                                          │
│       │                                                 │
│       ↓                                                 │
│  ┌─────────────────┐                                   │
│  │ Query Transform │  (Normalize, intent, HyDE)        │
│  └────────┬────────┘                                   │
│           │                                             │
│           ↓                                             │
│  ┌─────────────────────────────────────┐              │
│  │    HYBRID RETRIEVAL (Parallel)      │              │
│  │  ┌──────────┐      ┌──────────┐    │              │
│  │  │ Weaviate │      │OpenSearch│    │              │
│  │  │(Semantic)│      │  (BM25)  │    │              │
│  │  └────┬─────┘      └────┬─────┘    │              │
│  │       │                 │           │              │
│  │       └────────┬────────┘           │              │
│  │                ↓                    │              │
│  │         ┌─────────────┐             │              │
│  │         │  RRF Fusion │             │              │
│  │         └──────┬──────┘             │              │
│  └────────────────┼────────────────────┘              │
│                   ↓                                    │
│  ┌─────────────────────────────┐                      │
│  │  BGE CrossEncoder Rerank    │  (Optional)          │
│  └──────────────┬──────────────┘                      │
│                 ↓                                      │
│  ┌────────────────────────────┐                       │
│  │  Top-K Reranked Results    │  (k=8 default)        │
│  └──────────────┬─────────────┘                       │
│                 │                                      │
│                 ↓                                      │
│  ┌─────────────────────────────────────┐             │
│  │        GENERATION PIPELINE          │             │
│  │                                     │             │
│  │  ┌────────────────────────────┐    │             │
│  │  │  Strategy: Text or Vision? │    │             │
│  │  └────────┬──────────┬────────┘    │             │
│  │           │          │              │             │
│  │      Text │          │ Vision       │             │
│  │           ↓          ↓              │             │
│  │  ┌─────────────┐  ┌──────────────┐ │             │
│  │  │  Gemini     │  │ Gemini 2.5   │ │             │
│  │  │  2.5 Flash  │  │ Pro (Vision) │ │             │
│  │  │  (Text)     │  │ + PDF Pages  │ │             │
│  │  └──────┬──────┘  └──────┬───────┘ │             │
│  │         │                │          │             │
│  │         └────────┬───────┘          │             │
│  │                  ↓                  │             │
│  │        ┌──────────────────┐         │             │
│  │        │ Answer + Citation│         │             │
│  │        │  Extraction      │         │             │
│  │        └────────┬─────────┘         │             │
│  │                 ↓                   │             │
│  │        ┌──────────────────┐         │             │
│  │        │ Post-validation  │         │             │
│  │        │  (CiteFix-lite)  │         │             │
│  │        └────────┬─────────┘         │             │
│  │                 ↓                   │             │
│  │        ┌──────────────────┐         │             │
│  │        │ Confidence Score │         │             │
│  │        │  Calculation     │         │             │
│  │        └────────┬─────────┘         │             │
│  └─────────────────┼─────────────────────┘             │
│                    ↓                                   │
│  ┌─────────────────────────────────┐                  │
│  │     BUILD API RESPONSE          │                  │
│  │  • Answer text                  │                  │
│  │  • Citations (doc_id + page)    │                  │
│  │  • Confidence [0,1]             │                  │
│  │  • Metadata                     │                  │
│  │  • Timing breakdown             │                  │
│  └─────────────────┬───────────────┘                  │
│                    │                                   │
└────────────────────┼───────────────────────────────────┘
                     ↓
              ┌──────────────┐
              │  JSON Response│
              └──────────────┘
```

---

## 2. DATA FLOW - LUỒNG DỮ LIỆU HOÀN CHỈNH

### 2.1 Build Time (Offline)

```
RAW PDF FILES
    ↓
[1] INGESTION
    • Parse PDF (PyMuPDF)
    • OCR if needed (Tesseract)
    • Extract text + metadata
    ↓
[2] CHUNKING
    • Split by size (1000 chars, overlap 200)
    • Keep page metadata
    ↓
[3] DEDUPLICATION
    • content_hash = SHA1(normalized_text)
    • Keep 1 representative per hash
    ↓
[4] INDEXING
    ├── Weaviate: Vector embeddings (768D)
    └── OpenSearch: BM25 inverted index
    ↓
OUTPUT:
    • chunks.jsonl (deduplicated chunks)
    • doc_id_map.json (doc_id → pdf_path mapping)
    • Weaviate collection (vectors)
    • OpenSearch index (keywords)
```

### 2.2 Query Time (Online)

```
USER QUERY: "What is K06101 max pressure?"
    ↓
[1] QUERY TRANSFORM
    • Normalize: lowercase, spaces
    • Intent detection: ASK|LOCATE|EXPLAIN|REPORT
    • Extract filters: equipment_id, doc_type
    • HyDE: Generate hypothetical document (optional)
    ↓
[2] HYBRID RETRIEVAL (Parallel)
    ├── Weaviate Search
    │   • Embed query → 768D vector
    │   • near_vector search
    │   • Top 50 results
    │
    └── OpenSearch BM25
        • Tokenize query
        • BM25 scoring (k1=1.2, b=0.75)
        • Top 50 results
    ↓
[3] RRF FUSION
    • Reciprocal Rank Fusion
    • Merge scores from both sources
    • Combined ranking
    ↓
[4] BGE RERANKING (Optional)
    • CrossEncoder score each (query, doc) pair
    • Re-sort by semantic relevance
    • Top-k selection (k=8)
    ↓
[5] GENERATION
    ├── Strategy Decision
    │   • Has PDF pages? → Vision
    │   • Text only? → Text
    │
    ├── Vision Generation (if applicable)
    │   • Render PDF pages to JPEG (DPI=200)
    │   • Send to Gemini 2.5 Pro (multimodal)
    │   • Extract answer + citations
    │
    └── Text Generation (fallback)
        • Context = concatenated chunks
        • Send to Gemini 2.5 Flash/Pro
        • Extract answer + citations
    ↓
[6] POST-PROCESSING
    • Citation validation (CiteFix-lite)
    • Confidence calculation
    • IEEE-style conversion (optional)
    ↓
[7] RESPONSE BUILDING
    • Answer text
    • Citations: [{doc_id, page, pdf_path, confidence}]
    • Metadata: latency, model, vision_pages, etc.
    • Confidence: [0, 1] (validated & clamped)
    ↓
JSON RESPONSE to Client
```

---

## 3. PHASE 1: DOCUMENT INGESTION

### 3.1 Input
- **Source**: `D:\Data_Raw` (recursive scan)
- **Format**: PDF (vector text or scanned images)
- **Size**: Thousands of files, various sizes

### 3.2 Processing Steps

#### Step 1: File Discovery
```python
# Recursive scan
for pdf_file in scan_directory("D:\\Data_Raw"):
    if is_valid_pdf(pdf_file):
        process_document(pdf_file)
```

#### Step 2: PDF Parsing
```python
# Try vector text first
doc = fitz.open(pdf_path)
text = extract_text(doc)

if not has_text(text):
    # Fallback to OCR
    text = ocr_with_tesseract(pdf_path, lang="vie+eng", dpi=300)
```

#### Step 3: Metadata Extraction
```python
metadata = {
    "doc_id": generate_doc_id(pdf_path),
    "pdf_path": pdf_path,
    "file_name": Path(pdf_path).name,
    "source_format": "vector" or "scan",
    "equipment_id": extract_equipment_id(text),  # Regex: \bKT?\d{5}\b
    "doc_type": infer_doc_type(pdf_path, text),   # Manual, Drawing, etc.
    "total_pages": doc.page_count,
    "created_at": datetime.now()
}
```

#### Step 4: Content Normalization
```python
# Normalize for deduplication
normalized = text.lower().strip()
normalized = re.sub(r'\s+', ' ', normalized)
content_hash = hashlib.sha1(normalized.encode()).hexdigest()
```

### 3.3 Output
- **chunks.jsonl**: Raw chunks (before indexing)
- **doc_id_map.json**: `{doc_id: {pdf_path, file_name, ...}}`
- **quarantine.jsonl**: Failed/corrupted files

---

## 4. PHASE 2: INDEXING & STORAGE

### 4.1 Chunking Strategy

```python
# Character-based chunking
chunk_size = 1000  # characters
overlap = 200      # characters

chunks = []
for i in range(0, len(text), chunk_size - overlap):
    chunk_text = text[i:i + chunk_size]
    chunk = {
        "chunk_id": f"{doc_id}_chunk_{i}",
        "text": chunk_text,
        "doc_id": doc_id,
        "page": calculate_page(i, page_breaks),
        "metadata": {...}
    }
    chunks.append(chunk)
```

### 4.2 Deduplication

```python
# Group by content_hash
hash_groups = defaultdict(list)
for chunk in chunks:
    content_hash = sha1(normalize(chunk.text))
    hash_groups[content_hash].append(chunk)

# Keep 1 representative per group
deduped_chunks = []
for hash_val, group in hash_groups.items():
    # Priority: vector > scan > newer > shorter_path
    representative = select_best(group)
    deduped_chunks.append(representative)
```

### 4.3 Weaviate Indexing

```python
# Connect to Weaviate
client = weaviate.connect_to_local(
    host="localhost",
    port=8080,
    grpc_port=50051
)

# Create collection
collection = client.collections.create(
    name="PVCFCDocuments",
    vectorizer_config=None,  # Manual vectorization
    properties=[
        Property(name="text", data_type=DataType.TEXT),
        Property(name="doc_id", data_type=DataType.TEXT),
        Property(name="page", data_type=DataType.INT),
        # ... more properties
    ]
)

# Batch insert
with collection.batch.dynamic() as batch:
    for chunk in chunks:
        # Embed text
        vector = embed_text(chunk["text"])

        # Add to batch
        batch.add_object(
            properties=chunk,
            vector=vector
        )
```

### 4.4 OpenSearch Indexing

```python
# Create index
opensearch_client.indices.create(
    index="rag_chunks",
    body={
        "settings": {
            "index": {
                "similarity": {
                    "bm25_custom": {
                        "type": "BM25",
                        "k1": 1.2,
                        "b": 0.75
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "text": {"type": "text", "similarity": "bm25_custom"},
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
                # ... more fields
            }
        }
    }
)

# Bulk insert
for chunk in chunks:
    opensearch_client.index(
        index="rag_chunks",
        body=chunk
    )
```

---

## 5. PHASE 3: QUERY PROCESSING

### 5.1 Query Transform

```python
def transform_query(query: str) -> TransformedQuery:
    # 1. Normalize
    normalized = query.lower().strip()

    # 2. Intent detection
    intent = detect_intent(query)  # ASK|LOCATE|EXPLAIN|REPORT

    # 3. Extract filters
    filters = {}

    # Equipment ID: K06101, KT06101
    match = re.search(r'\bKT?(\d{5})\b', query, re.IGNORECASE)
    if match:
        filters["equipment_id"] = match.group(0)

    # Doc type: "manual", "drawing", etc.
    for doc_type in ["manual", "drawing", "maintenance"]:
        if doc_type in query.lower():
            filters["doc_type"] = doc_type.title()

    # 4. HyDE (optional)
    hyde_docs = []
    if enable_hyde:
        # Generate hypothetical document
        hyde_prompt = f"Write a technical document that would answer: {query}"
        hyde_doc = llm_generate(hyde_prompt)
        hyde_docs = [hyde_doc]

    return TransformedQuery(
        original=query,
        normalized=normalized,
        intent=intent,
        filters=filters,
        hyde_queries=hyde_docs
    )
```

---

## 6. PHASE 4: HYBRID RETRIEVAL

### 6.1 Parallel Retrieval

```python
async def hybrid_search(query: str, k: int = 50):
    # Parallel execution
    weaviate_task = asyncio.create_task(
        weaviate_search(query, limit=k)
    )
    opensearch_task = asyncio.create_task(
        opensearch_search(query, size=k)
    )

    # Wait for both
    weaviate_results, opensearch_results = await asyncio.gather(
        weaviate_task,
        opensearch_task,
        return_exceptions=True
    )

    # Handle failures gracefully
    if isinstance(weaviate_results, Exception):
        logger.warning("Weaviate failed, using OpenSearch only")
        weaviate_results = []

    if isinstance(opensearch_results, Exception):
        logger.warning("OpenSearch failed, using Weaviate only")
        opensearch_results = []

    return weaviate_results, opensearch_results
```

### 6.2 Weaviate Search

```python
def weaviate_search(query: str, limit: int) -> List[Result]:
    # 1. Embed query
    query_vector = embed_text(query)

    # 2. Vector search
    response = collection.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        return_metadata=["distance"]
    )

    # 3. Convert to results
    results = []
    for obj in response.objects:
        results.append(Result(
            chunk_id=obj.properties["chunk_id"],
            text=obj.properties["text"],
            doc_id=obj.properties["doc_id"],
            page=obj.properties["page"],
            score=1 - obj.metadata.distance,  # Convert distance to score
            source="weaviate"
        ))

    return results
```

### 6.3 OpenSearch BM25 Search

```python
def opensearch_search(query: str, size: int) -> List[Result]:
    # 1. Tokenize query
    tokens = query.lower().split()

    # 2. BM25 search
    response = opensearch_client.search(
        index="rag_chunks",
        body={
            "query": {
                "match": {
                    "text": {
                        "query": query,
                        "operator": "or"
                    }
                }
            },
            "size": size
        }
    )

    # 3. Convert to results
    results = []
    for hit in response["hits"]["hits"]:
        results.append(Result(
            chunk_id=hit["_source"]["chunk_id"],
            text=hit["_source"]["text"],
            doc_id=hit["_source"]["doc_id"],
            page=hit["_source"]["page"],
            score=hit["_score"],
            source="opensearch"
        ))

    return results
```

### 6.4 RRF Fusion

```python
def reciprocal_rank_fusion(
    weaviate_results: List[Result],
    opensearch_results: List[Result],
    k: int = 60
) -> List[Result]:
    """
    RRF formula: score(d) = Σ (1 / (k + rank_i(d)))
    where rank_i(d) is the rank of document d in retriever i
    """
    rrf_scores = defaultdict(float)

    # Add Weaviate scores
    for rank, result in enumerate(weaviate_results):
        rrf_scores[result.chunk_id] += 1 / (k + rank + 1)

    # Add OpenSearch scores
    for rank, result in enumerate(opensearch_results):
        rrf_scores[result.chunk_id] += 1 / (k + rank + 1)

    # Merge and deduplicate
    merged_results = {}
    for result in weaviate_results + opensearch_results:
        if result.chunk_id not in merged_results:
            merged_results[result.chunk_id] = result
            result.fused_score = rrf_scores[result.chunk_id]

    # Sort by RRF score
    sorted_results = sorted(
        merged_results.values(),
        key=lambda r: r.fused_score,
        reverse=True
    )

    return sorted_results
```

---

## 7. PHASE 5: RERANKING

### 7.1 BGE CrossEncoder Reranking (Optional)

```python
def bge_rerank(
    query: str,
    results: List[Result],
    top_k: int = 10
) -> List[Result]:
    # 1. Load model (cached)
    model = CrossEncoder("BAAI/bge-reranker-base")

    # 2. Prepare pairs
    pairs = [[query, result.text] for result in results]

    # 3. Score all pairs
    scores = model.predict(pairs)

    # 4. Attach scores
    for result, score in zip(results, scores):
        result.rerank_score = float(score)

    # 5. Sort by rerank score
    reranked = sorted(
        results,
        key=lambda r: r.rerank_score,
        reverse=True
    )

    # 6. Return top-k
    return reranked[:top_k]
```

### 7.2 Fallback: Score-based Reranking

```python
def score_based_rerank(results: List[Result], top_k: int) -> List[Result]:
    # Sort by original scores (fusion or retrieval)
    sorted_results = sorted(
        results,
        key=lambda r: r.fused_score if hasattr(r, 'fused_score') else r.score,
        reverse=True
    )
    return sorted_results[:top_k]
```

---

## 8. PHASE 6: ANSWER GENERATION

### 8.1 Strategy Selection

```python
def select_generation_strategy(
    query: str,
    retrieved_docs: List[Result],
    config: GeneratorConfig
) -> str:
    # Check if vision is enabled
    if not config.enable_vision_generation:
        return "text"

    # Check if we have PDF pages available
    has_pdf_pages = any(
        doc.pdf_path and doc.page
        for doc in retrieved_docs
    )

    if not has_pdf_pages:
        return "text"

    # Check for visual keywords
    visual_keywords = ["table", "figure", "diagram", "chart", "P&ID"]
    has_visual_intent = any(
        keyword in query.lower()
        for keyword in visual_keywords
    )

    if has_visual_intent:
        return "vision"

    # Default to text for simple queries
    return "text"
```

### 8.2 Vision Generation (Multimodal)

```python
def vision_generation(
    query: str,
    retrieved_docs: List[Result],
    doc_id_map: Dict
) -> Tuple[str, List[Citation]]:
    # 1. Select pages to render
    pages_to_render = select_vision_pages(
        retrieved_docs,
        max_pages=10
    )

    # 2. Render PDF pages to images
    rendered_pages = []
    for pdf_path, page_num in pages_to_render:
        try:
            image = render_pdf_page(
                pdf_path=pdf_path,
                page=page_num,
                dpi=200,
                format="jpeg"
            )
            rendered_pages.append({
                "pdf_path": pdf_path,
                "page": page_num,
                "image": image
            })
        except Exception as e:
            logger.warning(f"Failed to render page {page_num}: {e}")

    # 3. Build vision prompt
    prompt = f"""
Based on the provided PDF pages, answer the following question:

Question: {query}

Instructions:
- Provide a detailed answer based on the visual content
- Include page-specific citations in format: [Doc N, p.X]
- Focus on tables, diagrams, and specific values visible in the pages

Answer:
"""

    # 4. Call Gemini Vision
    response = gemini_client.generate_content(
        model="gemini-2.5-pro",
        contents=[
            prompt,
            *[page["image"] for page in rendered_pages]
        ]
    )

    # 5. Extract answer and citations
    answer = response.text
    citations = extract_citations(answer, rendered_pages)

    return answer, citations
```

### 8.3 Text Generation

```python
def text_generation(
    query: str,
    retrieved_docs: List[Result]
) -> Tuple[str, List[Citation]]:
    # 1. Build context
    context_parts = []
    doc_mapping = {}

    for i, doc in enumerate(retrieved_docs, 1):
        page_info = f" (Page {doc.page})" if doc.page else ""
        context_parts.append(f"[Doc {i}]{page_info} {doc.text}")
        doc_mapping[i] = doc

    context = "\n---\n".join(context_parts)

    # 2. Build prompt
    prompt = f"""
Based on the following context documents, answer the question.

Context:
{context}

Question: {query}

Instructions:
- Provide a concise, accurate answer
- Include citations in format: [Doc N, p.X]
- Only use information from the provided context

Answer:
"""

    # 3. Call Gemini
    response = gemini_client.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    # 4. Extract answer and citations
    answer = response.text
    citations = extract_citations(answer, doc_mapping)

    return answer, citations
```

### 8.4 Citation Extraction

```python
def extract_citations(
    answer: str,
    doc_mapping: Dict
) -> List[Citation]:
    # Pattern: [Doc X, p.Y] or [Doc X]
    pattern = r'\[Doc\s+(\d+)(?:,\s*pp?\.?\s*([\d\-]+))?\]'

    citations = []
    for match in re.finditer(pattern, answer):
        doc_num = int(match.group(1))
        page_str = match.group(2)

        if doc_num in doc_mapping:
            doc = doc_mapping[doc_num]

            # Parse page number
            if page_str:
                if '-' in page_str:
                    # Range: 5-7
                    start, end = map(int, page_str.split('-'))
                    pages = list(range(start, end + 1))
                else:
                    pages = [int(page_str)]
            else:
                pages = [doc.page] if doc.page else []

            # Create citation for each page
            for page in pages:
                citations.append(Citation(
                    doc_id=doc.doc_id,
                    page=page,
                    pdf_path=doc.pdf_path,
                    source="llm",
                    relevance_score=1.0
                ))

    return citations
```

### 8.5 Post-Validation (CiteFix-lite)

```python
def post_validate_citations(
    citations: List[Citation],
    query: str,
    retrieved_docs: List[Result]
) -> Tuple[List[Citation], Dict]:
    validator = CitationValidator(
        doc_id_map=load_doc_id_map(),
        neighbor_scan=2  # Check ±2 pages
    )

    validated_citations = []
    stats = {"valid": 0, "corrected": 0, "invalid": 0}

    for citation in citations:
        # Validate citation
        result = validator.validate(
            citation=citation,
            query=query,
            context_docs=retrieved_docs
        )

        if result.is_valid:
            validated_citations.append(citation)
            stats["valid"] += 1
        elif result.corrected_page:
            # Use corrected page
            citation.page = result.corrected_page
            validated_citations.append(citation)
            stats["corrected"] += 1
        else:
            stats["invalid"] += 1
            # Optionally keep or discard

    return validated_citations, stats
```

### 8.6 Confidence Calculation

```python
def calculate_confidence(
    answer: str,
    citations: List[Citation],
    retrieved_docs: List[Result]
) -> float:
    """
    Calculate confidence score with defensive programming
    """
    # Base confidence from retrieval scores
    if retrieved_docs:
        # DEFENSIVE: Handle None scores
        avg_score = sum(
            max(0, (doc.score or 0))
            for doc in retrieved_docs[:3]
        ) / min(3, len(retrieved_docs))
        base_confidence = min(avg_score * 2, 1.0)
    else:
        base_confidence = 0.0

    # Boost for citations
    if citations:
        citation_boost = min(len(citations) * 0.1, 0.3)
        base_confidence = min(base_confidence + citation_boost, 1.0)

    # Penalty for short answer
    if len(answer) < 50:
        base_confidence *= 0.7

    # Penalty for uncertainty markers
    uncertainty_phrases = ["not sure", "unclear", "might be"]
    if any(phrase in answer.lower() for phrase in uncertainty_phrases):
        base_confidence *= 0.8

    # DEFENSIVE: Final clamp to [0, 1]
    return max(0.0, min(1.0, base_confidence))
```

---

## 9. PHASE 7: RESPONSE BUILDING

### 9.1 Build API Response

```python
def build_response(
    query: str,
    answer: str,
    citations: List[Citation],
    confidence: float,
    metadata: Dict,
    timing: Dict
) -> AskResponse:
    # VALIDATION: Ensure confidence is valid
    final_confidence = confidence
    if final_confidence is None or not (0 <= final_confidence <= 1):
        logger.error(
            f"Invalid confidence value: {final_confidence}. "
            f"Clamping to valid range."
        )
        final_confidence = max(0.0, min(1.0, float(final_confidence or 0.0)))

    # Build citation list for response
    citations_list = []
    for cit in citations:
        # Clamp citation confidence too
        cit_conf = cit.relevance_score
        if cit_conf is not None:
            cit_conf = max(0.0, min(1.0, float(cit_conf)))

        citations_list.append({
            "doc_id": cit.doc_id,
            "page": cit.page or 1,
            "pdf_path": cit.pdf_path,
            "confidence": cit_conf,
            "bbox": cit.bbox
        })

    # Build metadata
    meta = {
        "model": metadata.get("model", "gemini-2.5-pro"),
        "latency_ms": round(timing["total"]),
        "breakdown": {
            "transform_ms": round(timing["transform"]),
            "retrieve_ms": round(timing["retrieve"]),
            "rerank_ms": round(timing["rerank"]),
            "generate_ms": round(timing["generate"])
        },
        "k": metadata.get("k", 8),
        "execution_mode": metadata.get("execution_mode", "production"),
        "trace_id": metadata.get("trace_id"),
        "vision_generation": metadata.get("vision_generation")
    }

    # Return response
    return AskResponse(
        answer=answer,
        citations=citations_list,
        confidence=final_confidence,
        meta=meta,
        warnings=metadata.get("warnings")
    )
```

---

## 10. COMPONENTS DEEP DIVE

### 10.1 LLM Service

```python
class LLMClient:
    def __init__(self, provider: str, model: str):
        self.provider = provider  # "gemini" or "openai"
        self.model = model

        if provider == "gemini":
            self.client = genai.GenerativeModel(model)
        elif provider == "openai":
            self.client = openai.ChatCompletion

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> LLMResponse:
        if self.provider == "gemini":
            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )
            return LLMResponse(
                content=response.text,
                model=self.model,
                finish_reason="stop"
            )
        # ... OpenAI implementation
```

### 10.2 Embedding Service

```python
class EmbeddingService:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.dimension = self._get_dimension(model)

    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 256
    ) -> List[np.ndarray]:
        """Batch embed texts with rate limiting"""
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Rate limiting
            time.sleep(0.1)

            # Embed batch
            if self.provider == "gemini":
                result = genai.embed_content(
                    model=self.model,
                    content=batch,
                    task_type="retrieval_document"
                )
                batch_embeddings = result['embedding']

            embeddings.extend(batch_embeddings)

        return embeddings

    def _get_dimension(self, model: str) -> int:
        """Auto-detect embedding dimension"""
        if "gemini-embedding-001" in model:
            return 768
        elif "e5-small" in model:
            return 384
        else:
            # Probe by embedding a test string
            test_emb = self.embed_texts(["test"])[0]
            return len(test_emb)
```

### 10.3 PDF Renderer

```python
def render_pdf_page(
    pdf_path: str,
    page: int,
    dpi: int = 200,
    format: str = "jpeg"
) -> bytes:
    """Render a PDF page to image bytes"""
    import fitz  # PyMuPDF

    # Open PDF
    doc = fitz.open(pdf_path)

    # Get page (0-indexed)
    page_obj = doc[page - 1]

    # Render to pixmap
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page_obj.get_pixmap(matrix=mat)

    # Convert to bytes
    if format == "jpeg":
        img_bytes = pix.tobytes("jpeg", quality=90)
    elif format == "png":
        img_bytes = pix.tobytes("png")

    doc.close()

    return img_bytes
```

---

## 11. ERROR HANDLING & RESILIENCE

### 11.1 Graceful Degradation

```python
# Hybrid retrieval with fallback
try:
    weaviate_results = weaviate_search(query)
except Exception as e:
    logger.warning(f"Weaviate failed: {e}. Using OpenSearch only.")
    weaviate_results = []

try:
    opensearch_results = opensearch_search(query)
except Exception as e:
    logger.warning(f"OpenSearch failed: {e}. Using Weaviate only.")
    opensearch_results = []

if not weaviate_results and not opensearch_results:
    raise RuntimeError("All retrieval backends failed")
```

### 11.2 Validation & Logging

```python
# Always validate and log invalid states
if confidence is None or not (0 <= confidence <= 1):
    logger.error(
        f"Invalid confidence: {confidence}. "
        f"This indicates a bug. Clamping for stability."
    )
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))
```

### 11.3 Retry Logic

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ConnectionError)
)
def embed_with_retry(texts: List[str]) -> List[np.ndarray]:
    return embedding_service.embed_texts(texts)
```

---

## 12. PERFORMANCE & OPTIMIZATION

### 12.1 Caching Strategy

```python
# Cache expensive operations
@lru_cache(maxsize=1000)
def embed_query_cached(query: str) -> np.ndarray:
    return embedding_service.embed_texts([query])[0]

# Cache retrieval results
retrieval_cache = TTLCache(maxsize=100, ttl=300)  # 5 minutes

def cached_retrieve(query: str, k: int) -> List[Result]:
    cache_key = (query, k)
    if cache_key in retrieval_cache:
        return retrieval_cache[cache_key]

    results = hybrid_retrieve(query, k)
    retrieval_cache[cache_key] = results
    return results
```

### 12.2 Batching

```python
# Batch embedding for efficiency
def embed_documents_batched(
    docs: List[str],
    batch_size: int = 256
) -> List[np.ndarray]:
    embeddings = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        batch_embeddings = embedding_service.embed_texts(batch)
        embeddings.extend(batch_embeddings)
    return embeddings
```

### 12.3 Async Processing

```python
# Parallel retrieval
async def parallel_retrieve(query: str):
    weaviate_task = asyncio.create_task(weaviate_search(query))
    opensearch_task = asyncio.create_task(opensearch_search(query))

    weaviate_results, opensearch_results = await asyncio.gather(
        weaviate_task,
        opensearch_task,
        return_exceptions=True
    )

    return weaviate_results, opensearch_results
```

---

## 📊 PERFORMANCE METRICS

| Metric | Value | Notes |
|--------|-------|-------|
| **Ingestion** | ~5 docs/sec | With OCR |
| **Indexing** | ~1000 docs/min | Weaviate + OpenSearch |
| **Query Latency** | 500-2000ms | Depends on reranking |
| **  - Transform** | 50-150ms | Query processing |
| **  - Retrieval** | 200-500ms | Hybrid search |
| **  - Rerank** | 100-400ms | BGE if enabled |
| **  - Generation** | 300-1000ms | LLM call |
| **Throughput** | 20-50 QPS | Single instance |
| **Memory Usage** | 4-8GB | Runtime |
| **Vector Dimension** | 768D | Gemini embedding |

---

## 🔗 RELATED DOCUMENTATION

- [README.md](README.md) - Quick start guide
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [CONFIDENCE_DEFENSIVE_IMPROVEMENTS.md](docs/implementation/CONFIDENCE_DEFENSIVE_IMPROVEMENTS.md) - Defensive programming details
- [docs/guides/WEAVIATE_SETUP_GUIDE.md](docs/guides/WEAVIATE_SETUP_GUIDE.md) - Weaviate setup
- [docs/guides/MANUAL_TESTING_CHECKLIST.md](docs/guides/MANUAL_TESTING_CHECKLIST.md) - Testing guide

---

**Last Updated**: 2025-10-11
**Version**: 0.6.1
**Status**: ✅ Production Ready
