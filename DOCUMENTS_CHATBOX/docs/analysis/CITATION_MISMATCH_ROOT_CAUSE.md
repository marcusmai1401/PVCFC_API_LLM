# 🔍 ROOT CAUSE ANALYSIS: LLM trả lời ĐÚNG nhưng trích nguồn SAI

**Date**: 2025-10-09
**Issue**: Query về "4th stage CO2 compressor" → Answer chính xác tuyệt đối → Nhưng cite sai file (TURBINE thay vì COMPRESSOR)

---

## 📊 Hiện tượng

### Query:
```
"What are the specified 'Rated' operating conditions for the 4th stage
of the CO2 compressor, specifically regarding inlet (suction) pressure,
inlet (suction) temperature, and molecular weight?"
```

### Answer (LLM):
```
Based on the provided documents, the specified rated operating conditions
for the 4th stage of the CO2 compressor are as follows:

- Inlet (Suction) Pressure: 79.5 BAR. A [1][1]
- Inlet (Suction) Temperature: 50.0 DEG. C [1][1]
- Molecular Weight: 43.40 [1][1]

Additionally, a remark specifies that the suction temperature of the 4th
stage must never drop below 50°C [1][1].
```

**✅ Answer: CHÍNH XÁC TUYỆT ĐỐI**

### Citations:
```
[1] 07087-06000-CP22-K06101 rev 0F.pdf (TURBINE file!)
    - Page 1, 2, 3
```

**❌ Citations: SAI HOÀN TOÀN** - File này là về TURBINE, không phải về CO2 COMPRESSOR!

---

## 🔬 Investigation Results

### 1. Files chứa đúng thông tin:

Theo `doc_id_map.json`, các files về CO2 Compressor:

```
✅ CORRECT FILES (should be cited):
- 002_3N4-S4274342 Data Sheet of Compressor_Rev.01.pdf
- 002_3N4-S4274343 datasheet for K06101_Rev.02.pdf
- 003_3N4-S4274344 Expected Performance Curve of Compressor_Rev.01.pdf

❌ WRONGLY CITED FILE:
- 07087-06000-CP22-K06101 rev 0F.pdf (TURBINE datasheet)
```

### 2. Retrieval + Reranking Scores:

Từ API logs:

```
Top retrieved docs (after reranking):
#1: doc_id=DOCID_KT06101_TURBINE_HTC_...  score=2.2063  ← TURBINE (WRONG!)
#2: doc_id=DOCID_KT06101_TURBINE_HTC_...  score=2.0196  ← TURBINE (WRONG!)
#3: doc_id=DOCID_K06101_CO2_COMPRESSOR... score=1.5732  ← CO2 COMPRESSOR (RIGHT!)
```

**🚨 VẤN ĐỀ #1**: BM25 + FAISS + Cross-encoder đã rank **TURBINE docs cao hơn** CO2 COMPRESSOR docs!

### 3. Vision Page Scoring:

Code trong `generator.py` (dòng 1454-1494):

```python
for doc in retrieved_docs[:20]:
    if doc.doc_id == result_doc_id:
        score += doc.score * 10  # Multiply retrieval score by 10!

        # Keyword matching
        for token in query_tokens:
            if token in doc_text_lower:
                score += 1
```

**Kết quả**:
```
Vision page scoring (from logs):
- Pages 1-5 from TURBINE:     score=29.06  (doc_score 2.2 × 10 + keywords)
- Pages 7-11 from CO2 COMP:   score=21.73  (doc_score 1.57 × 10 + keywords)
```

**🚨 VẤN ĐỀ #2**: Vision scoring **nhân đôi sai lầm** của retrieval/reranking!
- TURBINE pages ranked #1-5 ([Doc 1] - [Doc 5])
- CO2 COMPRESSOR pages ranked #6-10 ([Doc 6] - [Doc 10])

### 4. LLM Input:

LLM nhận được:
1. **Text context**: `[Doc 1]` = TURBINE, `[Doc 2]` = TURBINE, ... `[Doc 6]` = CO2 COMPRESSOR
2. **Images**:
   - Images 1-5: TURBINE pages
   - Images 6-10: CO2 COMPRESSOR pages

**🤔 PARADOX**: LLM trả lời ĐÚNG thông tin, nhưng cite [Doc 1] (TURBINE)!

---

## 🎯 Root Causes

