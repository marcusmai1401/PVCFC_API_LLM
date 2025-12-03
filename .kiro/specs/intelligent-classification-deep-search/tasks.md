# Implementation Plan

## 1. Setup Project Structure and Core Interfaces

- [x] 1.1 Create classification module structure
  - Create `app/classification/taxonomy.py` with DocumentTaxonomy class (4-category system per design)
  - Create `app/classification/sampler.py` with AdaptivePageSampler interface
  - Create `app/classification/classifier.py` with DocumentClassifier interface (multimodal)
  - Create `app/classification/pipeline.py` with ClassificationPipeline interface
  - Note: Existing `document_type_12.py` uses different 12-type taxonomy - new 4-category system will coexist
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 1.2 Write property test for taxonomy validation
  - **Property 1: Taxonomy Category Validation**
  - **Property 2: Category-DocType Mapping Consistency**
  - **Validates: Requirements 1.1, 1.3**

- [x] 1.3 Create deep search module structure
  - Create `app/services/deep_search.py` with DeepSearchService interface
  - Create `app/api/routers/search.py` with search endpoints
  - Create `app/api/routers/classification.py` with classification endpoints
  - _Requirements: 5.1, 5.2_

## 2. Implement Adaptive Page Sampler

- [x] 2.1 Implement AdaptivePageSampler class
  - Implement `sample()` method with Head-Body-Tail strategy
  - Implement `_select_head_body_tail()` for page selection logic
  - Implement page rendering to PNG images using PyMuPDF
  - Handle edge cases: 1 page, 10 pages, 11 pages
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.2 Write property tests for page sampling
  - **Property 4: Short Document Full Sampling**
  - **Property 5: Long Document Head-Body-Tail Sampling**
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

## 3. Implement Document Classifier with Gemini Integration

- [x] 3.1 Implement DocumentClassifier class
  - Implement Gemini 2.5 Flash API integration for multimodal (images)
  - Implement `classify()` method with multimodal input (page images)
  - Implement `_build_classification_prompt()` with 4-category taxonomy context
  - Implement response parsing to ClassificationResult
  - Note: Existing `DocumentType12LLM` uses text-only; new classifier uses images
  - _Requirements: 4.1, 4.2, 4.6_

- [x] 3.2 Implement Dominant Content Rule logic
  - Implement `_apply_dominant_content_rule()` method
  - Count text vs drawing pages from page analysis
  - Map dominant content to appropriate doc_types
  - _Requirements: 4.3, 4.4, 4.5_

- [x] 3.3 Write property test for dominant content rule
  - **Property 9: Dominant Content Rule**
  - **Validates: Requirements 4.3, 4.4, 4.5**

- [x] 3.4 Implement low confidence fallback
  - Check confidence threshold (0.5)
  - Override to UNCATEGORIZED + NEEDS_REVIEW when confidence < 0.5
  - Handle case when dominant content cannot be determined
  - _Requirements: 4.7_

- [x] 3.5 Write property test for low confidence fallback
  - **Property 10: Low Confidence Fallback**
  - **Validates: Requirements 4.7**

- [x] 3.6 Write property test for classification output completeness
  - **Property 3: Classification Output Completeness**
  - **Validates: Requirements 1.2, 4.6**

## 4. Implement Classification Pipeline with P&ID Guardrail

- [x] 4.1 Implement ClassificationPipeline class
  - Integrate existing CADLikeGate as first step (already in `app/ingestion/cadlike_gate.py`)
  - Implement P&ID force-assignment when CAD_score >= 0.55
  - Skip AI classifier when guardrail triggers
  - Chain to DocumentClassifier when guardrail doesn't trigger
  - _Requirements: 3.1, 3.2, 3.3, 4.1_

- [x] 4.2 Write property tests for P&ID guardrail
  - **Property 6: P&ID Guardrail Enforcement**
  - **Property 7: Guardrail Execution Order**
  - **Property 8: AI Classifier Invocation**
  - **Validates: Requirements 3.1, 3.2, 3.3, 4.1**

- [x] 4.3 Implement error handling and fallback
  - Handle Gemini API failures with retry logic
  - Implement ClassificationFallback strategies
  - Ensure pipeline continues on classification failure
  - _Requirements: 8.4_

- [x] 4.4 Write property test for classification failure handling
  - **Property 18: Classification Failure Handling**
  - **Validates: Requirements 8.4**

## 5. Checkpoint - Ensure Classification Module Tests Pass

- [x] 5. Checkpoint





  - Ensure all tests pass, ask the user if questions arise.

## 6. Implement Deep Search Service

- [x] 6.1 Implement DeepSearchService class
  - Implement OpenSearch multi_match query with phrase_prefix
  - Implement doc_id aggregation for unique documents
  - Implement result parsing to DeepSearchResult objects
  - Support up to 10,000 document buckets
  - _Requirements: 5.2, 5.3, 5.4, 5.5_

