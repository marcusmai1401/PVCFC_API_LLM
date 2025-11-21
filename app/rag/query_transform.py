"""
Query Transformation Module for RAG Pipeline
Handles query normalization, intent detection, HyDE generation, and filters
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from loguru import logger

from app.rag.query_classification import get_query_classifier
from app.services.llm_client import get_llm_client


class QueryIntent(Enum):
    """Types of query intents"""

    ASK = "ask"  # Question answering
    LOCATE = "locate"  # Entity location
    REPORT = "report"  # Report generation
    EXPLAIN = "explain"  # Explanation request
    UNKNOWN = "unknown"  # Cannot determine


@dataclass
class QueryFilters:
    """Filters to apply during retrieval"""

    doc_categories: Optional[List[str]] = None  # e.g., ["datasheet", "pid"]
    doc_ids: Optional[List[str]] = None  # Specific document IDs
    date_range: Optional[tuple] = None  # (start_date, end_date)
    metadata: Optional[Dict[str, Any]] = None  # Additional filters


@dataclass
class TransformedQuery:
    """Result of query transformation"""

    original: str
    normalized: str
    intent: QueryIntent
    filters: QueryFilters
    hyde_queries: Optional[List[str]] = None
    language: str = "en"
    metadata: Dict[str, Any] = None
    # NEW: Tag enhancement fields for Week 2
    detected_tags: Optional[List[str]] = None  # Equipment tags found in query
    expanded_query: Optional[str] = None  # Query with tag variants for better recall


class QueryTransformer:
    """Transforms and enhances user queries for RAG pipeline"""

    def __init__(
        self,
        enable_hyde: bool = True,
        hyde_count: int = 2,
        remove_stopwords: bool = True,
    ):
        """
        Initialize QueryTransformer

        Args:
            enable_hyde: Whether to generate hypothetical documents
            hyde_count: Number of HyDE variations to generate
            remove_stopwords: Whether to remove stopwords
        """
        self.enable_hyde = enable_hyde
        self.hyde_count = hyde_count
        self.remove_stopwords = remove_stopwords

        # Common stopwords for technical queries (minimal set)
        self.stopwords = {
            "the",
            "is",
            "at",
            "which",
            "on",
            "a",
            "an",
            "as",
            "are",
            "was",
            "were",
            "been",
            "be",
            "will",
            "would",
            "could",
        }

        # Intent detection patterns
        self.intent_patterns = {
            QueryIntent.LOCATE: [
                r"where.*(?:is|are|located)",
                r"\bfind\b",  # Any mention of 'find'
                r"\blocate\b",
                r"\blocation\b",  # Any mention of 'location'
                r"position.*(?:of|in)",
                r"page.*(?:number|containing)",
            ],
            QueryIntent.REPORT: [
                r"(?:create|generate|make).*report",
                r"summarize.*(?:all|everything)",
                r"compile.*information",
                r"comprehensive.*(?:overview|summary)",
            ],
            QueryIntent.EXPLAIN: [
                r"explain",
                r"how.*(?:does|do|to|work)",
                r"why.*(?:is|are|does|do)",
            ],
            QueryIntent.ASK: [
                r"what.*(?:pressure|temperature|flow|specification|operating)",
                r"what.*(?:is|are).*(?:the|specification)",
                r"(?:maximum|minimum|normal).*(?:value|range|temperature|pressure)",
                r"operating.*(?:condition|parameter)",
                r"specification.*(?:of|for)",
            ],
        }

    def transform(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        language: str = "en",
        query_type_override: Optional[str] = None,  # NEW: manual override
    ) -> TransformedQuery:
        """
        Transform user query through normalization, intent detection, and enhancement

        Args:
            query: Original user query
            filters: Optional filters to apply
            language: Query language (en/vi)

        Returns:
            TransformedQuery object with all transformations
        """
        logger.info(f"Transforming query: {query[:100]}...")

        # Normalize query
        normalized = self.normalize_query(query)

        # If language is not English, attempt translation to English for retrieval
        translated_from = None
        if language and language.lower() != "en":
            try:
                from app.services.llm_client import get_llm_client

                translator = get_llm_client(tier="light")
                # Smart Query Expansion: Context-aware keyword injection for better recall
                translation_prompt = (
                    f"Translate the following user query to English for technical document retrieval.\n"
                    f"EXPANSION STRATEGY (Apply based on query intent):\n"
                    f"- IF query asks for QUANTITATIVE DATA (capacity, pressure, flow, dimensions, efficiency...): "
                    f"APPEND keywords: 'datasheet', 'performance curve', 'specification', 'technical data', 'drawing'.\n"
                    f"- IF query asks for PROCESS/LOCATION (connection, flow path, location...): "
                    f"APPEND keywords: 'P&ID', 'piping diagram', 'layout', 'schematic'.\n"
                    f"- IF query asks for PROCEDURES (how to start, maintenance, steps...): "
                    f"APPEND keywords: 'manual', 'procedure', 'instruction', 'guideline'.\n"
                    f"- OTHERWISE: Keep translation literal.\n\n"
                    f"Original Query: {query}\n"
                    f"English Translation (with expansion):"
                )
                translation = translator.generate(
                    prompt=translation_prompt,
                    system_prompt="You are a precise technical translator with expertise in query expansion for document retrieval. Output only the translated text with relevant keywords appended.",
                    temperature=0.0,
                    max_tokens=4096,
                )
                if translation and getattr(translation, "content", None):
                    content = (translation.content or "").strip()
                    # Guard: ignore known error/fallback messages from LLM client
                    lower_c = content.lower()
                    if (
                        not content
                        or "error generating response" in lower_c
                        or "i apologize" in lower_c
                    ):
                        logger.warning(
                            "Translation returned error/fallback text; using original query for retrieval"
                        )
                    else:
                        normalized = self.normalize_query(content)
                        translated_from = language
            except Exception as e:
                logger.warning(f"Query translation failed: {e}. Using original query.")

        # Detect intent
        intent = self.detect_intent(normalized)

        # Parse filters
        query_filters = self.parse_filters(filters) if filters else QueryFilters()

        # Generate HyDE if enabled
        hyde_queries = None
        if self.enable_hyde and intent in [QueryIntent.ASK, QueryIntent.EXPLAIN]:
            hyde_queries = self.generate_hyde(query, intent, language)

        # NEW Week 2: Detect and expand equipment tags
        detected_tags = self.detect_equipment_tags(query)
        expanded_query = None
        if detected_tags:
            expanded_query = self.expand_tag_query(normalized, detected_tags)
            logger.info(
                f"Detected {len(detected_tags)} equipment tag(s): {detected_tags}"
            )

        # NEW Phase 1: Smart query classification (P&ID vs Technical Doc)
        query_classification = None
        try:
            # Check if classifier is enabled
            import os

            classifier_enabled = os.getenv(
                "HYBRID_CLASSIFIER_ENABLED", "true"
            ).lower() in ["true", "1", "yes"]

            if classifier_enabled:
                classifier = get_query_classifier()

                # Use override if provided, otherwise classify
                if query_type_override:
                    logger.info(f"Query type override: {query_type_override}")
                    query_classification = {
                        "type": query_type_override,
                        "confidence": 1.0,
                        "method": "manual_override",
                        "reasoning": "User-specified query type",
                    }
                else:
                    query_classification = classifier.classify(query, detected_tags)
                    logger.info(
                        f"Query classified as '{query_classification['type']}' "
                        f"(confidence={query_classification['confidence']}, method={query_classification['method']})"
                    )
        except Exception as e:
            logger.warning(
                f"Query classification failed: {e}, continuing without classification"
            )

        result = TransformedQuery(
            original=query,
            normalized=normalized,
            intent=intent,
            filters=query_filters,
            hyde_queries=hyde_queries,
            language=language,
            metadata={
                "word_count": len(query.split()),
                "has_technical_terms": self._has_technical_terms(query),
                "translated_from": translated_from,
                "has_tags": bool(detected_tags),
                "tag_count": len(detected_tags) if detected_tags else 0,
                "query_classification": query_classification,  # NEW: classification result
            },
            detected_tags=detected_tags,
            expanded_query=expanded_query,
        )

        logger.info(
            f"Transformation complete. Intent: {intent.value}, "
            f"HyDE: {len(hyde_queries) if hyde_queries else 0}, "
            f"Tags: {len(detected_tags) if detected_tags else 0}"
        )

        return result

    def normalize_query(self, query: str) -> str:
        """
        Normalize query text

        Args:
            query: Original query text

        Returns:
            Normalized query
        """
        # Convert to lowercase
        normalized = query.lower()

        # Remove extra whitespace
        normalized = " ".join(normalized.split())

        # Remove special characters but keep technical ones
        normalized = re.sub(r"[^\w\s\-\.\,\?\@\#\/]", " ", normalized)

        # Optionally remove stopwords (careful with technical context)
        if self.remove_stopwords:
            words = normalized.split()
            # Remove stopwords but keep words longer than 2 chars
            words = [w for w in words if w not in self.stopwords]
            normalized = " ".join(words)

        return normalized.strip()

    def detect_intent(self, query: str) -> QueryIntent:
        """
        Detect the intent of the query

        Priority order:
        1. Explicit location keywords -> LOCATE
        2. Report/summary keywords -> REPORT
        3. Explain/how/why keywords -> EXPLAIN
        4. Question patterns (what/when/etc) -> ASK
        5. Equipment tags alone -> ASK (not LOCATE)
        6. Default -> ASK

        Args:
            query: Normalized query text

        Returns:
            Detected QueryIntent
        """
        query_lower = query.lower()

        # Step 1: Check for explicit LOCATE keywords (highest priority)
        # Only return LOCATE if user explicitly asks for location
        for pattern in self.intent_patterns[QueryIntent.LOCATE]:
            if re.search(pattern, query_lower):
                return QueryIntent.LOCATE

        # Step 2: Check for REPORT keywords
        for pattern in self.intent_patterns[QueryIntent.REPORT]:
            if re.search(pattern, query_lower):
                return QueryIntent.REPORT

        # Step 3: Handle 'how/why' early: quantitative -> ASK, else EXPLAIN
        if query_lower.startswith(("how", "why")):
            ask_terms = [
                "much",
                "many",
                "long",
                "high",
                "low",
                "far",
                "often",
                "fast",
                "slow",
                "big",
                "small",
            ]
            if any(term in query_lower.split() for term in ask_terms):
                return (
                    QueryIntent.ASK
                )  # e.g., "how much pressure", "how long does it take"
            return QueryIntent.EXPLAIN

        # Step 4: Check for EXPLAIN keywords (fallback)
        for pattern in self.intent_patterns[QueryIntent.EXPLAIN]:
            if re.search(pattern, query_lower):
                return QueryIntent.EXPLAIN

        # Step 5: Check for ASK patterns
        for pattern in self.intent_patterns[QueryIntent.ASK]:
            if re.search(pattern, query_lower):
                return QueryIntent.ASK

        # Step 5: Handle question words
        if any(query_lower.startswith(q) for q in ["what", "when", "which", "who"]):
            return QueryIntent.ASK

        if query_lower.startswith("where"):
            return QueryIntent.LOCATE

        # Step 6: Equipment tags WITHOUT location keywords -> ASK
        # This is the key change for Task 2.2
        if re.search(r"\b[A-Z]{1,}[-]?\d{2,}[A-Z]?\b", query.upper()):
            # Equipment tag found, but no location keywords
            # User likely asking about the equipment's properties, not location
            return QueryIntent.ASK

        # Step 7: Default to ASK for all other queries
        return QueryIntent.ASK

    def generate_hyde(
        self, query: str, intent: QueryIntent, language: str = "en"
    ) -> List[str]:
        """
        Generate Hypothetical Document Embeddings (HyDE) with retry logic

        Args:
            query: Original query
            intent: Detected intent
            language: Target language

        Returns:
            List of hypothetical document snippets
        """
        import time

        # Retry logic for rate limits and overload
        max_retries = 3
        base_delay = 1.0  # Start with 1 second

        for attempt in range(max_retries):
            try:
                # Use light tier for HyDE generation (fast and cheap)
                client = get_llm_client(tier="light")

                # Prompt for HyDE generation
                prompt = self._build_hyde_prompt(query, intent, language)

                if not prompt:  # Skip for LOCATE/REPORT intents
                    return []

                response = client.generate(
                    prompt=prompt, temperature=0.7, max_tokens=1024
                )

                # Guard against empty/None responses
                content = getattr(response, "content", None)
                if not content or not isinstance(content, str) or not content.strip():
                    logger.warning(
                        "HyDE generation returned empty content; skipping HyDE for this query"
                    )
                    return []

                # Guard: ignore known error/fallback messages from LLM client
                lower_c = content.lower()
                if "error generating response" in lower_c or "i apologize" in lower_c:
                    logger.warning(
                        "HyDE generation returned error/fallback text; skipping HyDE for this query"
                    )
                    return []

                # Parse response into separate hypothetical documents
                hyde_queries = self._parse_hyde_response(content)

                if hyde_queries:
                    logger.info(
                        f"HyDE generated {len(hyde_queries)} queries successfully"
                    )

                return hyde_queries[: self.hyde_count]

            except Exception as e:
                error_str = str(e)

                # Check for specific error types
                if "503" in error_str or "overloaded" in error_str.lower():
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)  # Exponential backoff
                        logger.info(
                            f"Model overloaded, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.warning(
                            f"HyDE failed after {max_retries} attempts: Model overloaded"
                        )

                elif "429" in error_str or "quota" in error_str.lower():
                    logger.warning(f"Rate limit reached: {e}")
                    logger.info(
                        "Consider: 1) Upgrading to paid tier, 2) Using cache, 3) Reducing HyDE frequency"
                    )

                elif "400" in error_str or "invalid" in error_str.lower():
                    logger.error(f"Invalid request to Gemini: {e}")
                    break  # Don't retry on bad requests

                else:
                    logger.warning(f"HyDE generation failed: {e}")

                return []  # Fallback to normal search

        return []

    def parse_filters(self, filters: Dict[str, Any]) -> QueryFilters:
        """
        Parse and validate filters

        Args:
            filters: Raw filter dictionary

        Returns:
            QueryFilters object
        """
        return QueryFilters(
            doc_categories=filters.get("doc_category", filters.get("doc_categories")),
            doc_ids=filters.get("doc_id", filters.get("doc_ids")),
            date_range=filters.get("date_range"),
            metadata=filters.get("metadata", {}),
        )

    def _has_technical_terms(self, query: str) -> bool:
        """Check if query contains technical terms"""
        technical_patterns = [
            r"\b\d+\s*(?:bar|psi|kpa|mpa)\b",  # Pressure units
            r"\b\d+\s*(?:°c|°f|k|celsius|fahrenheit)\b",  # Temperature
            r"\b(?:flow|pressure|temperature|voltage|current)\b",  # Parameters
            r"\b[A-Z]{1,}[-]?\d{2,}[A-Z]?\b",  # Equipment tags (KT06101, V-202, P-301A)
            r"\bvalve\b",  # Equipment types
            r"\bpump\b",
            r"\bcompressor\b",
        ]

        query_lower = query.lower()
        return any(
            re.search(pattern, query_lower, re.IGNORECASE)
            for pattern in technical_patterns
        )

    def _build_hyde_prompt(self, query: str, intent: QueryIntent, language: str) -> str:
        """Build prompt for HyDE generation"""
        language_hint = "in English"  # documents are primarily in English
        if intent == QueryIntent.ASK:
            return f"""Given the technical question: "{query}"

