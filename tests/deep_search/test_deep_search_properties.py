"""
Property-based tests for Deep Search Service

**Feature: intelligent-classification-deep-search**

Tests:
- Property 11: Deep Search Completeness
- Property 12: Deep Search No-LLM Constraint
- Property 13: Search Result Metadata
- Property 14: Filter Correctness
- Property 15: Result Grouping
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Optional
from dataclasses import dataclass

from app.services.deep_search import (
    DeepSearchService,
    DeepSearchResult,
    DeepSearchResponse,
)
from app.classification.taxonomy import DocumentCategory, get_taxonomy


# =============================================================================
# Mock OpenSearch Client for Testing
# =============================================================================

class MockOpenSearchClient:
    """Mock OpenSearch client for property testing"""
    
    def __init__(self, documents: List[Dict] = None):
        """
        Initialize with test documents
        
        Args:
            documents: List of document dicts with fields:
                - doc_id: str
                - filename: str
                - category: str
                - doc_type: str
                - page_number: int
                - text: str
        """
        self.documents = documents or []
        self.last_query = None
    
    def search(self, index: str, body: dict) -> dict:
        """Mock search that returns aggregated results based on documents"""
        self.last_query = body
        
        # Extract keyword from query
        keyword = ""
        must_clauses = body.get("query", {}).get("bool", {}).get("must", [])
        for clause in must_clauses:
            if "multi_match" in clause:
                keyword = clause["multi_match"].get("query", "").lower()
                break
        
        # Extract filters
        filter_clauses = body.get("query", {}).get("bool", {}).get("filter", [])
        category_filter = None
        doc_type_filter = None
        for f in filter_clauses:
            if "term" in f:
                if "metadata.category" in f["term"]:
                    category_filter = f["term"]["metadata.category"]
                if "metadata.doc_type" in f["term"]:
                    doc_type_filter = f["term"]["metadata.doc_type"]
        
        # Filter documents by keyword and filters
        matching_docs = {}
        for doc in self.documents:
            text = doc.get("text", "").lower()
            if keyword and keyword not in text:
                continue
            
            if category_filter and doc.get("category") != category_filter:
                continue
            
            if doc_type_filter and doc.get("doc_type") != doc_type_filter:
                continue
            
            doc_id = doc.get("doc_id", "")
            if doc_id not in matching_docs:
                matching_docs[doc_id] = {
                    "doc": doc,
                    "count": 0,
                    "first_page": doc.get("page_number", 1)
                }
            matching_docs[doc_id]["count"] += 1
            matching_docs[doc_id]["first_page"] = min(
                matching_docs[doc_id]["first_page"],
                doc.get("page_number", 1)
            )
        
        # Build aggregation response
        buckets = []
        for doc_id, info in matching_docs.items():
            doc = info["doc"]
            buckets.append({
                "key": doc_id,
                "occurrence_count": {"value": info["count"]},
                "doc_info": {
                    "hits": {
                        "hits": [{
                            "_source": {
                                "metadata": {
                                    "doc_id": doc_id,
                                    "filename": doc.get("filename", ""),
                                    "category": doc.get("category", "UNCATEGORIZED"),
                                    "doc_type": doc.get("doc_type", "Unknown"),
                                    "page_number": info["first_page"]
                                },
                                "text": doc.get("text", "")
                            }
                        }]
                    }
                }
            })
        
        return {
            "aggregations": {
                "unique_documents": {
                    "buckets": buckets
                }
            }
        }


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid categories
valid_category_strategy = st.sampled_from([
    DocumentCategory.ENGINEERING_DESIGN.value,
    DocumentCategory.VENDOR_EQUIPMENT.value,
    DocumentCategory.OPERATIONS_MAINTENANCE.value,
    DocumentCategory.SAFETY_MANAGEMENT.value,
    DocumentCategory.UNCATEGORIZED.value,
])

# Valid doc_types per category
DOC_TYPES_BY_CATEGORY = {
    DocumentCategory.ENGINEERING_DESIGN.value: ["P&ID", "Drawing", "Technical Data"],
    DocumentCategory.VENDOR_EQUIPMENT.value: ["Datasheet", "Material Partlist", "Vendor Manual"],
    DocumentCategory.OPERATIONS_MAINTENANCE.value: [
        "Operation Instruction", "Maintenance Instruction",
        "Maintenance History", "Inventory"
    ],
    DocumentCategory.SAFETY_MANAGEMENT.value: ["MOC", "RCA", "Pictures"],
    DocumentCategory.UNCATEGORIZED.value: ["Unknown"],
}


@st.composite
def document_strategy(draw, keyword: str = None):
    """Generate a test document"""
    category = draw(valid_category_strategy)
    doc_types = DOC_TYPES_BY_CATEGORY.get(category, ["Unknown"])
    doc_type = draw(st.sampled_from(doc_types))
    
    doc_id = draw(st.text(alphabet="abcdef0123456789", min_size=8, max_size=16))
    filename = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=5, max_size=20)) + ".pdf"
    page_number = draw(st.integers(min_value=1, max_value=100))
    
    # Generate text, optionally including keyword
    base_text = draw(st.text(min_size=10, max_size=200))
    if keyword:
        # Insert keyword at random position
        pos = draw(st.integers(min_value=0, max_value=len(base_text)))
        text = base_text[:pos] + " " + keyword + " " + base_text[pos:]
    else:
        text = base_text
    
    return {
        "doc_id": doc_id,
        "filename": filename,
        "category": category,
        "doc_type": doc_type,
        "page_number": page_number,
        "text": text
    }


@st.composite
def documents_with_keyword_strategy(draw, min_docs=1, max_docs=20):
    """Generate a list of documents, some containing a keyword"""
    keyword = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10))
    assume(len(keyword.strip()) >= 3)
    
    num_with_keyword = draw(st.integers(min_value=1, max_value=max_docs))
    num_without_keyword = draw(st.integers(min_value=0, max_value=max_docs - num_with_keyword))
    
    docs_with = [draw(document_strategy(keyword=keyword)) for _ in range(num_with_keyword)]
    docs_without = [draw(document_strategy(keyword=None)) for _ in range(num_without_keyword)]
    
    # Filter out docs that accidentally contain keyword
    docs_without = [d for d in docs_without if keyword.lower() not in d["text"].lower()]
    
    return {
        "keyword": keyword,
        "docs_with_keyword": docs_with,
        "docs_without_keyword": docs_without,
        "all_docs": docs_with + docs_without
    }


# =============================================================================
# Property 11: Deep Search Completeness
# =============================================================================

class TestProperty11DeepSearchCompleteness:
    """
    **Feature: intelligent-classification-deep-search, Property 11: Deep Search Completeness**
    
    *For any* keyword search, the result SHALL contain all unique documents in the index
    that contain the keyword, with no duplicates (unique doc_ids).
    
    **Validates: Requirements 5.2, 5.4**
    """
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_search_returns_all_matching_documents(self, data):
        """
        Property: Search must return all documents containing the keyword
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        docs_with_keyword = data["docs_with_keyword"]
        
        # Create mock client with test documents
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        # Execute search
        response = service.search(keyword=keyword)
        
        # Get unique doc_ids from docs that should match
        expected_doc_ids = set(d["doc_id"] for d in docs_with_keyword)
        actual_doc_ids = set(r.doc_id for r in response.results)
        
        # All expected docs should be in results
        assert expected_doc_ids == actual_doc_ids, (
            f"Missing docs: {expected_doc_ids - actual_doc_ids}, "
            f"Extra docs: {actual_doc_ids - expected_doc_ids}"
        )
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_search_returns_no_duplicates(self, data):
        """
        Property: Search results must have unique doc_ids (no duplicates)
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        doc_ids = [r.doc_id for r in response.results]
        assert len(doc_ids) == len(set(doc_ids)), (
            f"Duplicate doc_ids found: {doc_ids}"
        )
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_total_documents_matches_results_count(self, data):
        """
        Property: total_documents must equal len(results)
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        assert response.total_documents == len(response.results), (
            f"total_documents ({response.total_documents}) != len(results) ({len(response.results)})"
        )


