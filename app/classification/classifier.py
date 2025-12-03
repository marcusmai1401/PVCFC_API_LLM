"""
Document Classifier using Gemini 2.5 Flash
Multimodal AI-powered document classification with Dominant Content Rule

Features:
- Multimodal analysis (page images)
- Dominant Content Rule for mixed documents
- Confidence-based fallback to UNCATEGORIZED
"""
import base64
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from loguru import logger

from app.classification.taxonomy import (
    ClassificationMethod,
    ClassificationStatus,
    DocumentCategory,
    DocumentTaxonomy,
    get_taxonomy,
)


@dataclass
class PageAnalysis:
    """Analysis result for a single page"""
    page_index: int
    content_type: str  # "text" | "drawing" | "mixed" | "image"
    confidence: float
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    """Result of document classification"""
    category: str  # ENGINEERING_DESIGN | VENDOR_EQUIPMENT | OPERATIONS_MAINTENANCE | SAFETY_MANAGEMENT | UNCATEGORIZED
    doc_type: str  # Specific document type within category
    confidence: float  # 0.0 to 1.0
    status: str  # "classified" | "needs_review"
    dominant_content: str  # "text" | "drawing" | "mixed"
    page_analysis: List[PageAnalysis] = field(default_factory=list)
    reasoning: Optional[str] = None  # AI reasoning for classification
    method: str = ClassificationMethod.AI_CLASSIFIER.value
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "category": self.category,
            "doc_type": self.doc_type,
            "confidence": self.confidence,
            "status": self.status,
            "dominant_content": self.dominant_content,
            "page_analysis": [
                {
                    "page_index": pa.page_index,
                    "content_type": pa.content_type,
                    "confidence": pa.confidence
                }
                for pa in self.page_analysis
            ],
            "reasoning": self.reasoning,
            "method": self.method
        }
    
    @classmethod
    def create_uncategorized(
        cls,
        confidence: float = 0.0,
        reasoning: str = "Unable to classify",
        method: str = ClassificationMethod.AI_CLASSIFIER.value
    ) -> "ClassificationResult":
        """Create an UNCATEGORIZED result"""
        return cls(
            category=DocumentCategory.UNCATEGORIZED.value,
            doc_type="Unknown",
            confidence=confidence,
            status=ClassificationStatus.NEEDS_REVIEW.value,
            dominant_content="unknown",
            page_analysis=[],
            reasoning=reasoning,
            method=method
        )