Generate {self.hyde_count} different hypothetical document passages that would contain the answer.
Each passage should be 2-3 sentences and contain specific technical details.
Write the passages {language_hint}.

Format: One passage per line, no numbering.

Passages:"""

        elif intent == QueryIntent.EXPLAIN:
            return f"""Given the explanation request: "{query}"

Generate {self.hyde_count} different hypothetical document passages that would explain this concept.
Each passage should be 2-3 sentences with technical context.
Write the passages {language_hint}.

Format: One passage per line, no numbering.

Passages:"""

        else:
            return ""

    def _parse_hyde_response(self, response: str) -> List[str]:
        """Parse HyDE response into separate documents"""
        if not response:
            return []
        # Split by newlines and filter empty lines
        lines = [line.strip() for line in str(response).split("\n") if line.strip()]

        # Remove numbering if present (1., 2., etc.)
        cleaned = []
        for line in lines:
            # Remove leading numbers and dots
            line = re.sub(r"^\d+[\.\)]\s*", "", line)
            if line and len(line) > 20:  # Minimum length check
                cleaned.append(line)

        return cleaned

    def detect_equipment_tags(self, query: str) -> Optional[List[str]]:
        """
        Detect equipment tags in query (Week 2: Day 1-2)

        Detects patterns like:
        - 06-TE-0256 (full prefix with dashes)
        - 06TE0256 (no dashes)
        - TE-0256 (partial, no prefix)
        - P-101A (with suffix)

        Args:
            query: User query text

        Returns:
            List of detected equipment tags, or None if no tags found
        """
        # Equipment tag patterns (ordered by specificity)
        patterns = [
            # Full tag with optional prefix: 06-TE-0256, 06-TE-0256A/B
            r"\b(\d{2,3}[-_]?[A-Z]{1,3}[-_]?\d{3,5}[A-Z]?(?:/[A-Z])?)\b",
            # Partial tag without prefix: TE-0256, PI-0103A
            r"\b([A-Z]{1,3}[-_]?\d{3,5}[A-Z]?)\b",
            # Common equipment prefixes: P-101, V-303, E-404
            r"\b([PVETHKFC][-_]\d{2,5}[A-Z]?)\b",
        ]

        detected = set()  # Use set to avoid duplicates
        query_upper = query.upper()

        for pattern in patterns:
            matches = re.findall(pattern, query_upper)
            for match in matches:
                # Filter out false positives (too short, all letters, etc.)
                if len(match) >= 4 and re.search(
                    r"\d", match
                ):  # Must have at least one digit
                    # Normalize separators to dash
                    normalized = match.replace("_", "-")
                    detected.add(normalized)

        return sorted(list(detected)) if detected else None

    def expand_tag_query(self, normalized_query: str, detected_tags: List[str]) -> str:
        """
        Expand query with tag variants for better recall (Week 2: Day 3)

        For each tag like "06-TE-0256", generate variants:
        - 06-TE-0256 (original with dashes)
        - 06 TE 0256 (spaces)
        - 06TE0256 (no separators)
        - TE-0256 (partial, no prefix)
        - TE0256 (partial, no separators)

        Args:
            normalized_query: Normalized query text
            detected_tags: List of detected equipment tags

        Returns:
            Expanded query string with all tag variants
        """
        if not detected_tags:
            return normalized_query

        # Generate variants for each tag
        all_variants = []
        for tag in detected_tags:
            variants = self._generate_tag_variants(tag)
            all_variants.extend(variants)

        # Combine original query with tag variants
        # Format: "original_query (variant1 OR variant2 OR variant3 ...)"
        variants_str = " OR ".join(all_variants)
        expanded = f"{normalized_query} ({variants_str})"

        return expanded

    def _generate_tag_variants(self, tag: str) -> List[str]:
        """
        Generate all variants of an equipment tag for search expansion

        Examples:
        - Input: "06-TE-0256"
        - Output: ["06-TE-0256", "06 TE 0256", "06TE0256", "TE-0256", "TE0256"]

        Args:
            tag: Equipment tag (e.g., "06-TE-0256")

        Returns:
            List of tag variants
        """
        variants = set([tag])  # Start with original

        # Variant 1: Replace dashes/underscores with spaces
        space_variant = tag.replace("-", " ").replace("_", " ")
        variants.add(space_variant)

        # Variant 2: Remove all separators
        no_sep_variant = tag.replace("-", "").replace("_", "").replace(" ", "")
        variants.add(no_sep_variant)

        # Variant 3: Try to extract partial tag (remove prefix if present)
        # Pattern: "06-TE-0256" -> "TE-0256", "TE0256"
        prefix_match = re.match(r"^\d{2,3}[-_]?([A-Z]{1,3}[-_]?\d{3,5}[A-Z]?)", tag)
        if prefix_match:
            partial = prefix_match.group(1)
            variants.add(partial)
            variants.add(partial.replace("-", "").replace("_", ""))

        # Variant 4: Try to extract just the letters+numbers (most generic)
        # "06-TE-0256" -> "TE0256", "0256"
        letters_numbers = re.findall(r"[A-Z]+|\d+", tag)
        if len(letters_numbers) >= 2:
            # Combine letter prefix with last number group
            letter_parts = [p for p in letters_numbers if p.isalpha()]
            number_parts = [p for p in letters_numbers if p.isdigit()]
            if letter_parts and number_parts:
                generic = f"{letter_parts[-1]}{number_parts[-1]}"
                variants.add(generic)
                variants.add(f"{letter_parts[-1]}-{number_parts[-1]}")

        return sorted(list(variants))


# Convenience function
def transform_query(
    query: str, filters: Optional[Dict[str, Any]] = None, enable_hyde: bool = True
) -> TransformedQuery:
    """
    Transform a query using default settings

    Args:
        query: User query
        filters: Optional filters
        enable_hyde: Whether to generate HyDE

    Returns:
        TransformedQuery object
    """
    transformer = QueryTransformer(enable_hyde=enable_hyde)
    return transformer.transform(query, filters)