# =============================================================================
# Property 12: Deep Search No-LLM Constraint
# =============================================================================

class TestProperty12DeepSearchNoLLMConstraint:
    """
    **Feature: intelligent-classification-deep-search, Property 12: Deep Search No-LLM Constraint**
    
    *For any* deep search request, the system SHALL NOT invoke any LLM or vector similarity search;
    only keyword-based OpenSearch queries are allowed.
    
    **Validates: Requirements 5.6**
    """
    
    @given(keyword=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=20))
    @settings(max_examples=100)
    def test_query_uses_multi_match_not_vector(self, keyword):
        """
        Property: Query must use multi_match, not vector similarity
        """
        assume(len(keyword.strip()) >= 3)
        
        client = MockOpenSearchClient(documents=[])
        service = DeepSearchService(opensearch_client=client)
        
        service.search(keyword=keyword)
        
        query = client.last_query
        assert query is not None, "No query was executed"
        
        # Check that query uses multi_match
        must_clauses = query.get("query", {}).get("bool", {}).get("must", [])
        has_multi_match = any("multi_match" in clause for clause in must_clauses)
        assert has_multi_match, "Query must use multi_match"
        
        # Check that query does NOT use knn or script_score (vector search)
        query_str = str(query)
        assert "knn" not in query_str.lower(), "Query must not use knn (vector search)"
        assert "script_score" not in query_str.lower(), "Query must not use script_score"
        assert "embedding" not in query_str.lower(), "Query must not use embeddings"
    
    @given(keyword=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=20))
    @settings(max_examples=100)
    def test_query_uses_phrase_prefix(self, keyword):
        """
        Property: Query must use phrase_prefix type for multi_match
        """
        assume(len(keyword.strip()) >= 3)
        
        client = MockOpenSearchClient(documents=[])
        service = DeepSearchService(opensearch_client=client)
        
        service.search(keyword=keyword)
        
        query = client.last_query
        must_clauses = query.get("query", {}).get("bool", {}).get("must", [])
        
        for clause in must_clauses:
            if "multi_match" in clause:
                match_type = clause["multi_match"].get("type")
                assert match_type == "phrase_prefix", (
                    f"multi_match type must be 'phrase_prefix', got '{match_type}'"
                )


