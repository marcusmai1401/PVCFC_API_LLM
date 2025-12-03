# Requirements Document

## Introduction

Hệ thống PVCFC RAG v1.7.1 đã hoàn thiện khả năng hỏi đáp ngữ nghĩa (Semantic QA) và xử lý P&ID. Giai đoạn tiếp theo (v2.0) tập trung vào **Quản trị tri thức (Knowledge Management)** và **Tìm kiếm toàn diện (Exhaustive Search)**.

Feature này bao gồm 2 tính năng chính:
1. **Intelligent Auto-Classification**: Tự động phân loại tài liệu PDF vào taxonomy chuẩn hóa sử dụng Multimodal AI (Gemini 2.5 Flash)
2. **Deep Discovery Search**: Tìm kiếm keyword toàn diện không bị giới hạn bởi top_k của RAG

## Glossary

- **Taxonomy**: Hệ thống phân loại tài liệu theo 4 nhóm chính (ENGINEERING_DESIGN, VENDOR_EQUIPMENT, OPERATIONS_MAINTENANCE, SAFETY_MANAGEMENT)
- **CADLikeGate**: Module hiện tại dùng để phát hiện tài liệu P&ID/CAD-like qua vector features và regex
- **Adaptive Sampling**: Chiến lược lấy mẫu trang thông minh (Head/Body/Tail) để phân loại tài liệu dài
- **Deep Discovery Search**: Tìm kiếm keyword sử dụng OpenSearch Aggregation, trả về tất cả documents chứa keyword
- **Mixed Content**: Tài liệu có nội dung hỗn hợp (ví dụ: Manual có chèn hình P&ID)
- **Dominant Content Rule**: Quy tắc phân loại dựa trên loại nội dung chiếm đa số trong tài liệu
- **UNCATEGORIZED**: Category đặc biệt dành cho tài liệu không thể phân loại tự động do confidence thấp hoặc nội dung không rõ ràng
- **NEEDS_REVIEW**: Trạng thái đánh dấu tài liệu cần được con người xem xét và phân loại thủ công
- **Confidence Threshold**: Ngưỡng tin cậy tối thiểu (0.5) để chấp nhận kết quả phân loại AI

## Requirements

### Requirement 1: Document Taxonomy Structure

**User Story:** As a knowledge manager, I want documents to be classified into a standardized taxonomy, so that I can organize and navigate the document library efficiently.

#### Acceptance Criteria

1. THE Classification_System SHALL support exactly 4 main categories: ENGINEERING_DESIGN, VENDOR_EQUIPMENT, OPERATIONS_MAINTENANCE, SAFETY_MANAGEMENT
2. WHEN a document is classified THEN THE Classification_System SHALL assign both a category and a doc_type from the predefined taxonomy
3. THE Classification_System SHALL support the following doc_types per category:
   - ENGINEERING_DESIGN: P&ID, Drawing, Technical Data
   - VENDOR_EQUIPMENT: Datasheet, Material Partlist, Vendor Manual
   - OPERATIONS_MAINTENANCE: Operation Instruction, Maintenance Instruction, Maintenance History, Inventory
   - SAFETY_MANAGEMENT: MOC, RCA, Pictures

### Requirement 2: Adaptive Page Sampling

**User Story:** As a system architect, I want the classifier to sample pages intelligently, so that classification is accurate even for long documents with mixed content.

#### Acceptance Criteria

1. WHEN a PDF has 10 or fewer pages THEN THE Sampling_Strategy SHALL send all pages to the classifier
2. WHEN a PDF has more than 10 pages THEN THE Sampling_Strategy SHALL select exactly 10 representative pages using Head-Body-Tail strategy
3. THE Sampling_Strategy SHALL select Head pages as pages 1, 2, 3 to capture cover and table of contents
4. THE Sampling_Strategy SHALL select Tail pages as pages N-1, N to capture appendix and signatures
5. THE Sampling_Strategy SHALL select 5 Body pages distributed evenly across the middle section

### Requirement 3: P&ID Safety Guardrail

**User Story:** As a plant engineer, I want P&ID drawings to never be misclassified as regular documents, so that critical engineering documents are always correctly identified.

#### Acceptance Criteria

1. WHEN CADLikeGate scores a document with CAD_score >= 0.55 THEN THE Classification_System SHALL force-assign category as ENGINEERING_DESIGN and doc_type as P&ID
2. THE Classification_System SHALL apply code-based guardrail (CADLikeGate) before AI classification
3. WHEN CADLikeGate force-assigns P&ID THEN THE Classification_System SHALL skip AI classification for that document
4. THE Classification_System SHALL achieve 100% accuracy for P&ID classification with zero false negatives

### Requirement 4: AI-Powered Classification

