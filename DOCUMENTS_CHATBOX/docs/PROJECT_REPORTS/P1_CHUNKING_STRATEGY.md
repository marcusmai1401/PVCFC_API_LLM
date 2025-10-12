# P1: Task-Aware Chunking Strategy

**Date**: 2025-10-02
**Phase**: P1 (Chunking & Domain Normalization)
**Status**: 🔨 IN PROGRESS

---

## 📝 Overview

P1 implements intelligent, task-aware chunking strategies that preserve semantic meaning and spatial relationships for different document types: regular text, tables, and P&ID diagrams.

---

## 🎯 Goals

1. **Preserve semantic meaning** - Don't break mid-sentence or mid-concept
2. **Maintain spatial context** - Keep bbox metadata for P&IDs
3. **Optimize for retrieval** - Chunks sized for effective embedding
4. **Enable deduplication** - Content-hash based to avoid redundancy
5. **Support multi-language** - Handle Vietnamese and English equally

---

## 📊 Chunking Strategies

### 1. Regular Text Chunking

**Target**: Technical documents, reports, manuals, specifications

**Parameters:**
```python
DEFAULT_CHUNK_SIZE = 900  # tokens (800-1000 range)
DEFAULT_OVERLAP = 140      # tokens (120-160 range)
MIN_CHUNK_SIZE = 100       # tokens
MAX_CHUNK_SIZE = 1200      # tokens (hard limit)
```