# =============================================================================
# Property 13: Search Result Metadata
# =============================================================================

class TestProperty13SearchResultMetadata:
    """
    **Feature: intelligent-classification-deep-search, Property 13: Search Result Metadata**
    
    *For any* document in deep search results, the result SHALL include:
    doc_id, filename, category, doc_type, and occurrence_count (all non-null).
    
    **Validates: Requirements 5.7**
    """
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_all_results_have_required_fields(self, data):
        """
        Property: Every result must have all required metadata fields
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        for result in response.results:
            # Check doc_id
            assert result.doc_id is not None, "doc_id must not be None"
            assert isinstance(result.doc_id, str), "doc_id must be a string"
            assert len(result.doc_id) > 0, "doc_id must not be empty"
            
            # Check filename
            assert result.filename is not None, "filename must not be None"
            assert isinstance(result.filename, str), "filename must be a string"
            
            # Check category
            assert result.category is not None, "category must not be None"
            assert isinstance(result.category, str), "category must be a string"
            
            # Check doc_type
            assert result.doc_type is not None, "doc_type must not be None"
            assert isinstance(result.doc_type, str), "doc_type must be a string"
            
            # Check occurrence_count
            assert result.occurrence_count is not None, "occurrence_count must not be None"
            assert isinstance(result.occurrence_count, int), "occurrence_count must be an int"
            assert result.occurrence_count >= 1, "occurrence_count must be >= 1"
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_result_to_dict_contains_all_fields(self, data):
        """
        Property: to_dict() must include all required fields
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        required_fields = {"doc_id", "filename", "category", "doc_type", "occurrence_count", "first_page", "snippet"}
        
        for result in response.results:
            result_dict = result.to_dict()
            assert set(result_dict.keys()) == required_fields, (
                f"Missing fields: {required_fields - set(result_dict.keys())}"
            )


