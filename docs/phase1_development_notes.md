# Phase 1 Development Notes

## Quá trình phát triển và debug

### Thời gian: 13/09/2025

## 1. Các vấn đề gặp phải và giải quyết

### 1.1 Bug trong VectorExtractor
- **Hyphenation bug**: List mutation khi iterate gây crash
- **Processing order**: Merge trước sort làm sai thứ tự text  
- **Rotation handling**: Mutate page object gây side effects
- **Unused parameters**: `handle_rotation` không được dùng

### 1.2 Import và dependencies
- Thiếu `rich` trong requirements.txt cho demo scripts
- Cần `app/rag/extractors/__init__.py` cho package structure
- PYTHONPATH cần set để import modules

### 1.3 Test compatibility
- Tests cũ reference `handle_rotation` parameter đã bị xóa
- Cần update test assertions

## 2. Modules được implement

### 2.1 Core processing
- `document_detector.py`: PDF type classification
- `vector_extractor.py`: Text extraction với bbox
- `text_normalizer.py`: Unicode và whitespace normalization
- `tag_normalizer.py`: P&ID equipment tag extraction
- `unit_normalizer.py`: Technical unit standardization

### 2.2 Pipeline components  
- `markdown_converter.py`: Convert blocks to Markdown
- `hierarchical_chunker.py`: Smart chunking với parent_id
- `bm25_indexer.py`: Offline search indexing

### 2.3 Tools và testing
- `extract_pilot.py`: Batch PDF processing
- `demo_pipeline.py`: Full pipeline demo
- `qa_extraction.py`: Quality analysis
- `test_fixes.py`: Bug verification

## 3. Real PDF testing results

### 3.1 Pilot documents tested
1. **P&ID Ammonia Unit** (117 pages, vector)
   - 14,970 blocks extracted
   - 410,184 characters
   - All pages rotated 270°
   - Structure detected correctly

2. **CO2 Compressor Data Sheet** (8 pages, vector)  
   - 953 blocks extracted
   - 16,064 characters
   - Technical units found: bar(g), °C, m³/h
   - Equipment tags identified

3. **Performance Curve** (11 pages, scan)
   - Correctly identified as scan
   - Skipped for OCR (Phase 2)

4. **Operation Manual** (37 pages, scan)
   - Correctly identified as scan  
   - Skipped for OCR (Phase 2)

### 3.2 Quality metrics achieved
- 100% PDF type detection accuracy
- 0% empty blocks after extraction
- Structure types properly classified
- Technical units and tags extracted
- BM25 search working with relevant results

## 4. Performance observations

### 4.1 Processing speed
- Vector PDFs: < 1 second per page
- Large P&ID (117 pages): ~ 2 minutes total
- Memory efficient: no OOM issues

### 4.2 Search quality
- BM25 index: 639 unique tokens from 36 chunks
- Query relevance: "CO2 compressor" score 6.32
- Search speed: instant for small corpus

## 5. Technical decisions made

### 5.1 Architecture choices
- PyMuPDF cho text extraction (fast, reliable)
- Dataclasses cho structured data (type safety)
- Regex patterns cho tag extraction (predictable, fast)
- Separate normalizers (single responsibility)

### 5.2 Processing pipeline
- Sort before merge để đảm bảo reading order
- Preserve original rotation trong results
- Skip flag thay vì list mutation
- Structure detection dựa trên font size

## 6. Known limitations

### 6.1 Current scope
- Chỉ hỗ trợ vector PDFs (scan PDFs chờ OCR)
- Basic table detection (chưa có advanced parsing)
- Không xử lý images/diagrams
- Không support form fields

### 6.2 Quality issues noted
- Superscript characters: "m /h" thay vì "m³/h"
- Unit variations: "Bar a", "bar g", "℃" vs "°C"
- Special characters trong P&ID: ●, ○, □

## 7. Next development priorities

### 7.1 Immediate (Phase 2)
- OCR integration cho scan PDFs
- Advanced table extraction
- Image/diagram processing
- API endpoints implementation

### 7.2 Future enhancements
- Vector embedding indexing (FAISS)
- LLM integration cho question answering
- Web UI development
- Performance optimization

---

**Notes**: Tài liệu này ghi lại quá trình development và debug. Thông tin final sẽ được tổng hợp vào CHANGLOG_README/ sau khi hoàn thành phase.
