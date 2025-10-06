"""
Citation-Aware Retriever - Phase 1 RAG Pipeline

Integrates all Phase 1 components for accurate citation retrieval:
1. Document retrieval (existing hybrid retriever)
2. Page-level reranking within documents
3. Snippet extraction for context
4. Citation assembly with doc_id, page, score, and highlighted snippets

This is the main entry point for Phase 1 RAG queries.

Usage:
    retriever = CitationRetriever()
    results = retriever.search_with_citations(
        query="What is the operating pressure?",
        top_k_docs=3,
        top_k_pages_per_doc=2
    )

    for result in results:
        print(f"Document: {result.doc_id}")
        print(f"Page: {result.page}")
        print(f"Score: {result.score}")
        print(f"Snippets: {result.snippets}")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# Import core components
try:
    from app.rag.page_reranker import PageReranker, get_page_reranker
    from app.rag.snippet_extractor import (
        Snippet,
        SnippetExtractor,
        get_snippet_extractor,
    )

    _components_available = True
except ImportError as e:
    logger.error(f"Failed to import core RAG components: {e}")
    _components_available = False

# Import config
try:
    from app.config import get_config

    _pipeline_config = get_config()
except ImportError:
    _pipeline_config = None
    logger.warning("Config not available, using defaults")


@dataclass
class CitationResult:
    """
    A single citation result with page-level accuracy

    Attributes:
        doc_id: Document identifier
        page: Page number (1-indexed)
        score: Relevance score (0.0 - 1.0)
        page_text: Full text of the cited page
        snippets: List of relevant text snippets with highlighting
        metadata: Additional metadata (doc title, path, etc.)
        rank: Rank in results (1-indexed)
    """

    doc_id: str
    page: int
    score: float
    page_text: str
    snippets: List[Snippet] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "doc_id": self.doc_id,
            "page": self.page,
            "score": self.score,
            "rank": self.rank,
            "snippets": [
                {
                    "text": s.text,
                    "highlighted_text": s.highlighted_text,
                    "score": s.score,
                    "matched_keywords": list(s.matched_keywords),
                }
                for s in self.snippets
            ],
            "metadata": self.metadata,
        }

    def format_citation(self, include_snippets: bool = True) -> str:
        """
        Format as human-readable citation

        Args:
            include_snippets: Whether to include snippet text

        Returns:
            Formatted citation string
        """
        doc_name = self.metadata.get("doc_name", self.doc_id)

        citation = (
            f"[{self.rank}] {doc_name}, Page {self.page} (Score: {self.score:.2%})"
        )

        if include_snippets and self.snippets:
            citation += "\n\nRelevant excerpts:"
            for i, snippet in enumerate(self.snippets, 1):
                citation += f"\n  {i}. {snippet.highlighted_text}"

        return citation


@dataclass
class SearchConfig:
    """Configuration for citation-aware search"""

    # Document retrieval
    top_k_docs: int = 5  # Number of documents to retrieve

    # Page-level reranking
    top_k_pages_per_doc: int = 3  # Pages to extract per document
    min_page_score: float = 0.0  # Minimum BM25 score for pages

    # Snippet extraction
    max_snippets_per_page: int = 3  # Snippets per page
    snippet_context_size: int = 200  # Characters of context
    highlight_keywords: bool = True  # Highlight keywords in snippets

    # Final results
    max_total_citations: int = 10  # Maximum citations to return

    # Deduplication
    deduplicate_pages: bool = True  # Remove duplicate page citations

    # NEW: Citation Validation (CiteFix-lite)
    enable_validation: bool = False  # Feature flag for validation
    validation_level: int = 2  # 1=basic, 2=text, 3=semantic
    min_confidence_threshold: float = 0.7  # Minimum confidence to pass
    filter_invalid_citations: bool = False  # Remove invalid citations


class CitationRetriever:
    """
    Main retriever for Phase 1 with page-level citations

    This class orchestrates:
    1. Document candidates (from existing indexes or doc list)
    2. Page-level reranking within each document
    3. Snippet extraction from top pages
    4. Assembly of citation results
    """

    def __init__(
        self,
        page_reranker: Optional[PageReranker] = None,
        snippet_extractor: Optional[SnippetExtractor] = None,
        config: Optional[SearchConfig] = None,
    ):
        """
        Initialize CitationRetriever

        Args:
            page_reranker: PageReranker instance (uses singleton if None)
            snippet_extractor: SnippetExtractor instance (uses singleton if None)
            config: Search configuration
        """
        if not _components_available:
            raise RuntimeError(
                "Core RAG components not available. "
                "Please ensure page_reranker and snippet_extractor are installed."
            )

        self.page_reranker = page_reranker or get_page_reranker()
        self.snippet_extractor = snippet_extractor or get_snippet_extractor()
        self.config = config or SearchConfig()
        self.validator = None  # Lazy load CitationValidator

        logger.info(
            "CitationRetriever initialized with page-level reranking and snippet extraction"
        )

    def search_with_citations(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        config_override: Optional[SearchConfig] = None,
    ) -> List[CitationResult]:
        """
        Search with page-level citations

        Args:
            query: Search query
            doc_ids: List of document IDs to search within (if None, uses all docs)
            config_override: Override default configuration

        Returns:
            List of CitationResult objects, ranked by relevance
        """
        config = config_override or self.config

        if not query:
            logger.warning("Empty query provided")
            return []

        logger.info(f"Citation search for: '{query}'")
        logger.info(f"Searching {len(doc_ids) if doc_ids else 'all'} document(s)")

        # Step 1: Get document candidates
        if doc_ids is None:
            # If no doc_ids provided, we need to get them from somewhere
            # For Phase 1, we'll load from page index
            doc_ids = self._get_all_doc_ids()

        if not doc_ids:
            logger.warning("No documents to search")
            return []

        # Limit to top_k_docs if specified
        if len(doc_ids) > config.top_k_docs:
            logger.info(f"Limiting search to top {config.top_k_docs} documents")
            doc_ids = doc_ids[: config.top_k_docs]

        # Step 2: For each document, rank pages
        all_citations = []

        for doc_id in doc_ids:
            doc_citations = self._process_document(
                query=query,
                doc_id=doc_id,
                config=config,
            )
            all_citations.extend(doc_citations)

        # Step 3: Sort all citations by score
        all_citations.sort(key=lambda c: c.score, reverse=True)

        # Step 4: Deduplicate if requested
        if config.deduplicate_pages:
            all_citations = self._deduplicate_citations(all_citations)

        # Step 5: Limit to max_total_citations
        all_citations = all_citations[: config.max_total_citations]

        # Step 6: Validate citations (if enabled)
        if config.enable_validation:
            all_citations = self._validate_citations(all_citations, query, config)

        # Step 7: Assign ranks
        for rank, citation in enumerate(all_citations, 1):
            citation.rank = rank

        logger.info(f"Found {len(all_citations)} citations for query")

        return all_citations

    def search_in_document(
        self,
        query: str,
        doc_id: str,
        config_override: Optional[SearchConfig] = None,
    ) -> List[CitationResult]:
        """
        Search within a single document with page-level citations

        Args:
            query: Search query
            doc_id: Document ID to search within
            config_override: Override default configuration

        Returns:
            List of CitationResult objects for this document
        """
        config = config_override or self.config

        citations = self._process_document(query, doc_id, config)

        # Assign ranks
        for rank, citation in enumerate(citations, 1):
            citation.rank = rank

        return citations

    def _process_document(
        self,
        query: str,
        doc_id: str,
        config: SearchConfig,
    ) -> List[CitationResult]:
        """
        Process a single document: rank pages and extract snippets

        Args:
            query: Search query
            doc_id: Document ID
            config: Search configuration

        Returns:
            List of CitationResult objects for this document
        """
        # Rank pages in this document
        try:
            ranked_pages = self.page_reranker.rank_pages_for_doc(
                query=query,
                doc_id=doc_id,
                top_k=config.top_k_pages_per_doc,
                min_score=config.min_page_score,
            )
        except Exception as e:
            logger.error(f"Failed to rank pages for doc {doc_id}: {e}")
            return []

        if not ranked_pages:
            logger.debug(f"No relevant pages found in document {doc_id}")
            return []

        logger.debug(f"Found {len(ranked_pages)} relevant pages in {doc_id}")

        # Extract snippets from each page
        citations = []

        for page_num, page_score in ranked_pages:
            citation = self._create_citation(
                query=query,
                doc_id=doc_id,
                page=page_num,
                page_score=page_score,
                config=config,
            )

            if citation:
                citations.append(citation)

        return citations

    def _create_citation(
        self,
        query: str,
        doc_id: str,
        page: int,
        page_score: float,
        config: SearchConfig,
    ) -> Optional[CitationResult]:
        """
        Create a citation result for a specific page

        Args:
            query: Search query
            doc_id: Document ID
            page: Page number
            page_score: BM25 score for this page
            config: Search configuration

        Returns:
            CitationResult or None if page not found
        """
        # Get page text
        try:
            page_text = self.page_reranker.get_page_text(doc_id, page)
        except Exception as e:
            logger.error(f"Failed to get page text for {doc_id} page {page}: {e}")
            return None

        if not page_text:
            logger.debug(f"No text found for {doc_id} page {page}")
            return None

        # Extract snippets
        try:
            snippets = self.snippet_extractor.extract_snippets(
                text=page_text,
                query=query,
                max_snippets=config.max_snippets_per_page,
                highlight=config.highlight_keywords,
            )
        except Exception as e:
            logger.error(f"Failed to extract snippets: {e}")
            snippets = []

        # Get metadata
        metadata = self._get_page_metadata(doc_id, page)

        # Create citation
        citation = CitationResult(
            doc_id=doc_id,
            page=page,
            score=page_score,
            page_text=page_text,
            snippets=snippets,
            metadata=metadata,
        )

        return citation

    def _get_all_doc_ids(self) -> List[str]:
        """
        Get all document IDs from page index

        Returns:
            List of document IDs
        """
        try:
            # Load from page index
            import pickle

            if _pipeline_config:
                index_path = _pipeline_config.page_bm25_index_path
            else:
                index_path = Path("artifacts/ingestion_production/page_bm25_index.pkl")

            if not index_path.exists():
                logger.warning(f"Page index not found: {index_path}")
                return []

            with open(index_path, "rb") as f:
                data = pickle.load(f)

            # Get unique doc_ids
            doc_ids = sorted(set(data["doc_ids"]))

            logger.info(f"Loaded {len(doc_ids)} document IDs from page index")

            return doc_ids

        except Exception as e:
            logger.error(f"Failed to load doc_ids: {e}")
            return []

    def _get_page_metadata(self, doc_id: str, page: int) -> Dict[str, Any]:
        """
        Get metadata for a page

        Args:
            doc_id: Document ID
            page: Page number

        Returns:
            Metadata dictionary
        """
        # TODO: Load from page_metadata.json or doc_metadata.json
        # For now, return basic metadata
        return {
            "doc_id": doc_id,
            "page": page,
            "doc_name": self._extract_doc_name(doc_id),
        }

    def _extract_doc_name(self, doc_id: str) -> str:
        """
        Extract human-readable document name from doc_id

        Args:
            doc_id: Document ID

        Returns:
            Document name
        """
        # doc_id format: DOCID_<category>_<name>_<hash>
        # Extract the meaningful part
        parts = doc_id.split("_")
        if len(parts) > 2:
            # Skip DOCID and hash, join the rest
            name_parts = parts[1:-1]
            return "_".join(name_parts)
        return doc_id

    def _deduplicate_citations(
        self, citations: List[CitationResult]
    ) -> List[CitationResult]:
        """
        Remove duplicate page citations

        If the same (doc_id, page) appears multiple times, keep the one with higher score.

        Args:
            citations: List of citations

        Returns:
            Deduplicated list
        """
        seen = {}  # (doc_id, page) -> CitationResult

        for citation in citations:
            key = (citation.doc_id, citation.page)

            if key not in seen or citation.score > seen[key].score:
                seen[key] = citation

        # Return in original score order
        result = list(seen.values())
        result.sort(key=lambda c: c.score, reverse=True)

        return result

    def _validate_citations(
        self,
        citations: List[CitationResult],
        query: Optional[str],
        config: SearchConfig,
    ) -> List[CitationResult]:
        """
        Validate citations and attach validation results to metadata

        Args:
            citations: List of citations to validate
            query: Original search query
            config: Search configuration

        Returns:
            Validated (and optionally filtered) citations
        """
        # Lazy load validator
        if self.validator is None:
            from app.rag.citation_validator import CitationValidator

            self.validator = CitationValidator(
                validation_level=config.validation_level,
                min_confidence_threshold=config.min_confidence_threshold,
            )
            logger.info("CitationValidator loaded for validation")

        validated_citations = []

        for citation in citations:
            # Validate (pass primitives, not CitationResult object)
            validation_result = self.validator.validate(
                doc_id=citation.doc_id,
                page=citation.page,
                page_text=citation.page_text,
                snippets=citation.snippets,
                query=query,
            )

            # Store validation in metadata (not as field to avoid circular dependency)
            citation.metadata["validation"] = validation_result.to_dict()

            # Filter if configured and citation is invalid
            if config.filter_invalid_citations and not validation_result.is_valid:
                logger.warning(
                    f"Filtered invalid citation: {citation.doc_id} page {citation.page}, "
                    f"confidence={validation_result.confidence:.2%}, "
                    f"errors={len(validation_result.errors)}"
                )
                continue

            validated_citations.append(citation)

        logger.info(
            f"Validated {len(citations)} citations: "
            f"{len(validated_citations)} passed, "
            f"{len(citations) - len(validated_citations)} filtered"
        )

        return validated_citations


# Singleton instance
_citation_retriever_instance = None


def get_citation_retriever() -> CitationRetriever:
    """
    Get singleton CitationRetriever instance

    Returns:
        CitationRetriever instance
    """
    global _citation_retriever_instance

    if _citation_retriever_instance is None:
        _citation_retriever_instance = CitationRetriever()

    return _citation_retriever_instance