- [x] 6.2 Write property test for deep search completeness
  - **Property 11: Deep Search Completeness**
  - **Validates: Requirements 5.2, 5.4**

- [x] 6.3 Implement category and doc_type filters
  - Add optional filter parameters to search method
  - Build OpenSearch bool query with filters
  - Ensure filters are applied before aggregation
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 6.4 Write property test for filter correctness
  - **Property 14: Filter Correctness**
  - **Validates: Requirements 6.1, 6.2, 6.3**

- [x] 6.5 Implement result grouping by category
  - Group results by category in response
  - Ensure no document appears in multiple groups
  - _Requirements: 6.4_

- [x] 6.6 Write property test for result grouping
  - **Property 15: Result Grouping**
  - **Validates: Requirements 6.4**

- [x] 6.7 Write property tests for search constraints
  - **Property 12: Deep Search No-LLM Constraint**
  - **Property 13: Search Result Metadata**
  - **Validates: Requirements 5.6, 5.7**

## 7. Implement API Endpoints
  
- [x] 7.1 Implement Deep Search endpoint
  - Create GET /api/search/documents endpoint
  - Add request validation for keyword parameter
  - Add optional category and doc_type query parameters
  - Return DeepSearchResponse with results_by_category
  - _Requirements: 5.1, 5.7, 6.4_

- [x] 7.2 Implement Classification endpoints
  - Create POST /api/classification/classify endpoint
  - Create GET /api/classification/taxonomy endpoint
  - Create GET /api/classification/documents/by-category endpoint
  - _Requirements: 9.1, 9.2, 9.3_

- [x] 7.3 Write unit tests for API endpoints
  - Test request validation
  - Test response format
  - Test error responses
  - _Requirements: 5.1, 9.1_

## 8. Update Metadata Schema

- [x] 8.1 Update OpenSearch index mapping
  - Add metadata.category field (keyword type) to existing rag_chunks index
  - Add metadata.doc_type field (keyword type)
  - Add metadata.classification_status field (keyword type)
  - Add metadata.classification_confidence field (float type)
  - Create migration script for existing documents
  - Note: Current index in `scripts/opensearch/create_rag_chunks_index.py` lacks these fields
  - _Requirements: 7.1, 7.2_

- [x] 8.2 Update Weaviate schema
  - Add category property (filterable)
  - Add doc_type property (filterable)
  - Add classification_status property (filterable)
  - _Requirements: 7.3, 7.4_

- [x] 8.3 Write property test for metadata persistence
  - **Property 17: Metadata Persistence**
  - **Validates: Requirements 8.2**

## 9. Integrate Classification into Ingestion Pipeline

- [x] 9.1 Modify PDF ingestion flow
  - Call ClassificationPipeline after PDF upload in `tools/ingest.py`
  - Store classification results in document metadata
  - Pass metadata to chunking and embedding steps
  - Note: Current ingestion uses CADLikeGate but doesn't store 4-category classification
  - _Requirements: 8.1, 8.2_

- [x] 9.2 Write property test for pipeline auto-classification
  - **Property 16: Pipeline Auto-Classification**
  - **Validates: Requirements 8.1**

- [x] 9.3 Add classification logging
  - Log classification decisions with confidence scores
  - Log guardrail triggers
  - Log fallback activations
  - _Requirements: 8.3_

## 10. Checkpoint - Ensure All Backend Tests Pass

- [x] 10. Checkpoint





  - Ensure all tests pass, ask the user if questions arise.

## 11. Implement Streamlit UI - Document Explorer

- [x] 11.1 Update Document Explorer tree view
  - Update existing `streamlit_app/components/classification_browser.py` for 4-category taxonomy
  - Create tree structure with 4 main category groups (ENGINEERING_DESIGN, VENDOR_EQUIPMENT, etc.)
  - Implement category expansion to show doc_types
  - Implement doc_type expansion to show files
  - Show classification status badges (classified, pending, needs_review)
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x] 11.2 Implement document preview
  - Show document preview when file is clicked
  - Display document metadata (category, doc_type, confidence)
  - Add button to trigger re-classification
  - _Requirements: 9.4, 9.6_

## 12. Implement Streamlit UI - Deep Search

- [x] 12.1 Create Deep Search tab
  - Add separate "Deep Search" tab in Streamlit app
  - Create search bar for keyword input
  - Add dropdown filters for category and doc_type
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 12.2 Implement search results display
  - Show results grouped by category
  - Display file name, doc_type, occurrence count
  - Add "View" button for each result
  - _Requirements: 10.4, 10.5_

- [x] 12.3 Implement PDF viewer integration
  - Open PDF at first keyword occurrence page when "View" clicked
  - Highlight keyword in PDF viewer if possible
  - _Requirements: 10.6_

## 13. Final Checkpoint - Ensure All Tests Pass

- [x] 13. Final Checkpoint





  - Ensure all tests pass, ask the user if questions arise.