**Strategy:**
- Split by semantic boundaries (paragraphs, sections)
- Preserve headers and titles with their content
- Use token-based counting (tiktoken or simple char/4 estimate)
- Sliding window with overlap for context continuity
- Detect and preserve:
  - Section headers (markdown-style or numbered)
  - Bullet lists (keep together)
  - Equipment IDs and tags (don't split)
  - Technical specifications (keep together)

**Example:**
```
Input Text: "The CO2 compressor (E-404) operates at 5000 RPM..."
Chunk 1: [Header] + First paragraph + Equipment spec
Chunk 2: [Overlap from Chunk 1 tail] + Next section...
```

**Implementation Details:**
- Use sentence tokenization as base unit
- Accumulate sentences until target size
- Add overlap by including last N tokens from previous chunk
- Normalize whitespace but preserve structure

---

### 2. Table Chunking

**Target**: Tabular data, specifications, BOM lists, data sheets

**Strategy: Column-First Mode**
- Keep table headers with every chunk
- Split by rows when table is too large
- Use window-merge for rows split across pages
- Preserve column relationships

**Parameters:**
```python
TABLE_MAX_ROWS_PER_CHUNK = 50    # rows
TABLE_KEEP_HEADER = True          # always include header
TABLE_WINDOW_MERGE = True         # merge split rows
```

**Table Structure Preservation:**
```
Original Table:
| Equipment | Type | Pressure | Flow | Status |
|-----------|------|----------|------|--------|
| P-101     | Pump | 150 PSI  | 250  | OK     |
| ...       | ...  | ...      | ...  | ...    |

Chunked:
Chunk 1: Header + Rows 1-50
Chunk 2: Header + Rows 51-100 (with window-merge if row 50 was split)
```

**Special Handling:**
- **Unit normalization**: "150 psi" → "150 PSI"
- **Number formatting**: Keep scientific notation, decimals
- **Column alignment**: Preserve relationships
- **Merged cells**: Keep context from merge span

**Markdown Table Format:**
```markdown
| Column1 | Column2 | Column3 |
|---------|---------|---------|
| Value1  | Value2  | Value3  |
```

---

### 3. P&ID Chunking

**Target**: P&ID diagrams, engineering drawings with text annotations

**Strategy: Bbox-Aware with Label Clustering**

**Metadata to Preserve:**
```python
{
    "page": 1,                    # Page number
    "zoom": 1.0,                  # Zoom factor
    "dpi": 150,                   # Rendering DPI
    "pixel_coords": {
        "x": 245,
        "y": 678,
        "width": 120,
        "height": 30
    },
    "text": "P-101",
    "confidence": 0.95,
    "nearby_symbols": ["arrow_right", "circle"],
    "label_cluster_id": "cluster_12"
}
```

**Label Clustering Logic:**
- Group text labels near each other (distance threshold: 50 pixels)
- Include nearby symbols (arrows, shapes) in cluster
- Preserve tag → equipment relationships
- Example cluster: "P-101" + "Pump" + "150 PSI" (all within 50px)

**Chunking Approach:**
1. Extract all text regions with OCR
2. For each region, compute bbox in page coordinates
3. Cluster nearby labels (spatial proximity)
4. Create chunks per cluster or per equipment
5. Preserve full bbox metadata in chunk metadata

**Example Chunk:**
```json
{
    "chunk_id": "doc_1234_page_5_cluster_3",
    "text": "P-101 Centrifugal Pump 150 PSI 250 GPM",
    "metadata": {
        "doc_id": "doc_1234",
        "page": 5,
        "chunk_type": "pid",
        "bbox_list": [
            {"text": "P-101", "x": 100, "y": 200, "w": 50, "h": 20},
            {"text": "Centrifugal Pump", "x": 160, "y": 200, "w": 150, "h": 20},
            ...
        ],
        "cluster_id": "cluster_3",
        "equipment_tag": "P-101",
        "equipment_type": "Pump"
    }
}
```

---

## 🔤 Language Normalization

### Text Cleanup
- **Whitespace**: Normalize multiple spaces to single space
- **Line breaks**: Remove unnecessary breaks, preserve paragraph structure
- **Special chars**: Keep technical symbols ($, %, °, etc.)
- **CJK handling**: Preserve if mixed with Latin (don't force remove)

### Mixed Language Support
```python
# Example: Vietnamese + English mixed text
text = "Bơm ly tâm P-101 operates at 150 PSI"
# Keep as-is, both languages preserved for recall
```

---

## 🔑 Content Deduplication

**Strategy**: Hash-based before embedding

**Process:**
1. Normalize chunk text (lowercase, trim, remove extra whitespace)
2. Compute content hash (SHA256)
3. Check cache/database for existing hash
4. Skip embedding if duplicate found
5. Reuse existing embedding vector

**Benefits:**
- Avoid redundant API calls (cost savings)
- Faster processing
- Consistent embeddings for identical content

**Implementation:**
```python
import hashlib

def compute_content_hash(text: str) -> str:
    normalized = text.lower().strip()
    normalized = ' '.join(normalized.split())  # normalize whitespace
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
```

**Dedup Logic:**
```python
# Before embedding
content_hash = compute_content_hash(chunk.text)

if content_hash in cache:
    chunk.embedding = cache[content_hash]
    metrics['cache_hits'] += 1
else:
    chunk.embedding = embed_service.embed([chunk.text])[0]
    cache[content_hash] = chunk.embedding
    metrics['api_calls'] += 1
```

---

## 📐 Token Estimation

**Methods:**
1. **Simple estimate**: `len(text) / 4` (rough)
2. **Accurate**: Use tiktoken library (OpenAI tokenizer)
3. **Fallback**: Character count with adjustments

**Implementation:**
```python
def estimate_tokens(text: str) -> int:
    """Estimate token count for chunking"""
    # Method 1: Simple estimate (fast)
    simple_estimate = len(text) / 4

    # Method 2: Accurate (if tiktoken available)
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except:
        return int(simple_estimate)
```

---

## 🏗️ Module Structure

```
app/ingestion/
├── chunkers/
│   ├── __init__.py
│   ├── base.py              # BaseChunker abstract class
│   ├── text_chunker.py      # Regular text chunking
│   ├── table_chunker.py     # Table-aware chunking
│   ├── pid_chunker.py       # P&ID bbox-aware chunking
│   └── utils.py             # Token counting, normalization
├── normalizers/
│   ├── __init__.py
│   ├── text_cleanup.py      # Whitespace, special char handling
│   └── unit_normalizer.py   # PSI, GPM, °F standardization
├── domain/
│   ├── __init__.py
│   └── pid_schema.py        # P&ID tag schema, regex, synonyms
└── dedup.py                 # Content deduplication
```

---

## 🎯 Success Criteria (DoD)

### P1 Acceptance Criteria

| Criteria | Target | Validation |
|----------|--------|------------|
| Text chunk size | 800-1000 tokens | Measure avg/p95 |
| Text overlap | 120-160 tokens | Verify overlap content |
| Header preservation | 100% | Check headers in chunks |
| Table header kept | 100% | Verify in table chunks |
| P&ID bbox preserved | 100% | Check metadata present |
| Label clustering | >90% accuracy | Manual review sample |
| Dedup effectiveness | >80% cache hit on repeat | Measure cache hits |
| Multi-language support | No loss | Test VI+EN mixed text |

---

## 🧪 Test Cases

### Test 1: Regular Text
```
Input: 5-page technical manual (3,000 tokens)
Expected: ~3-4 chunks, overlap preserved, headers included
```

### Test 2: Large Table
```
Input: BOM table with 200 rows, 8 columns
Expected: 4 chunks (50 rows each), header in all chunks
```

### Test 3: P&ID Diagram
```
Input: P&ID page with 50 text annotations
Expected: 8-10 clusters, all bbox metadata preserved
```

### Test 4: Deduplication
```
Input: Same paragraph repeated 10 times
Expected: 1 embedding, 9 cache hits (90% cache hit rate)
```

### Test 5: Mixed Language
```
Input: "Bơm P-101 operates at 150 PSI and delivers 250 GPM"
Expected: Single chunk, both languages preserved
```

---

## 📊 Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Chunking speed | > 100 pages/min | Fast ingestion |
| Memory usage | < 500 MB per worker | Scalable |
| Dedup cache size | < 1 GB for 10K chunks | Manageable |
| Token accuracy | ±10% vs tiktoken | Good enough for chunking |

---

## 🔜 Next Steps

After P1 design approval:
1. Implement BaseChunker abstract class
2. Implement TextChunker
3. Implement TableChunker
4. Implement PIDChunker
5. Implement deduplication module
6. Create integration tests
7. Benchmark performance

---

**Status**: ✅ Design Complete
**Ready for**: Implementation
**Owner**: Agent Mode (Warp AI)