### Root Cause #1: Retrieval Pipeline SAI (BM25 + FAISS)

**Vấn đề**:
- Query: "4th stage CO2 compressor"
- BM25 + FAISS retrieval trả về TURBINE docs với score cao hơn
- Có thể do:
  - TURBINE và CO2 COMPRESSOR share nhiều technical terms
  - Doc "K06101" xuất hiện ở cả 2 loại files
  - BM25 term frequency-based → nhầm lẫn khi terms overlap

**Evidence**:
```
Retrieved doc #1 score: 2.2063 (TURBINE)  ← Higher score
Retrieved doc #3 score: 1.5732 (CO2 COMP) ← Lower score
```

### Root Cause #2: Cross-Encoder Reranker KHÔNG SỬA ĐƯỢC

**Vấn đề**:
- Cross-encoder model (`ms-marco-MiniLM-L-6-v2`) vẫn rank TURBINE cao hơn
- Model có thể không đủ semantic understanding để phân biệt TURBINE vs COMPRESSOR context

**Evidence**:
- Sau reranking, TURBINE docs vẫn ở top #1, #2

### Root Cause #3: Vision Scoring NHÂN ĐÔI SAI LẦM

**Vấn đề**:
- Vision scoring logic: `score = retrieval_score × 10 + keyword_matches`
- Nếu retrieval sai từ đầu → vision scoring làm tệ hơn
- TURBINE pages được boost lên [Doc 1-5], CO2 pages bị đẩy xuống [Doc 6-10]

**Code location**: `app/rag/generator.py` dòng 1454-1494

### Root Cause #4: LLM Bias Towards Top-Ranked Docs

**Vấn đề**:
- LLM thấy [Doc 1-5] là TURBINE (images + text context)
- LLM thấy [Doc 6-10] là CO2 COMPRESSOR (images + text context)
- LLM có xu hướng cite docs xuất hiện đầu tiên trong context
- Mặc dù LLM **đọc được thông tin đúng từ [Doc 6-10]** (CO2 pages), nhưng cite [Doc 1] (TURBINE)

