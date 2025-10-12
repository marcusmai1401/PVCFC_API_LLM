# Implementation Tasks - Device Search & Page Jump Features

## 📋 Task List Overview

### Phase 1: Foundation - Data & Metadata (Current)
- [x] 1.1 Normalize tag utility function ✅
- [x] 1.2 Sync metadata "page" field across BM25/FAISS indices ✅
- [x] 1.3 PDF page image rendering pipeline ✅
- [x] 1.4 Document classification with LLM ✅

### Phase 2: Retrieval Enhancement
- [x] 2.1 Page-range expansion algorithm ✅
- [x] 2.2 Force ASK intent for non-location queries ✅
- [x] 2.3 Improve citation extraction with page numbers ✅

### Phase 3: UI - Device Overview
- [ ] 3.1 Create Device Overview component
- [ ] 3.2 PDF viewer with page jump
- [ ] 3.3 External data integration (Excel)
- [ ] 3.4 Q&A tab with auto-language

### Phase 4: Report Generation
- [ ] 4.1 Update report template
- [ ] 4.2 Add device-specific report sections
- [ ] 4.3 Format citations as footnotes

### Phase 5: Optimization
- [ ] 5.1 Enable GPU for CrossEncoder
- [ ] 5.2 Performance tuning
- [ ] 5.3 Evaluation metrics for page accuracy

---

## 🚀 Current Sprint: Phase 1 - Foundation

Starting with the most critical foundation components that other features depend on.
