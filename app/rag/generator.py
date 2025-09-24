"""
RAG Generator Module - Sprint 1.4
Generates answers with citations from retrieved documents
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult
from app.services.llm_client import get_llm_client


@dataclass
class Citation:
    """Citation for a piece of information"""

    doc_id: str
    source: str
    page: Optional[int] = None
    text_snippet: str = ""
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "page": self.page,
            "snippet": self.text_snippet[:100] + "..."
            if len(self.text_snippet) > 100
            else self.text_snippet,
            "score": round(self.relevance_score, 4),
        }


@dataclass
class GeneratedAnswer:
    """Generated answer with citations"""

    query: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": round(self.confidence, 2),
            "metadata": self.metadata,
            "generation_time_ms": round(self.generation_time_ms, 2),
        }


@dataclass
class GeneratorConfig:
    """Configuration for answer generation"""

    llm_tier: str = "standard"  # LLM tier to use
    max_context_length: int = 4000  # Max tokens for context
    max_answer_length: int = 500  # Max tokens for answer
    temperature: float = 0.3  # Lower = more focused
    include_citations: bool = True
    citation_style: str = "inline"  # inline, footnote, or separate
    min_confidence: float = 0.5  # Minimum confidence to return answer
    language: str = "en"
    prompt_template: Optional[str] = None

    # Fallback behavior
    allow_uncited_fallback: bool = (
        True  # Allow answering without citations if outside KB or LLM empty
    )
    general_answer_tier: str = (
        "light"  # Tier for generic answers when no context is available
    )

    # Advanced options
    use_chain_of_thought: bool = True  # Add reasoning steps
    verify_facts: bool = True  # Double-check facts against sources
    handle_contradictions: bool = True  # Handle conflicting information


class ResponseGenerator:
    """
    Generates answers from retrieved documents
    Handles citation tracking and answer formatting
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        """
        Initialize generator

        Args:
            config: Generator configuration
        """
        self.config = config or GeneratorConfig()
        self.llm_client = None
        self._init_llm()

        logger.info(f"RAG Generator initialized with tier: {self.config.llm_tier}")

    def _init_llm(self):
        """Initialize LLM client"""
        try:
            self.llm_client = get_llm_client(tier=self.config.llm_tier)
            logger.info("LLM client initialized for generation")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

    def generate(
        self,
        query: TransformedQuery,
        retrieved_docs: List[RetrievalResult],
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> GeneratedAnswer:
        """
        Generate answer from retrieved documents

        Args:
            query: Transformed query with intent
            retrieved_docs: Retrieved and ranked documents
            additional_context: Optional additional context

        Returns:
            Generated answer with citations
        """
        import time

        start_time = time.time()

        if not retrieved_docs:
            return self._generate_no_results_answer(query)

        try:
            # Prepare context from documents
            context, doc_mapping = self._prepare_context(retrieved_docs)

            # For bilingual support: use both original and normalized queries
            # normalized query is in English for matching with English docs
            # original query preserves the user's language for response
            is_translated = query.metadata and query.metadata.get("translated_from")
            generation_query = (
                query.normalized
            )  # Always use normalized for context matching
            original_query = query.original  # Keep original for language detection

            # Determine response language
            response_language = query.language if hasattr(query, "language") else "en"

            # Generate answer based on intent
            if query.intent == QueryIntent.ASK:
                answer, citations = self._generate_ask_answer_bilingual(
                    generation_query,
                    original_query,
                    context,
                    doc_mapping,
                    response_language,
                )
            elif query.intent == QueryIntent.EXPLAIN:
                # For simplicity, using same bilingual approach for EXPLAIN
                answer, citations = self._generate_ask_answer_bilingual(
                    generation_query,
                    original_query,
                    context,
                    doc_mapping,
                    response_language,
                )
            elif query.intent == QueryIntent.LOCATE:
                answer, citations = self._generate_locate_answer(
                    generation_query, retrieved_docs
                )
            elif query.intent == QueryIntent.REPORT:
                # For reports, also use bilingual approach
                answer, citations = self._generate_ask_answer_bilingual(
                    generation_query,
                    original_query,
                    context,
                    doc_mapping,
                    response_language,
                )
            else:
                # Default also uses bilingual
                answer, citations = self._generate_ask_answer_bilingual(
                    generation_query,
                    original_query,
                    context,
                    doc_mapping,
                    response_language,
                )

            # If the LLM returned an empty/too short answer, or an apology/error, fall back to a general answer
            fallback_used = False
            apology_markers = [
                "i apologize",
                "i couldn't generate",
                "error generating response",
                "xin lỗi",
                "không thể",
            ]
            if (not answer or len(answer.strip()) < 10) or any(
                m in (answer or "").lower() for m in apology_markers
            ):
                try:
                    # Use original query for general answer to maintain language consistency
                    answer, citations = self._generate_general_answer(query.original)
                    fallback_used = True
                except Exception as _:
                    # Keep original empty answer; will be handled by post-processing
                    pass

            # Calculate confidence
            confidence = self._calculate_confidence(
                answer if answer else "", citations, retrieved_docs
            )

            # Post-process answer
            final_answer = self._post_process_answer(answer, citations, confidence)

            generation_time = (time.time() - start_time) * 1000

            metadata_extra = {
                "intent": query.intent.value,
                "num_docs": len(retrieved_docs),
                "has_filters": bool(query.filters),
                "used_hyde": (len(query.hyde_queries) > 0)
                if query.hyde_queries
                else False,
            }
            if "fallback_used" in locals() and fallback_used:
                metadata_extra["uncited_fallback"] = True

            return GeneratedAnswer(
                query=query.original,
                answer=final_answer,
                citations=citations,
                confidence=confidence,
                metadata=metadata_extra,
                generation_time_ms=generation_time,
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return self._generate_error_answer(query, str(e))

    def _prepare_context(
        self, docs: List[RetrievalResult]
    ) -> Tuple[str, Dict[int, RetrievalResult]]:
        """
        Prepare context from retrieved documents

        Returns:
            (context_string, doc_id_mapping)
        """
        context_parts = []
        doc_mapping = {}

        for i, doc in enumerate(docs):
            # Truncate if needed
            text = doc.text
            if len(text) > 500:  # Limit each doc
                text = text[:500] + "..."

            # Add with clear separation
            context_parts.append(f"[Doc {i+1}] {text}")
            doc_mapping[i + 1] = doc

        # Join with clear separators
        context = "\n---\n".join(context_parts)

        # Truncate total context if too long
        if len(context) > self.config.max_context_length:
            context = context[: self.config.max_context_length] + "..."

        return context, doc_mapping

    def _call_llm_with_fallback(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call primary LLM, and if empty/apology/error, retry with light-tier model."""
        # First try with configured client
        response = self.llm_client.generate(
            prompt=prompt, temperature=temperature, max_tokens=max_tokens
        )
        content = (
            response.content if response and isinstance(response.content, str) else ""
        )
        content_l = (content or "").lower()
        # If not usable, try light-tier
        if (
            (not content.strip())
            or ("i apologize" in content_l)
            or ("error generating response" in content_l)
        ):
            try:
                fallback_client = get_llm_client(tier="light")
                resp2 = fallback_client.generate(
                    prompt=prompt,
                    temperature=max(0.2, temperature),
                    max_tokens=max_tokens,
                )
                if resp2 and isinstance(resp2.content, str) and resp2.content.strip():
                    return resp2.content.strip()
            except Exception:
                pass
        return (content or "").strip()

    def _generate_ask_answer_bilingual(
        self,
        english_query: str,
        original_query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        language: str = "en",
    ) -> Tuple[str, List[Citation]]:
        """Generate answer for ASK intent with bilingual support

        Args:
            english_query: Query in English (for matching with English documents)
            original_query: Query in original language (for determining response language)
            context: Document context (in English)
            doc_mapping: Mapping of doc numbers to results
            language: Target response language
        """

        # If Vietnamese, create bilingual prompt
        if language == "vi":
            prompt = f"""Answer the following question based on the provided technical documents.

Original Question (Vietnamese): {original_query}
English Translation: {english_query}

Context (from English documents):
{context}

Instructions:
1. Answer in Vietnamese (Tiếng Việt) based on the English context
2. Start with a direct 1-2 sentence answer to the question
3. Include specific technical details from the documents
4. Cite sources using [Doc X] format inline with your statements
5. If the context doesn't contain the answer, say so clearly in Vietnamese
6. DO NOT just list citations without answering the question

Vietnamese Answer:"""
        else:
            # English or default
            prompt = f"""Answer the following question based on the provided technical documents.

Question: {english_query}

Context:
{context}

Instructions:
1. IMPORTANT: Start with a direct 1-2 sentence answer to the question
2. Then provide supporting details from the documents
3. Cite sources using [Doc X] format inline with your statements
4. If the context doesn't contain the answer, say so clearly
5. DO NOT just list citations without answering the question

Answer:"""

        # Call LLM with fallback to light-tier if needed
        answer = self._call_llm_with_fallback(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        # Extract citations
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_ask_answer(
        self,
        query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        language: str = "en",
    ) -> Tuple[str, List[Citation]]:
        """Generate answer for ASK intent"""

        # Add language instruction if Vietnamese is needed
        lang_instruction = ""
        if language == "vi":
            lang_instruction = "\n7. IMPORTANT: Respond in Vietnamese (Tiếng Việt) but keep citation markers [Doc X] as is"

        prompt = f"""Answer the following question based on the provided technical documents.

Question: {query}

Context:
{context}

Instructions:
1. IMPORTANT: Start with a direct 1-2 sentence answer to the question
2. Then provide supporting details from the documents
3. Cite sources using [Doc X] format inline with your statements
4. If the context doesn't contain the answer, say so clearly
5. DO NOT just list citations without answering the question
6. Use information from the context to provide specific technical details{lang_instruction}

Answer:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        answer = (
            response.content
            if response
            and isinstance(response.content, str)
            and response.content.strip()
            else ""
        )

        # Extract citations
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_explain_answer(
        self, query: str, context: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate explanation for EXPLAIN intent"""

        prompt = f"""Explain the following technical concept based on the provided documents.
Provide a clear, educational explanation with citations.

Topic: {query}

Context:
{context}

Instructions:
1. Start with a clear definition
2. Explain key principles and mechanisms
3. Include relevant specifications or examples
4. Cite sources using [Doc X] format
5. Use technical terms appropriately

Explanation:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        answer = response.content if response and response.content else ""
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_locate_answer(
        self, query: str, docs: List[RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate answer for LOCATE intent (finding equipment/documents)"""

        # Extract equipment tags or document references
        found_items = []
        citations = []

        for doc in docs[:5]:  # Check top 5 docs
            # Look for equipment tags (e.g., KT06101)
            tags = re.findall(r"\b[A-Z]{1,}[-]?\d{2,}[A-Z]?\b", doc.text.upper())
            if tags:
                for tag in tags:
                    found_items.append(
                        {
                            "tag": tag,
                            "source": doc.source,
                            "doc_id": doc.doc_id,
                            "context": doc.text[:200],
                        }
                    )

                    citations.append(
                        Citation(
                            doc_id=doc.doc_id,
                            source=doc.source,
                            page=doc.page,
                            text_snippet=doc.text[:100],
                            relevance_score=doc.score,
                        )
                    )

        if found_items:
            answer = f"Found the following related items:\n"
            for item in found_items[:3]:
                answer += f"\n• {item['tag']} - Located in {item['source']}"
        else:
            answer = f"Could not locate specific equipment or documents matching '{query}'. Please check the reference format."

        return answer, citations

    def _generate_report_answer(
        self, query: str, context: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate report/summary for REPORT intent"""

        prompt = f"""Generate a comprehensive report on the following topic based on the technical documents.
Structure the information clearly with sections.

Topic: {query}

Context:
{context}

Instructions:
1. Organize information into clear sections
2. Include key specifications and parameters
3. Summarize important findings
4. Cite sources using [Doc X] format
5. Highlight any critical values or requirements

Report:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length * 2,  # Allow longer reports
        )

        answer = response.content if response and response.content else ""
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_default_answer(
        self, query: str, context: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate default answer when intent is unclear"""

        prompt = f"""Provide relevant information for the following query based on the technical documents.

Query: {query}

Context:
{context}

Instructions:
1. Identify the most relevant information
2. Provide a helpful response
3. Cite sources using [Doc X] format

Response:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        answer = response.content if response and response.content else ""
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_general_answer(self, query: str) -> Tuple[str, List[Citation]]:
        """Generate a general answer without requiring citations.
        Used when there is no relevant context or the LLM returned empty content.
        """
        try:
            client = get_llm_client(tier=self.config.general_answer_tier)
            system_prompt = (
                "You are a knowledgeable technical assistant. Answer concisely and helpfully based on general "
                "domain knowledge when no specific document context is provided. Do not fabricate citations."
            )
            prompt = (
                f"Provide a concise overview answering the following query. "
                f"Use bullet points where appropriate.\n\nQuery: {query}\n\nAnswer:"
            )
            response = client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=max(0.2, self.config.temperature),
                max_tokens=max(300, self.config.max_answer_length),
            )

            # Extract answer from response
            if response and hasattr(response, "content") and response.content:
                generic_answer = response.content.strip()
            else:
                generic_answer = ""

            # If still empty, provide a fallback message
            if not generic_answer or len(generic_answer) < 10:
                logger.warning(
                    f"General answer generation failed or returned empty for query: {query[:100]}"
                )
                generic_answer = (
                    f"I understand you're asking about '{query[:100]}...'. "
                    f"Unfortunately, I couldn't generate a complete answer at this moment. "
                    f"Please try rephrasing your question or providing more context."
                )

            return generic_answer, []

        except Exception as e:
            logger.error(f"Failed to generate general answer: {e}")
            # Return a helpful fallback message
            return (
                f"I'm having trouble processing your question about '{query[:100]}...'. "
                f"Please try again or rephrase your question for better results."
            ), []

    def _extract_citations(
        self, answer: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> List[Citation]:
        """Extract citations from answer text"""
        citations = []

        # Find all [Doc X] references
        pattern = r"\[Doc\s*(\d+)\]"
        matches = re.findall(pattern, answer)

        seen_docs = set()
        for match in matches:
            doc_num = int(match)
            if doc_num in doc_mapping and doc_num not in seen_docs:
                doc = doc_mapping[doc_num]
                citations.append(
                    Citation(
                        doc_id=doc.doc_id,
                        source=doc.source,
                        page=doc.page,
                        text_snippet=doc.text[:200],
                        relevance_score=doc.score,
                    )
                )
                seen_docs.add(doc_num)

        return citations

    def _calculate_confidence(
        self, answer: str, citations: List[Citation], docs: List[RetrievalResult]
    ) -> float:
        """Calculate confidence score for the answer"""

        # Base confidence from document scores
        if docs:
            avg_score = sum(d.score for d in docs[:3]) / min(3, len(docs))
            base_confidence = min(avg_score * 2, 1.0)  # Scale up
        else:
            base_confidence = 0.0

        # Adjust based on citations
        if citations:
            citation_boost = min(len(citations) * 0.1, 0.3)
            base_confidence = min(base_confidence + citation_boost, 1.0)

        # Penalize if answer is too short or generic
        if len(answer) < 50:
            base_confidence *= 0.7

        # Check for uncertainty markers
        uncertainty_phrases = ["not sure", "unclear", "might be", "possibly", "unknown"]
        if any(phrase in answer.lower() for phrase in uncertainty_phrases):
            base_confidence *= 0.8

        return base_confidence

    def _post_process_answer(
        self, answer: str, citations: List[Citation], confidence: float
    ) -> str:
        """Post-process answer for final formatting"""

        # Clean up answer
        answer = (answer or "").strip()

        # Add confidence indicator if low (ASCII only)
        if confidence < self.config.min_confidence and answer:
            answer = f"[LOW CONFIDENCE]\n{answer}"

        # Format citations based on style
        if self.config.citation_style == "footnote" and citations:
            # Convert inline [Doc X] to footnotes
            for i, citation in enumerate(citations, 1):
                answer = answer.replace(f"[Doc {i}]", f"[{i}]")

            # Add footnotes
            answer += "\n\nSources:"
            for i, citation in enumerate(citations, 1):
                answer += f"\n[{i}] {citation.source}"
                if citation.page:
                    answer += f" (Page {citation.page})"

        return answer

    def _generate_no_results_answer(self, query: TransformedQuery) -> GeneratedAnswer:
        """Generate answer when no documents are retrieved.
        If allowed, fall back to a general answer without citations.
        """
        if self.config.allow_uncited_fallback:
            # Try to produce a general answer using model knowledge
            try:
                generic_answer, _ = self._generate_general_answer(query.original)
            except Exception:
                generic_answer = ""
            if generic_answer:
                return GeneratedAnswer(
                    query=query.original,
                    answer=generic_answer,
                    citations=[],
                    confidence=0.5,
                    metadata={"no_results": True, "uncited_fallback": True},
                )
        # Conservative fallback message if disabled or failed
        answer = f"No specific information found about '{query.original}' in the current documents."
        return GeneratedAnswer(
            query=query.original,
            answer=answer,
            citations=[],
            confidence=0.0,
            metadata={"no_results": True},
        )

    def _generate_error_answer(
        self, query: TransformedQuery, error: str
    ) -> GeneratedAnswer:
        """Generate answer when an error occurs"""

        answer = (
            "I encountered an error while processing your request. "
            "Please try rephrasing your question or contact support if the issue persists."
        )

        logger.error(f"Generation error for query '{query.original}': {error}")

        return GeneratedAnswer(
            query=query.original,
            answer=answer,
            citations=[],
            confidence=0.0,
            metadata={"error": True, "error_message": error},
        )

    def generate_streaming(
        self, query: TransformedQuery, retrieved_docs: List[RetrievalResult]
    ) -> Any:
        """
        Generate answer with streaming (for future implementation)
        Yields chunks of the answer as they're generated
        """
        # TODO: Implement streaming generation for real-time responses
        pass


def create_generator(config: Optional[GeneratorConfig] = None) -> ResponseGenerator:
    """
    Factory function to create generator

    Args:
        config: Optional configuration

    Returns:
        Configured RAGGenerator instance
    """
    return ResponseGenerator(config or GeneratorConfig())


# Backward compatibility alias expected by some tests
RAGGenerator = ResponseGenerator


# Convenience function
def generate_answer(
    query: TransformedQuery, retrieved_docs: List[RetrievalResult], **kwargs
) -> GeneratedAnswer:
    """
    Quick function to generate answer

    Args:
        query: Transformed query
        retrieved_docs: Retrieved documents
        **kwargs: Additional config parameters

    Returns:
        Generated answer with citations
    """
    config = GeneratorConfig(**kwargs)
    generator = create_generator(config)
    return generator.generate(query, retrieved_docs)