class DocumentClassifierProtocol(Protocol):
    """Protocol for document classifier implementations"""
    
    def classify(
        self,
        page_images: List[bytes],
        filename: str,
        metadata: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify document based on page images"""
        ...


class DocumentClassifier:
    """
    AI-powered document classifier using Gemini 2.5 Flash
    
    Features:
    - Multimodal analysis (text + images)
    - Dominant Content Rule for mixed documents
    - Confidence-based fallback to UNCATEGORIZED
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        confidence_threshold: float = 0.5,
        api_key: Optional[str] = None
    ):
        """
        Initialize classifier
        
        Args:
            model_name: Gemini model name
            confidence_threshold: Minimum confidence to accept classification
            api_key: Google API key (optional, will use env var if not provided)
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.taxonomy = get_taxonomy()
        self._api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            import google.generativeai as genai
            import os
            
            # Try multiple env var names for API key
            api_key = (
                self._api_key 
                or os.getenv("GOOGLE_API_KEY") 
                or os.getenv("GEMINI_API_KEY")
            )
            if not api_key:
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")
            
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(self.model_name)
        
        return self._client
    
    def classify(
        self,
        page_images: List[bytes],
        filename: str,
        metadata: Optional[Dict] = None
    ) -> ClassificationResult:
        """
        Classify document based on sampled page images
        
        Args:
            page_images: List of page images (PNG bytes)
            filename: Original filename for hints
            metadata: Optional metadata from path
            
        Returns:
            ClassificationResult with category, doc_type, confidence
        """
        if not page_images:
            logger.warning(f"No page images provided for {filename}")
            return ClassificationResult.create_uncategorized(
                reasoning="No page images available for classification"
            )
        
        # Filter out empty images
        valid_images = [img for img in page_images if img]
        if not valid_images:
            logger.warning(f"All page images are empty for {filename}")
            return ClassificationResult.create_uncategorized(
                reasoning="All page images are empty"
            )
        
        try:
            # Build prompt
            prompt = self._build_classification_prompt(filename, metadata)
            
            # Call Gemini API
            response = self._call_gemini(prompt, valid_images)
            
            # Parse response
            result = self._parse_response(response, filename)
            
            # Apply dominant content rule if needed
            if result.page_analysis:
                result.dominant_content = self._apply_dominant_content_rule(
                    result.page_analysis
                )
            
            # Apply low confidence fallback
            if result.confidence < self.confidence_threshold:
                logger.info(
                    f"Low confidence ({result.confidence:.2f}) for {filename}, "
                    f"marking as UNCATEGORIZED"
                )
                return ClassificationResult(
                    category=DocumentCategory.UNCATEGORIZED.value,
                    doc_type="Unknown",
                    confidence=result.confidence,
                    status=ClassificationStatus.NEEDS_REVIEW.value,
                    dominant_content=result.dominant_content,
                    page_analysis=result.page_analysis,
                    reasoning=f"Low confidence ({result.confidence:.2f}): {result.reasoning}",
                    method=ClassificationMethod.AI_CLASSIFIER.value
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Classification failed for {filename}: {e}")
            return ClassificationResult.create_uncategorized(
                reasoning=f"Classification error: {str(e)}"
            )
    
    def _build_classification_prompt(
        self,
        filename: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Build prompt for Gemini classification"""
        taxonomy_info = self.taxonomy.to_dict()
        
        prompt = f"""You are a document classification expert for industrial/engineering documents.

Analyze the provided document pages and classify the document into one of these categories:

CATEGORIES AND DOC_TYPES:
1. ENGINEERING_DESIGN: P&ID, Drawing, Technical Data
2. VENDOR_EQUIPMENT: Datasheet, Material Partlist, Vendor Manual  
3. OPERATIONS_MAINTENANCE: Operation Instruction, Maintenance Instruction, Maintenance History, Inventory
4. SAFETY_MANAGEMENT: MOC, RCA, Pictures

CLASSIFICATION RULES:
- Analyze ALL provided page images
- For each page, determine if it's primarily TEXT (paragraphs, instructions) or DRAWING (diagrams, schematics, P&ID)
- Apply DOMINANT CONTENT RULE: classify based on the content type that appears in majority of pages
- If text pages dominate → classify as text-based type (Manual, Instruction, etc.)
- If drawing pages dominate → classify as drawing-based type (P&ID, Drawing, etc.)
- P&ID documents have specific symbols: valves, instruments, flow lines, equipment tags

DOCUMENT INFO:
- Filename: {filename}
- Additional metadata: {json.dumps(metadata) if metadata else 'None'}

RESPOND IN JSON FORMAT:
{{
    "category": "CATEGORY_NAME",
    "doc_type": "DOC_TYPE_NAME",
    "confidence": 0.0-1.0,
    "dominant_content": "text" | "drawing" | "mixed",
    "page_analysis": [
        {{"page_index": 0, "content_type": "text|drawing|mixed", "confidence": 0.0-1.0}},
        ...
    ],
    "reasoning": "Brief explanation of classification decision"
}}

Analyze the document pages now:"""
        
        return prompt
    
    def _call_gemini(
        self,
        prompt: str,
        images: List[bytes]
    ) -> str:
        """Call Gemini API with images"""
        client = self._get_client()
        
        # Build content parts
        parts = [prompt]
        
        # Add images
        for idx, img_bytes in enumerate(images):
            if img_bytes:
                # Convert to base64 for Gemini
                img_data = {
                    "mime_type": "image/png",
                    "data": base64.b64encode(img_bytes).decode("utf-8")
                }
                parts.append(img_data)
        
        # Generate response
        response = client.generate_content(parts)
        
        return response.text
    
    def _parse_response(
        self,
        response: str,
        filename: str
    ) -> ClassificationResult:
        """Parse Gemini response to ClassificationResult"""
        try:
            # Extract JSON from response
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            data = json.loads(json_str.strip())
            
            # Validate category
            category = data.get("category", "UNCATEGORIZED")
            if not self.taxonomy.is_valid_category(category):
                logger.warning(f"Invalid category '{category}' from Gemini, using UNCATEGORIZED")
                category = DocumentCategory.UNCATEGORIZED.value
            
            # Validate doc_type
            doc_type = data.get("doc_type", "Unknown")
            if not self.taxonomy.is_valid_category_doc_type_pair(category, doc_type):
                logger.warning(
                    f"Invalid doc_type '{doc_type}' for category '{category}', "
                    f"using first valid type"
                )
                valid_types = self.taxonomy.get_doc_types_for_category(category)
                doc_type = valid_types[0] if valid_types else "Unknown"
            
            # Parse page analysis
            page_analysis = []
            for pa in data.get("page_analysis", []):
                page_analysis.append(PageAnalysis(
                    page_index=pa.get("page_index", 0),
                    content_type=pa.get("content_type", "unknown"),
                    confidence=pa.get("confidence", 0.0)
                ))
            
            return ClassificationResult(
                category=category,
                doc_type=doc_type,
                confidence=float(data.get("confidence", 0.0)),
                status=ClassificationStatus.CLASSIFIED.value,
                dominant_content=data.get("dominant_content", "unknown"),
                page_analysis=page_analysis,
                reasoning=data.get("reasoning"),
                method=ClassificationMethod.AI_CLASSIFIER.value
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            return ClassificationResult.create_uncategorized(
                reasoning=f"Failed to parse AI response: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error parsing classification response: {e}")
            return ClassificationResult.create_uncategorized(
                reasoning=f"Error parsing response: {str(e)}"
            )
    
    def _apply_dominant_content_rule(
        self,
        page_analysis: List[PageAnalysis]
    ) -> str:
        """
        Determine dominant content type from page analysis
        
        Returns: "text" | "drawing" | "mixed"
        """
        if not page_analysis:
            return "unknown"
        
        text_count = 0
        drawing_count = 0
        
        for pa in page_analysis:
            if pa.content_type == "text":
                text_count += 1
            elif pa.content_type == "drawing":
                drawing_count += 1
        
        total = len(page_analysis)
        
        # More than 50% of one type = dominant
        if text_count > total / 2:
            return "text"
        elif drawing_count > total / 2:
            return "drawing"
        else:
            return "mixed"