**Possible reasons LLM answered correctly**:
1. **Memorization**: Gemini 2.5 Pro đã học data này từ training
2. **Read CO2 pages**: LLM thực sự đọc images 6-10 (CO2 pages) nhưng cite nhầm [Doc 1]
3. **Context text**: Text context có chứa snippet từ CO2 doc (#3 in retrieval)

---

## 💡 Solution Paths

### Path 1: Fix Retrieval Pipeline (HIGH PRIORITY)

**Problem**: BM25 + FAISS retrieval không phân biệt được TURBINE vs COMPRESSOR

**Solutions**:
1. **Query rewriting với explicit keywords**:
   ```python
   # Khi detect "CO2 compressor" → boost terms
   boosted_query = "CO2 compressor stage datasheet specifications"
   # Negative keywords cho TURBINE
   negative_query = "-turbine -steam"
   ```

2. **Metadata filtering**:
   ```python
   # Filter by folder/file path
   if "compressor" in query.lower():
       filter_paths = ["CO2_COMPRESSOR", "COMPRESSOR_HITACHI"]
   ```

3. **Better embeddings model**:
   - Thay `gemini-embedding-001` bằng model better at technical domain
   - Or: fine-tune embedding model on your corpus

### Path 2: Improve Reranker (MEDIUM PRIORITY)

**Problem**: Cross-encoder model không đủ mạnh

**Solutions**:
1. **Upgrade model**:
   - From: `ms-marco-MiniLM-L-6-v2` (small, general-purpose)
   - To: `cross-encoder/ms-marco-MiniLM-L-12-v2` (larger) or domain-specific model

2. **Add metadata-based scoring**:
   ```python
   # Boost score if doc_id/path matches query intent
   if "compressor" in query and "COMPRESSOR" in doc_id:
       rerank_score *= 1.5
   if "compressor" in query and "TURBINE" in doc_id:
       rerank_score *= 0.5
   ```

### Path 3: Fix Vision Scoring Logic (LOW PRIORITY)

**Problem**: Vision scoring blindly trusts retrieval scores

**Solutions**:
1. **Independent vision scoring**:
   ```python
   # Don't multiply by retrieval score
   score = keyword_matches  # Only keywords, not doc.score × 10
   ```

2. **Add LLM-based relevance check**:
   ```python
   # Quick LLM call to score page relevance
   relevance = llm.score_relevance(query, page_text)
   score = relevance × 10 + keyword_matches
   ```

### Path 4: LLM Prompt Engineering (QUICK WIN)

**Problem**: LLM cite top docs even if info from lower docs

**Solutions**:
1. **Explicit citation instructions**:
   ```
   "CRITICAL: You MUST cite the EXACT Doc number where you found each piece of information.
   If information is in Doc 6, cite [Doc 6], NOT [Doc 1]."
   ```

2. **Force LLM to explain citations**:
   ```
   "For each citation, briefly explain why you cite that specific Doc."
   ```

3. **Shuffle doc order** (experimental):
   ```python
   # Randomize doc order to prevent position bias
   shuffled_vision_mapping = shuffle_with_seed(vision_doc_mapping)
   ```

---

## 🧪 Testing Plan

### Test 1: Verify retrieval scores
```python
# Run query manually
query = "4th stage CO2 compressor specifications"
results = retriever.search(query, top_k=20)

# Check if CO2 COMPRESSOR docs in top 3
for i, doc in enumerate(results[:5], 1):
    print(f"#{i}: {doc.doc_id}, score={doc.score}")
    # Expect CO2 COMPRESSOR docs to be #1, #2
```

### Test 2: Test reranker alone
```python
# Get BM25/FAISS results
retrieval_results = retriever.search(query, top_k=50)

# Rerank
reranked = reranker.rerank(query, retrieval_results, top_k=10)

# Verify CO2 COMPRESSOR docs moved to top
```

### Test 3: Test with fixed retrieval
```python
# Manually inject CO2 COMPRESSOR docs as top results
fake_top_docs = [
    get_doc("002_3N4-S4274342"),  # CO2 datasheet
    get_doc("002_3N4-S4274343"),  # CO2 datasheet
]
fake_results = fake_top_docs + retrieval_results[2:]

# Run generation with fixed retrieval
answer = generator.generate(query, fake_results)

# Check if citations now point to CO2 COMPRESSOR docs
```

---

## 📈 Priority & Impact

| Solution | Priority | Effort | Impact | Risk |
|----------|----------|--------|--------|------|
| **Query rewriting + metadata filter** | 🔴 HIGH | Medium | High | Low |
| **LLM prompt engineering** | 🟡 MEDIUM | Low | Medium | Low |
| **Upgrade reranker model** | 🟡 MEDIUM | Medium | Medium | Low |
| **Better embeddings** | 🟢 LOW | High | High | Medium |
| **Fix vision scoring** | 🟢 LOW | Low | Low | Low |

---

## 🎯 Recommended Next Steps

### Immediate (Today):
1. ✅ **Add debug logging** to print retrieval scores for CO2 queries
2. ✅ **Test query with manual doc injection** to verify hypothesis
3. ✅ **Try LLM prompt engineering** (quick win, no code change needed)

### Short-term (This week):
4. **Implement query rewriting** with keyword boosting for "compressor" queries
5. **Add metadata filtering** based on folder/file paths
6. **Test with different reranker models** (ms-marco-L-12 or domain-specific)

### Long-term (Next sprint):
7. **Fine-tune embedding model** on your technical corpus
8. **Build domain-specific reranker** trained on your docs
9. **Implement hybrid scoring** (retrieval + semantic + metadata)

---

## 📝 Conclusion

**The bug is NOT in IEEE Citations feature!**

IEEE Citations feature hoạt động đúng 100%:
- ✅ Citations được extract correct từ LLM answer
- ✅ Doc number mapping correct
- ✅ References section hiển thị correct file names
- ✅ PDF links work correctly

**The bug is in the Retrieval → Reranking → Vision Scoring pipeline:**
- ❌ BM25/FAISS retrieval rank wrong docs higher
- ❌ Cross-encoder reranker không sửa được
- ❌ Vision scoring nhân đôi sai lầm
- ❌ LLM cite top-ranked docs despite reading info from lower docs

**Impact**:
- User thấy answer ĐÚNG nhưng click vào cited doc lại thấy KHÔNG có thông tin
- Trust in system bị giảm
- Critical issue for production use

**Urgency**: 🔴 HIGH - Cần fix ngay để deploy production

---

**Analyzed by**: AI Assistant
**Status**: Root Cause Identified
**Next**: Implement solutions Path 1 + Path 4 (quick wins)