**User Story:** As a document administrator, I want the system to use AI vision to understand document content, so that classification is accurate for complex documents.

#### Acceptance Criteria

1. WHEN CADLikeGate does not force-assign P&ID THEN THE Classification_System SHALL use Gemini 2.5 Flash for classification
2. THE AI_Classifier SHALL render sampled pages as images and send to Gemini 2.5 Flash
3. THE AI_Classifier SHALL apply Dominant Content Rule: classify based on the content type that appears in majority of sampled pages
4. WHEN text pages dominate over drawing pages THEN THE AI_Classifier SHALL classify as text-based document type (Manual/Report)
5. WHEN drawing pages dominate over text pages THEN THE AI_Classifier SHALL classify as drawing-based document type
6. THE AI_Classifier SHALL return structured output with category, doc_type, and confidence score
7. IF the AI_Classifier returns a confidence score below 0.5 OR cannot determine a dominant type THEN THE Classification_System SHALL assign category as 'UNCATEGORIZED' and status as 'NEEDS_REVIEW' for manual intervention

### Requirement 5: Deep Discovery Search Endpoint

**User Story:** As an auditor, I want to find all documents containing a specific keyword, so that I can perform comprehensive document reviews without missing any relevant files.

#### Acceptance Criteria

1. THE Search_System SHALL provide a new endpoint GET /api/search/documents for keyword-based document discovery
2. WHEN a user searches for a keyword THEN THE Search_System SHALL return all unique documents containing that keyword
3. THE Search_System SHALL use OpenSearch multi_match query with phrase_prefix on the text field
4. THE Search_System SHALL aggregate results by doc_id to return unique documents
5. THE Search_System SHALL support returning up to 10,000 document buckets
6. THE Search_System SHALL not use LLM or vector search for Deep Discovery Search
7. WHEN returning results THEN THE Search_System SHALL include document metadata (category, doc_type, occurrence_count)

### Requirement 6: Search Result Filtering

**User Story:** As a user, I want to filter search results by category or document type, so that I can narrow down results to relevant document groups.

#### Acceptance Criteria

1. THE Search_System SHALL support optional filter parameter for category
2. THE Search_System SHALL support optional filter parameter for doc_type
3. WHEN filters are applied THEN THE Search_System SHALL return only documents matching the filter criteria
4. THE Search_System SHALL return results grouped by category for easy navigation

### Requirement 7: Metadata Schema Update

**User Story:** As a system developer, I want document metadata to include classification fields, so that classification results are persisted and queryable.

#### Acceptance Criteria

1. THE Database_Schema SHALL include metadata.category field in OpenSearch index rag_chunks
2. THE Database_Schema SHALL include metadata.doc_type field in OpenSearch index rag_chunks
3. THE Database_Schema SHALL include metadata.category field in Weaviate collection
4. THE Database_Schema SHALL include metadata.doc_type field in Weaviate collection
5. THE System SHALL provide a migration script to update metadata for existing documents

### Requirement 8: Classification Pipeline Integration

**User Story:** As a system operator, I want classification to run automatically during ingestion, so that new documents are classified without manual intervention.

#### Acceptance Criteria

1. WHEN a new PDF is ingested THEN THE Ingestion_Pipeline SHALL automatically run classification
2. THE Ingestion_Pipeline SHALL store classification results (category, doc_type) in document metadata
3. THE Ingestion_Pipeline SHALL log classification decisions with confidence scores for audit
4. IF classification fails THEN THE Ingestion_Pipeline SHALL mark document as "needs_review" and continue processing

### Requirement 9: Document Explorer UI

**User Story:** As a user, I want a tree-view interface to browse documents by category, so that I can navigate the document library intuitively.

#### Acceptance Criteria

1. THE UI SHALL display a tree structure with 4 main category groups
2. THE UI SHALL allow expanding categories to show doc_types
3. THE UI SHALL allow expanding doc_types to show individual PDF files
4. WHEN a user clicks on a file THEN THE UI SHALL display document preview and metadata
5. THE UI SHALL show classification status for each document (classified, pending, needs_review)
6. THE UI SHALL provide a button to trigger auto-classification for unclassified documents

### Requirement 10: Deep Search UI

**User Story:** As a user, I want a dedicated search interface for keyword discovery, so that I can find all documents containing specific terms.

#### Acceptance Criteria

1. THE UI SHALL provide a separate "Deep Search" tab distinct from "Chat RAG"
2. THE UI SHALL include a search bar for keyword input
3. THE UI SHALL include dropdown filters for category and doc_type
4. WHEN displaying results THEN THE UI SHALL show file name, document type, keyword occurrence count, and view button
5. THE UI SHALL group search results by category
6. WHEN user clicks "View" THEN THE UI SHALL open the PDF at the page containing the first keyword occurrence
