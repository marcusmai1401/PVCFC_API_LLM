"""
Query Classification Module - Smart Hybrid Approach
Classifies queries as P&ID vs Technical Document queries using 3-stage pipeline
"""
import hashlib
import re
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger
from sklearn.metrics.pairwise import cosine_similarity

from app.services.embedding_enhanced import EmbeddingService
from app.services.llm_client import get_llm_client


class HybridQueryClassifier:
    """
    3-stage query classification:
    Stage 1: Fast pattern matching (10-50ms) - handles obvious cases
    Stage 2: Embedding similarity (50-200ms) - semantic understanding
    Stage 3: LLM reasoning (300-800ms) - complex/ambiguous cases
    """

    def __init__(self):
        """Initialize classifier with examples and services"""
        self.embedding_service = None
        self.llm_client = None
        self.cache = {}  # Query hash -> classification result
        self.stats = {"pattern": 0, "embedding": 0, "llm": 0, "cache_hit": 0}

        # Example queries for embedding similarity
        self.examples = {
            "pid": [
                "Where is valve 04-FIC-2035 located?",
                "Which line connects pump P-101 to tank T-201?",
                "Find instrument MYLP 04504 on the P&ID",
                "Show me the location of pressure transmitter PT-123",
                "What equipment is connected to line 2-HC-001?",
                "Locate tag 04-PSV-2001 on the diagram",
                "Where is the control valve in the cooling water system?",
                "Which P&ID drawing shows equipment E-101?",
                "Find all instruments on sheet P&ID-001",
                "What is the tag number for the inlet valve?",
            ],
            "technical_doc": [
                "According to the manual, what is the rated pressure?",
                "What are the alarm setpoints for lubricating oil pressure?",
                "What is the 100% operating speed in RPM?",
                "According to specification, what is the design temperature?",
                "What is the normal operating range for the gear unit?",
                "What maintenance interval is specified in the manual?",
                "What are the trip setpoints for the turbine?",
                "According to the datasheet, what is the rated capacity?",
                "What is the specified lubricating oil pressure for normal operation?",
                "What are the expected performance curves for the compressor?",
                "What is the design pressure according to the O&M manual?",
                "What cooling water flow rate is specified?",
            ],
        }

        self.example_embeddings = None  # Lazy-loaded
        logger.info("HybridQueryClassifier initialized")

    def classify(self, query: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Classify query using 3-stage pipeline

        Args:
            query: User query string
            tags: Optional list of detected equipment tags

        Returns:
            {
                "type": "pid" | "technical_doc" | "ambiguous",
                "confidence": 0.0-1.0,
                "method": "pattern" | "embedding" | "llm" | "cache",
                "reasoning": "explanation",
                "scores": {"pid": 0.x, "technical_doc": 0.y}
            }
        """
        if not query or not query.strip():
            return self._default_result()

        # Check cache first
        cache_key = self._get_cache_key(query, tags)
        if cache_key in self.cache:
            self.stats["cache_hit"] += 1
            result = self.cache[cache_key].copy()
            result["method"] = "cache"
            return result

        # Stage 1: Fast pattern matching
        pattern_result = self._fast_pattern_check(query, tags)
        if pattern_result["confidence"] >= 0.90:
            self.stats["pattern"] += 1
            self.cache[cache_key] = pattern_result
            logger.info(
                f"✓ Fast path: {pattern_result['type']} (confidence={pattern_result['confidence']})"
            )
            return pattern_result

        # Stage 2: Embedding similarity
        try:
            embedding_result = self._embedding_classify(query, tags)
            if embedding_result["confidence"] >= 0.75:
                self.stats["embedding"] += 1
                self.cache[cache_key] = embedding_result
                logger.info(
                    f"✓ Smart path: {embedding_result['type']} (confidence={embedding_result['confidence']})"
                )
                return embedding_result
        except Exception as e:
            logger.warning(f"Embedding classification failed: {e}")

        # Stage 3: LLM reasoning (for ambiguous cases)
        try:
            # Check if LLM is enabled via feature flag
            if self._is_llm_enabled():
                llm_result = self._llm_classify(query, tags)
                self.stats["llm"] += 1
                self.cache[cache_key] = llm_result
                logger.info(
                    f"✓ Deep path: {llm_result['type']} (confidence={llm_result['confidence']})"
                )
                return llm_result
            else:
                # LLM disabled, return embedding result with lower confidence
                embedding_result["confidence"] *= 0.8
                embedding_result["reasoning"] += " (LLM disabled, moderate confidence)"
                self.cache[cache_key] = embedding_result
                return embedding_result
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, using embedding result")
            self.cache[cache_key] = embedding_result
            return embedding_result

    def _fast_pattern_check(
        self, query: str, tags: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Stage 1: Lightning-fast pattern checks for obvious cases"""
        q = query.lower()

        # OBVIOUS P&ID: Location query + equipment tag
        if tags and any(
            w in q for w in ["where", "locate", "location", "find", "show", "nằm ở"]
        ):
            return {
                "type": "pid",
                "confidence": 0.95,
                "method": "fast_pattern",
                "reasoning": "Location query with equipment tag",
                "scores": {"pid": 0.95, "technical_doc": 0.05},
            }

        # OBVIOUS TECH DOC: "according to" + "manual/specification"
        if re.search(
            r"according to\s+(the\s+)?(manual|specification|datasheet|o&m|operation|maintenance)",
            q,
        ):
            return {
                "type": "technical_doc",
                "confidence": 0.95,
                "method": "fast_pattern",
                "reasoning": "Explicit document reference (according to manual/spec)",
                "scores": {"pid": 0.05, "technical_doc": 0.95},
            }

        # OBVIOUS TECH DOC: Equipment model + specification query
        if re.search(r"\b(HCD|HTR|HTC|gear\s+unit)\d{0,5}\b", q, re.I) and re.search(
            r"(setpoint|alarm|trip|shutdown|pressure|temperature|speed|rpm|flow|capacity)",
            q,
        ):
            return {
                "type": "technical_doc",
                "confidence": 0.92,
                "method": "fast_pattern",
                "reasoning": "Equipment model + specification value query",
                "scores": {"pid": 0.08, "technical_doc": 0.92},
            }

        # OBVIOUS TECH DOC: Performance/specification query patterns
        if re.search(
            r"(performance\s+curve|data\s*sheet|rated\s+(capacity|pressure|speed))",
            q,
            re.I,
        ):
            return {
                "type": "technical_doc",
                "confidence": 0.90,
                "method": "fast_pattern",
                "reasoning": "Performance/specification document query",
                "scores": {"pid": 0.10, "technical_doc": 0.90},
            }

        # FALSE POSITIVE FILTER: "IN RPM", "IN barG" are NOT P&ID tags!
        if re.search(r"\bin\s+(rpm|barg|bar|psi|kpa|kg|m3|mm|°c|mw)", q, re.I):
            return {
                "type": "technical_doc",
                "confidence": 0.88,
                "method": "fast_pattern",
                "reasoning": "Unit indicator pattern (in RPM/bar/etc - not P&ID tag)",
                "scores": {"pid": 0.12, "technical_doc": 0.88},
            }

        # Not obvious enough, move to next stage
        return {
            "confidence": 0.5,
            "method": "inconclusive",
            "reasoning": "Pattern matching inconclusive",
        }

    def _embedding_classify(
        self, query: str, tags: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Stage 2: Classify by semantic similarity to examples"""
        # Lazy-load embedding service
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService()

        # Lazy-load example embeddings
        if self.example_embeddings is None:
            self._precompute_embeddings()

        # Embed query
        query_emb = self.embedding_service.embed_query(query)

        # Compute similarity to each type
        scores = {}
        for type_name, example_embs in self.example_embeddings.items():
            # Cosine similarity to all examples
            similarities = cosine_similarity(query_emb.reshape(1, -1), example_embs)[0]

            # Use top-3 average
            top_k = sorted(similarities, reverse=True)[:3]
            scores[type_name] = float(np.mean(top_k))

        # Determine winner
        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        # Boost confidence if tags detected and type is P&ID
        if tags and best_type == "pid":
            confidence = min(1.0, confidence + 0.15)

        # If too close, mark ambiguous
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[0] - sorted_scores[1] < 0.10:
            best_type = "ambiguous"
            confidence = 0.5

        return {
            "type": best_type,
            "confidence": round(confidence, 2),
            "method": "embedding",
            "scores": {k: round(v, 2) for k, v in scores.items()},
            "reasoning": f"Most similar to {best_type} example queries",
        }

    def _llm_classify(self, query: str, tags: Optional[List[str]]) -> Dict[str, Any]:
        """Stage 3: Use LLM reasoning for complex/ambiguous cases"""
        # Lazy-load LLM client
        if self.llm_client is None:
            self.llm_client = get_llm_client(tier="light")  # Use Gemini Flash

        # Build classification prompt
        tags_str = ", ".join(tags) if tags else "None"
        prompt = f"""You are a query classifier for an industrial document RAG system.

We have two types of queries:
1. **P&ID Queries**: Questions about equipment location, piping connections, instrument positions on P&ID diagrams
   - Examples: "Where is valve 04-FIC-2035?", "Which line connects pump P-101 to tank T-201?"

2. **Technical Document Queries**: Questions about specifications, operating parameters, maintenance procedures from manuals/datasheets
   - Examples: "What is the rated pressure?", "According to manual, what are the alarm setpoints?"

Query: "{query}"
Detected tags: {tags_str}

Analyze this query and respond with ONLY a JSON object (no other text):
{{
  "type": "pid" OR "technical_doc" OR "ambiguous",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Think step by step:
1. What is the user asking for? (location/visual vs specification/value)
2. Are there equipment tags suggesting P&ID? (e.g., 04-FIC-2035)
3. Are there document references? (e.g., "according to manual")
4. What type of answer would they expect? (diagram location vs numerical value)"""

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=150,  # Low temp for consistency
            )

            # Parse JSON response
            import json

            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            result = json.loads(content)

            # Validate result
            if "type" not in result or result["type"] not in [
                "pid",
                "technical_doc",
                "ambiguous",
            ]:
                raise ValueError(f"Invalid type in LLM response: {result.get('type')}")

            # Add metadata
            result["method"] = "llm"
            result["confidence"] = round(float(result.get("confidence", 0.7)), 2)

            return result

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            # Fallback to default
            return {
                "type": "ambiguous",
                "confidence": 0.5,
                "method": "llm_failed",
                "reasoning": f"LLM classification error: {str(e)[:100]}",
            }

    def _precompute_embeddings(self):
        """Pre-embed all example queries"""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService()

        self.example_embeddings = {}
        for type_name, examples in self.examples.items():
            embs = self.embedding_service.embed_texts(examples)
            self.example_embeddings[type_name] = embs

        logger.info(f"Precomputed embeddings for {len(self.examples)} example types")

    def _get_cache_key(self, query: str, tags: Optional[List[str]]) -> str:
        """Generate cache key from query and tags"""
        tags_str = ",".join(sorted(tags)) if tags else ""
        combined = f"{query.lower().strip()}|{tags_str}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _is_llm_enabled(self) -> bool:
        """Check if LLM classification is enabled via feature flag"""
        try:
            import os

            return os.getenv("HYBRID_CLASSIFIER_USE_LLM", "true").lower() in [
                "true",
                "1",
                "yes",
            ]
        except Exception:
            return True  # Default enabled

    def _default_result(self) -> Dict[str, Any]:
        """Return default result for empty/invalid queries"""
        return {
            "type": "ambiguous",
            "confidence": 0.5,
            "method": "default",
            "reasoning": "Empty or invalid query",
            "scores": {"pid": 0.5, "technical_doc": 0.5},
        }

    def get_stats(self) -> Dict[str, int]:
        """Return classification statistics"""
        return self.stats.copy()

    def clear_cache(self):
        """Clear classification cache"""
        self.cache.clear()
        logger.info("Classification cache cleared")


# Singleton instance
_classifier_instance = None


def get_query_classifier() -> HybridQueryClassifier:
    """Get or create singleton classifier instance"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = HybridQueryClassifier()
    return _classifier_instance