# =============================================================================
# Property 14: Filter Correctness
# =============================================================================

class TestProperty14FilterCorrectness:
    """
    **Feature: intelligent-classification-deep-search, Property 14: Filter Correctness**
    
    *For any* deep search with category_filter or doc_type_filter applied,
    all returned documents SHALL match the specified filter criteria.
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    
    @given(data=documents_with_keyword_strategy(), category=valid_category_strategy)
    @settings(max_examples=100)
    def test_category_filter_returns_only_matching_category(self, data, category):
        """
        Property: When category_filter is applied, all results must have that category
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword, category_filter=category)
        
        for result in response.results:
            assert result.category == category, (
                f"Result category '{result.category}' does not match filter '{category}'"
            )
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_doc_type_filter_returns_only_matching_doc_type(self, data):
        """
        Property: When doc_type_filter is applied, all results must have that doc_type
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        # Pick a random doc_type from the test data
        if not all_docs:
            return
        
        doc_type = all_docs[0]["doc_type"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword, doc_type_filter=doc_type)
        
        for result in response.results:
            assert result.doc_type == doc_type, (
                f"Result doc_type '{result.doc_type}' does not match filter '{doc_type}'"
            )
    
    @given(data=documents_with_keyword_strategy(), category=valid_category_strategy)
    @settings(max_examples=100)
    def test_combined_filters_return_matching_results(self, data, category):
        """
        Property: When both filters are applied, all results must match both criteria
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        doc_types = DOC_TYPES_BY_CATEGORY.get(category, ["Unknown"])
        doc_type = doc_types[0]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(
            keyword=keyword,
            category_filter=category,
            doc_type_filter=doc_type
        )
        
        for result in response.results:
            assert result.category == category, (
                f"Result category '{result.category}' does not match filter '{category}'"
            )
            assert result.doc_type == doc_type, (
                f"Result doc_type '{result.doc_type}' does not match filter '{doc_type}'"
            )
    
    @given(keyword=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10))
    @settings(max_examples=100)
    def test_filter_is_applied_in_query(self, keyword):
        """
        Property: Filters must be included in the OpenSearch query
        """
        assume(len(keyword.strip()) >= 3)
        
        client = MockOpenSearchClient(documents=[])
        service = DeepSearchService(opensearch_client=client)
        
        category = DocumentCategory.ENGINEERING_DESIGN.value
        doc_type = "P&ID"
        
        service.search(keyword=keyword, category_filter=category, doc_type_filter=doc_type)
        
        query = client.last_query
        filter_clauses = query.get("query", {}).get("bool", {}).get("filter", [])
        
        # Check category filter is present
        category_filter_found = any(
            f.get("term", {}).get("metadata.category") == category
            for f in filter_clauses
        )
        assert category_filter_found, "Category filter not found in query"
        
        # Check doc_type filter is present
        doc_type_filter_found = any(
            f.get("term", {}).get("metadata.doc_type") == doc_type
            for f in filter_clauses
        )
        assert doc_type_filter_found, "Doc_type filter not found in query"


# =============================================================================
# Property 15: Result Grouping
# =============================================================================

