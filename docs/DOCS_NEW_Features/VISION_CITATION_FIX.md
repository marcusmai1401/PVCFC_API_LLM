# Vision Citation Fix

## Problem Description

When using vision-based generation (Gemini 2.5 Pro with page images), the system was generating **correct answers** by reading tables and information from vision pages, but the **citations were incorrect** - they pointed to the wrong source documents and pages.

### Example Issue:
- **Query**: "What is the specified final tightening torque for an M42 anchor bolt according to Table: Tightened torque for anchor bolt?"
- **Correct Answer**: "1420 Nm" (from table on page 15 of KT06101_Installation instruction.pdf)
- **Incorrect Citations**: Pointed to page 160 of Operating Manual KT06101_0-2520-8043-00-en.pdf

## Root Cause

The vision generation system (`_try_vision_generation` method) was:
1. Rendering page images from the correct PDF pages (e.g., page 15 of Installation instruction.pdf)
2. Sending these images to Gemini 2.5 Pro
3. Getting a correct answer that referenced information from the vision images

However, when extracting citations from the LLM's answer using `_extract_citations`:
- It used the **original `doc_mapping`** built from text-based retrieval results (BM25/FAISS)
- This `doc_mapping` contained chunks from different documents (e.g., page 160 of Operating Manual)
- So when the LLM wrote `[Doc 1]` referencing the vision image, it was mapped to the wrong document

## Solution

Created a **vision-specific `doc_mapping`** that maps to the actual pages shown in vision images:

### Changes in `app/rag/generator.py`:

1. **Build vision_doc_mapping** (lines 1098-1137):
   - For each page rendered for vision, create a synthetic `RetrievalResult`
   - Store the actual `pdf_path` and `page` number in the metadata
   - Map Doc numbers (1, 2, 3...) to these vision pages in order

2. **Use vision_doc_mapping in prompt** (lines 1171-1181):
   - Updated the prompt generation to use `vision_doc_mapping` instead of `doc_mapping`
   - This ensures the Doc mapping shown to the LLM matches the actual images

3. **Extract citations using vision_doc_mapping** (line 1263-1265):
   - Changed `_extract_citations` to use `vision_doc_mapping`
   - Now citations correctly point to the pages actually shown in vision images

4. **Enhanced citation enrichment** (lines 1024-1033, 1052-1062):
   - Updated `_extract_citations` to first check for `pdf_path` in `RetrievalResult.metadata`
   - Falls back to `doc_id_map` for text-based retrieval results
   - This ensures both vision and text citations are enriched correctly

## Testing

Run the test script to verify:

```powershell
python test_api_vision_citations.py
```

The test will:
1. Send a query about the M42 anchor bolt torque
2. Check if vision was used
3. Validate that citations point to the correct document and page
4. Show which pages were actually used in vision generation

## Expected Behavior After Fix

- When vision is used, citations should point to the **actual PDF pages shown in the vision images**
- The citation doc_id, page number, and pdf_path should all match the vision pages
- The answer should continue to be accurate (unchanged)
- The vision metadata will show which pages were used for generation

## Files Modified

- `app/rag/generator.py`: Core fix for vision citation mapping
- `test_api_vision_citations.py`: Test script to verify the fix

## Verification Checklist

✅ Citations point to correct PDF files
✅ Citations point to correct page numbers
✅ pdf_path is correctly populated in citations
✅ Answer quality remains unchanged
✅ Vision metadata shows correct pages used
✅ Fallback to text-only generation still works correctly
