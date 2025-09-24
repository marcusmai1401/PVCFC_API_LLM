"""
HyDE (Hypothetical Document Embeddings) module
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HyDEGenerator:
    """
    Generates hypothetical documents for improved retrieval
    """

    def __init__(self, generator=None):
        """
        Initialize HyDE generator

        Args:
            generator: LLM generator for creating hypothetical documents
        """
        self.generator = generator

    async def generate_hypothetical_document(
        self, query: str, num_documents: int = 1, temperature: float = 0.7
    ) -> List[str]:
        """
        Generate hypothetical documents that would answer the query

        Args:
            query: User query
            num_documents: Number of hypothetical documents to generate
            temperature: Generation temperature

        Returns:
            List of hypothetical documents
        """
        if not self.generator:
            logger.warning("No generator available for HyDE")
            return [query]  # Fallback to original query

        try:
            hypothetical_docs = []

            for i in range(num_documents):
                # Create prompt for hypothetical document
                prompt = self._create_hyde_prompt(query, i)

                # Generate hypothetical document
                doc, _ = await self.generator.generate(
                    query=prompt, context=[], temperature=temperature, max_tokens=200
                )

                hypothetical_docs.append(doc)
                logger.debug(f"Generated hypothetical document {i+1}/{num_documents}")

            return hypothetical_docs

        except Exception as e:
            logger.error(f"Error generating hypothetical documents: {str(e)}")
            return [query]  # Fallback to original query

    def _create_hyde_prompt(self, query: str, variant: int = 0) -> str:
        """
        Create prompt for generating hypothetical document

        Args:
            query: User query
            variant: Variant number for diversity

        Returns:
            Prompt string
        """
        prompts = [
            f"Write a detailed paragraph that would perfectly answer this question: {query}",
            f"Create a technical document excerpt that contains the answer to: {query}",
            f"Generate a comprehensive explanation that addresses: {query}",
        ]

        return prompts[variant % len(prompts)]

    async def enhance_query_with_hyde(
        self, query: str, embedder, num_variants: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Enhance query using HyDE for better retrieval

        Args:
            query: Original query
            embedder: Embedder for generating embeddings
            num_variants: Number of HyDE variants to generate

        Returns:
            List of query variants with embeddings
        """
        try:
            # Generate hypothetical documents
            hyde_docs = await self.generate_hypothetical_document(
                query, num_documents=num_variants
            )

            # Add original query
            all_queries = [query] + hyde_docs

            # Generate embeddings
            embeddings = embedder.embed_documents(all_queries)

            # Create query variants
            variants = []
            for i, (q, emb) in enumerate(zip(all_queries, embeddings)):
                variants.append(
                    {
                        "text": q,
                        "embedding": emb,
                        "is_original": i == 0,
                        "variant_type": "original" if i == 0 else f"hyde_{i}",
                    }
                )

            logger.info(f"Generated {len(variants)} query variants with HyDE")
            return variants

        except Exception as e:
            logger.error(f"Error in HyDE enhancement: {str(e)}")
            # Fallback to original query only
            emb = embedder.embed_query(query)
            return [
                {
                    "text": query,
                    "embedding": emb,
                    "is_original": True,
                    "variant_type": "original",
                }
            ]


# Export class
__all__ = ["HyDEGenerator"]