class TestProperty15ResultGrouping:
    """
    **Feature: intelligent-classification-deep-search, Property 15: Result Grouping**
    
    *For any* deep search response, results_by_category SHALL contain all results
    grouped by their category, with no document appearing in multiple category groups.
    
    **Validates: Requirements 6.4**
    """
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_all_results_appear_in_grouped_results(self, data):
        """
        Property: Every result in results must appear in exactly one category group
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        # Collect all doc_ids from grouped results
        grouped_doc_ids = set()
        for category, results in response.results_by_category.items():
            for result in results:
                grouped_doc_ids.add(result.doc_id)
        
        # Collect all doc_ids from flat results
        flat_doc_ids = set(r.doc_id for r in response.results)
        
        assert grouped_doc_ids == flat_doc_ids, (
            f"Grouped results don't match flat results. "
            f"Missing: {flat_doc_ids - grouped_doc_ids}, "
            f"Extra: {grouped_doc_ids - flat_doc_ids}"
        )
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_no_document_in_multiple_groups(self, data):
        """
        Property: No document should appear in multiple category groups
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        seen_doc_ids = set()
        for category, results in response.results_by_category.items():
            for result in results:
                assert result.doc_id not in seen_doc_ids, (
                    f"Document '{result.doc_id}' appears in multiple category groups"
                )
                seen_doc_ids.add(result.doc_id)
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_results_grouped_by_correct_category(self, data):
        """
        Property: Each result must be in the group matching its category
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        for category, results in response.results_by_category.items():
            for result in results:
                assert result.category == category, (
                    f"Result with category '{result.category}' "
                    f"is in wrong group '{category}'"
                )
    
    @given(data=documents_with_keyword_strategy())
    @settings(max_examples=100)
    def test_grouped_count_equals_total(self, data):
        """
        Property: Sum of grouped results must equal total_documents
        """
        keyword = data["keyword"]
        all_docs = data["all_docs"]
        
        client = MockOpenSearchClient(documents=all_docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword=keyword)
        
        grouped_count = sum(
            len(results) for results in response.results_by_category.values()
        )
        
        assert grouped_count == response.total_documents, (
            f"Grouped count ({grouped_count}) != total_documents ({response.total_documents})"
        )


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestDeepSearchEdgeCases:
    """Additional edge case tests for deep search"""
    
    def test_empty_keyword_returns_empty_results(self):
        """Empty keyword should return empty results"""
        client = MockOpenSearchClient(documents=[])
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword="")
        
        assert response.total_documents == 0
        assert len(response.results) == 0
        assert len(response.results_by_category) == 0
    
    def test_whitespace_keyword_returns_empty_results(self):
        """Whitespace-only keyword should return empty results"""
        client = MockOpenSearchClient(documents=[])
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword="   ")
        
        assert response.total_documents == 0
        assert len(response.results) == 0
    
    def test_no_matching_documents_returns_empty(self):
        """Search with no matches should return empty results"""
        docs = [
            {"doc_id": "1", "filename": "test.pdf", "category": "ENGINEERING_DESIGN",
             "doc_type": "P&ID", "page_number": 1, "text": "hello world"}
        ]
        client = MockOpenSearchClient(documents=docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword="nonexistent")
        
        assert response.total_documents == 0
        assert len(response.results) == 0
    
    def test_response_to_dict_structure(self):
        """Response to_dict should have correct structure"""
        docs = [
            {"doc_id": "1", "filename": "test.pdf", "category": "ENGINEERING_DESIGN",
             "doc_type": "P&ID", "page_number": 1, "text": "test keyword here"}
        ]
        client = MockOpenSearchClient(documents=docs)
        service = DeepSearchService(opensearch_client=client)
        
        response = service.search(keyword="keyword")
        response_dict = response.to_dict()
        
        assert "query" in response_dict
        assert "total_documents" in response_dict
        assert "results" in response_dict
        assert "results_by_category" in response_dict
        assert response_dict["query"] == "keyword"
