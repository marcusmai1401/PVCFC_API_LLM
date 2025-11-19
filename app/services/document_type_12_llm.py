"""
Document Type 12 LLM Classifier
Uses Gemini 2.5 Flash (light tier) for document classification into 12 types
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from app.classification.document_type_12 import (
    DocumentType12,
    DocumentType12Result,
    map_llm_label_to_code,
)
from app.services.llm import LLMService


class DocumentType12LLM:
    """
    LLM-based classifier for 12-type document classification
    Uses Gemini 2.5 Flash via LLMService with tier='light'
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize LLM classifier

        Args:
            llm_service: Optional LLM service instance (creates new if None)
        """
        self.llm_service = llm_service or LLMService()

    def create_classification_prompt(
        self,
        filename: str,
        file_path: Optional[str] = None,
        first_page_text: Optional[str] = None,
        path_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create prompt for 12-type document classification

        Args:
            filename: Name of the file
            file_path: Optional full file path
            first_page_text: Optional text from first page (will be truncated)
            path_metadata: Optional metadata from path extraction

        Returns:
            Formatted prompt string for LLM
        """
        # Build context sections
        context_parts = [f"Filename: {filename}"]

        if file_path:
            context_parts.append(f"File path: {file_path}")

        if path_metadata:
            if path_metadata.get("equipment_id"):
                context_parts.append(f"Equipment ID: {path_metadata['equipment_id']}")
            if path_metadata.get("equipment_type"):
                context_parts.append(
                    f"Equipment type: {path_metadata['equipment_type']}"
                )
            if path_metadata.get("vendor"):
                context_parts.append(f"Vendor: {path_metadata['vendor']}")

        if first_page_text:
            # Send full first page text (no truncation)
            context_parts.append(f"First page content:\n{first_page_text}")

        context = "\n\n".join(context_parts)

        # Create prompt with hierarchical taxonomy
        prompt = f"""Classify this industrial/engineering document.

PARENT CATEGORIES (choose ONE):
1. P&ID - Piping & Instrumentation Diagrams
2. Management of Change - MOC, change requests
3. Root Cause Analysis - RCA, failure analysis
4. Technical Data - Technical documents (see sub-categories below)

If you select "Technical Data", also choose ONE SUB-CATEGORY:
4.1 Maintenance History - maintenance records, logs
4.2 Material Partlist - parts lists, BOM
4.3 Datasheet - equipment datasheets
4.4 Operation Instruction - operating manuals, user guides
4.5 Maintenance Instruction - maintenance manuals, service guides
4.6 Other Technical Document - other technical docs
4.7 Inventory - inventory lists, stock records
4.8 Pictures - photos, images

Document:
{context}

Return ONLY valid JSON:
{{
    "parent_category": "P&ID" or "Management of Change" or "Root Cause Analysis" or "Technical Data",
    "sub_category": "sub-category name if parent is Technical Data, otherwise null",
    "confidence": 0.0-1.0,
    "reasoning": "1-2 sentence explanation"
}}"""

        return prompt

    def parse_llm_response(
        self, response: str
    ) -> Tuple[DocumentType12, float, Optional[str]]:
        """
        Parse LLM JSON response to extract hierarchical classification

        Args:
            response: Raw LLM response text

        Returns:
            Tuple of (doc_type_12, confidence, reasoning)
            - doc_type_12: Final classification (parent or sub-category)
        """
        try:
            # Extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)

                # Extract fields from new hierarchical format
                parent_raw = result.get("parent_category", "")
                sub_raw = result.get("sub_category")
                confidence = float(result.get("confidence", 0.5))
                reasoning = result.get("reasoning", "")

                # Map parent category
                parent_type = map_llm_label_to_code(parent_raw)

                # If parent is Technical Data and sub_category provided, use sub
                if parent_type == DocumentType12.TECHNICAL_DATA and sub_raw:
                    doc_type_12 = map_llm_label_to_code(sub_raw)
                else:
                    doc_type_12 = parent_type

                logger.debug(
                    f"LLM hierarchical classification: parent='{parent_raw}', "
                    f"sub='{sub_raw}' -> final={doc_type_12.value}, "
                    f"confidence={confidence}, reasoning='{reasoning}'"
                )

                return doc_type_12, confidence, reasoning

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}")

        # Fallback: try simple pattern matching
        response_lower = response.lower()

        # Try to find any of the 12 category names in response
        fallback_mappings = {
            "p&id": DocumentType12.P_ID,
            "piping and instrumentation": DocumentType12.P_ID,
            "management of change": DocumentType12.MANAGEMENT_OF_CHANGE,
            "moc": DocumentType12.MANAGEMENT_OF_CHANGE,
            "root cause": DocumentType12.ROOT_CAUSE_ANALYSIS,
            "rca": DocumentType12.ROOT_CAUSE_ANALYSIS,
            "maintenance history": DocumentType12.MAINTENANCE_HISTORY,
            "maintenance record": DocumentType12.MAINTENANCE_HISTORY,
            "material partlist": DocumentType12.MATERIAL_PARTLIST,
            "parts list": DocumentType12.MATERIAL_PARTLIST,
            "bom": DocumentType12.MATERIAL_PARTLIST,
            "datasheet": DocumentType12.DATASHEET,
            "data sheet": DocumentType12.DATASHEET,
            "operation instruction": DocumentType12.OPERATION_INSTRUCTION,
            "operating manual": DocumentType12.OPERATION_INSTRUCTION,
            "maintenance instruction": DocumentType12.MAINTENANCE_INSTRUCTION,
            "maintenance manual": DocumentType12.MAINTENANCE_INSTRUCTION,
            "inventory": DocumentType12.INVENTORY,
            "pictures": DocumentType12.PICTURES,
            "photos": DocumentType12.PICTURES,
            "technical data": DocumentType12.TECHNICAL_DATA,
        }

        for keyword, doc_type in fallback_mappings.items():
            if keyword in response_lower:
                logger.info(f"Fallback: matched '{keyword}' -> {doc_type.value}")
                return doc_type, 0.5, "Fallback pattern matching"

        # Complete fallback
        logger.error(f"Could not parse LLM response at all: {response[:200]}")
        return DocumentType12.UNKNOWN, 0.0, "Parse failed"

    async def classify_async(
        self,
        filename: str,
        file_path: Optional[str] = None,
        first_page_text: Optional[str] = None,
        path_metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.6,
    ) -> Tuple[DocumentType12, float, str]:
        """
        Classify document using LLM (async)

        Args:
            filename: Name of the file
            file_path: Optional full file path
            first_page_text: Optional first page text
            path_metadata: Optional path metadata
            confidence_threshold: Minimum confidence (results below this -> UNKNOWN)

        Returns:
            Tuple of (doc_type_12, confidence, reasoning)
        """
        try:
            # Create prompt
            prompt = self.create_classification_prompt(
                filename=filename,
                file_path=file_path,
                first_page_text=first_page_text,
                path_metadata=path_metadata,
            )

            # Call LLM with light tier (Gemini 2.5 Flash)
            response = await self.llm_service.complete(
                prompt=prompt,
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=8000,  # High limit to process full content without truncation
                tier="light",  # Use Gemini 2.5 Flash
            )

            # Parse response
            doc_type_12, confidence, reasoning = self.parse_llm_response(response)

            # Apply confidence threshold
            if confidence < confidence_threshold:
                logger.info(
                    f"LLM confidence {confidence:.2f} below threshold "
                    f"{confidence_threshold}, marking as UNKNOWN"
                )
                return (
                    DocumentType12.UNKNOWN,
                    confidence,
                    f"Low confidence: {reasoning}",
                )

            return doc_type_12, confidence, reasoning

        except Exception as e:
            logger.error(f"LLM classification failed: {e}", exc_info=True)
            return DocumentType12.UNKNOWN, 0.0, f"Error: {str(e)}"

    def classify(
        self,
        filename: str,
        file_path: Optional[str] = None,
        first_page_text: Optional[str] = None,
        path_metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.6,
    ) -> Tuple[DocumentType12, float, str]:
        """
        Classify document using LLM (sync wrapper)

        Args:
            filename: Name of the file
            file_path: Optional full file path
            first_page_text: Optional first page text
            path_metadata: Optional path metadata
            confidence_threshold: Minimum confidence (results below this -> UNKNOWN)

        Returns:
            Tuple of (doc_type_12, confidence, reasoning)
        """
        import asyncio

        try:
            # Run async classification in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.classify_async(
                    filename=filename,
                    file_path=file_path,
                    first_page_text=first_page_text,
                    path_metadata=path_metadata,
                    confidence_threshold=confidence_threshold,
                )
            )
            loop.close()
            return result

        except Exception as e:
            logger.error(f"Sync LLM classification failed: {e}", exc_info=True)
            return DocumentType12.UNKNOWN, 0.0, f"Error: {str(e)}"


# Export main class
__all__ = ["DocumentType12LLM"]
