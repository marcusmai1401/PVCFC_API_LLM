"""
Document Classification using LLM
Enhances rule-based classification with LLM for better accuracy
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.services.llm import LLMService


class DocumentClassificationLLM:
    """
    LLM-based document classifier for enhanced classification
    """

    # Standard document types in the system
    DOCUMENT_TYPES = [
        "P&ID",
        "Technical Data",
        "Manual",
        "Drawing",
        "Procedure",
        "Report",
        "MOC",
        "RCA",
        "Certificate",
        "Calculation",
        "Performance",
        "Checklist",
        "Schedule",
        "Specification",
        "List",
        "Vendor",
    ]

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize LLM classifier

        Args:
            llm_service: Optional LLM service instance
        """
        self.llm_service = llm_service or LLMService()

    def create_classification_prompt(
        self,
        filename: str,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.7,
    ) -> str:
        """
        Create a prompt for document classification

        Args:
            filename: Name of the file
            first_page_text: Text from first page (limited to 1500 chars)
            metadata: Document metadata
            confidence_threshold: Minimum confidence for classification

        Returns:
            Formatted prompt for LLM
        """
        # Prepare context
        context_parts = [f"Filename: {filename}"]

        if metadata:
            if metadata.get("title"):
                context_parts.append(f"Title: {metadata['title']}")
            if metadata.get("subject"):
                context_parts.append(f"Subject: {metadata['subject']}")
            if metadata.get("keywords"):
                context_parts.append(f"Keywords: {metadata['keywords']}")

        if first_page_text:
            # Limit text to avoid token limits
            text_preview = first_page_text[:1500]
            if len(first_page_text) > 1500:
                text_preview += "..."
            context_parts.append(f"First page content:\n{text_preview}")

        context = "\n\n".join(context_parts)

        # Create the prompt
        prompt = f"""You are a technical document classifier for industrial engineering documents.

Classify the following document into one of these categories:
{', '.join(self.DOCUMENT_TYPES)}

Document Information:
{context}

Instructions:
1. Analyze the filename, metadata, and content to determine the document type
2. Consider industry-specific terminology and patterns
3. If the document doesn't clearly fit any category, classify as "unknown"
4. Also extract any revision information (Rev, Version, V, Issue, etc.)

Response Format (JSON only):
{{
    "doc_type": "selected type or unknown",
    "confidence": 0.0-1.0,
    "revision": "revision if found or null",
    "reasoning": "brief explanation"
}}

Important:
- P&ID: Piping and Instrumentation Diagrams
- MOC: Management of Change documents
- RCA: Root Cause Analysis reports
- Technical Data: Datasheets, specifications with technical parameters
- Manual: Operation, maintenance, installation guides
- Drawing: Engineering drawings, layouts, schematics
- Vendor: Documents from equipment suppliers/manufacturers

Respond with JSON only, no additional text."""

        return prompt

    def parse_llm_response(self, response: str) -> Tuple[str, float, Optional[str]]:
        """
        Parse LLM response to extract classification

        Args:
            response: LLM response text

        Returns:
            Tuple of (doc_type, confidence, revision)
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)

                doc_type = result.get("doc_type", "unknown")
                confidence = float(result.get("confidence", 0.5))
                revision = result.get("revision")

                # Validate doc_type
                if doc_type not in self.DOCUMENT_TYPES and doc_type != "unknown":
                    # Try to find closest match
                    doc_type_lower = doc_type.lower()
                    for valid_type in self.DOCUMENT_TYPES:
                        if (
                            valid_type.lower() in doc_type_lower
                            or doc_type_lower in valid_type.lower()
                        ):
                            doc_type = valid_type
                            break
                    else:
                        doc_type = "unknown"

                logger.debug(
                    f"LLM classification: type={doc_type}, confidence={confidence}, "
                    f"revision={revision}, reasoning={result.get('reasoning', 'N/A')}"
                )

                return doc_type, confidence, revision

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        # Fallback parsing if JSON fails
        doc_type = "unknown"
        confidence = 0.5
        revision = None

        # Try simple pattern matching
        response_lower = response.lower()
        for dtype in self.DOCUMENT_TYPES:
            if dtype.lower() in response_lower:
                doc_type = dtype
                confidence = 0.6  # Lower confidence for pattern match
                break

        # Extract revision if mentioned
        rev_match = re.search(
            r"rev(?:ision)?\s*[:=]?\s*([A-Z0-9]+)", response, re.IGNORECASE
        )
        if rev_match:
            revision = rev_match.group(1)

        return doc_type, confidence, revision

    async def classify_async(
        self,
        file_path: Path,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.7,
    ) -> Tuple[str, Optional[str], float]:
        """
        Classify document using LLM (async)

        Args:
            file_path: Path to document
            first_page_text: Optional first page text
            metadata: Optional document metadata
            confidence_threshold: Minimum confidence threshold

        Returns:
            Tuple of (doc_type, revision, confidence)
        """
        try:
            # Create classification prompt
            prompt = self.create_classification_prompt(
                filename=file_path.name,
                first_page_text=first_page_text,
                metadata=metadata,
                confidence_threshold=confidence_threshold,
            )

            # Call LLM (async)
            response = await self.llm_service.complete(
                prompt=prompt,
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=200,
                tier="light",  # Use light tier for classification
            )

            # Parse response
            doc_type, confidence, revision = self.parse_llm_response(response)

            # Apply confidence threshold
            if confidence < confidence_threshold:
                logger.info(
                    f"LLM confidence {confidence} below threshold {confidence_threshold}, "
                    f"returning 'unknown'"
                )
                doc_type = "unknown"

            return doc_type, revision, confidence

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return "unknown", None, 0.0

    def classify(
        self,
        file_path: Path,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.7,
    ) -> Tuple[str, Optional[str], float]:
        """
        Classify document using LLM (sync wrapper)

        Args:
            file_path: Path to document
            first_page_text: Optional first page text
            metadata: Optional document metadata
            confidence_threshold: Minimum confidence threshold

        Returns:
            Tuple of (doc_type, revision, confidence)
        """
        try:
            # Create classification prompt
            prompt = self.create_classification_prompt(
                filename=file_path.name,
                first_page_text=first_page_text,
                metadata=metadata,
                confidence_threshold=confidence_threshold,
            )

            # Call LLM (sync) - use async in sync context
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                self.llm_service.complete(
                    prompt=prompt,
                    temperature=0.1,  # Low temperature for consistent classification
                    max_tokens=200,
                    tier="light",  # Use light tier for classification
                )
            )
            loop.close()

            # Parse response
            doc_type, confidence, revision = self.parse_llm_response(response)

            # Apply confidence threshold
            if confidence < confidence_threshold:
                logger.info(
                    f"LLM confidence {confidence} below threshold {confidence_threshold}, "
                    f"returning 'unknown'"
                )
                doc_type = "unknown"

            return doc_type, revision, confidence

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return "unknown", None, 0.0

    def enhance_classification(
        self,
        rule_based_type: str,
        rule_based_revision: Optional[str],
        file_path: Path,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Enhance rule-based classification with LLM

        Args:
            rule_based_type: Type from rule-based classifier
            rule_based_revision: Revision from rule-based classifier
            file_path: Path to document
            first_page_text: Optional first page text
            metadata: Optional document metadata

        Returns:
            Tuple of (enhanced_type, enhanced_revision)
        """
        # Only use LLM if rule-based returned "unknown" or low confidence
        if rule_based_type == "unknown":
            logger.info("Rule-based classifier returned 'unknown', trying LLM")
            llm_type, llm_revision, confidence = self.classify(
                file_path=file_path,
                first_page_text=first_page_text,
                metadata=metadata,
                confidence_threshold=0.6,  # Lower threshold for unknown cases
            )

            if llm_type != "unknown" and confidence > 0.6:
                logger.info(
                    f"LLM enhanced classification: {rule_based_type} -> {llm_type} "
                    f"(confidence: {confidence})"
                )
                return llm_type, llm_revision or rule_based_revision

        # Keep rule-based result if it's good
        return rule_based_type, rule_based_revision
