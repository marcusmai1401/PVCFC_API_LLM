"""
Structured Citation Schemas for JSON Mode Generation

Defines pydantic models for structured citation output from LLM.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class StructuredCitation(BaseModel):
    """A single citation with structured fields"""

    doc_id: str = Field(
        ..., description="Document identifier (e.g., 'PVCFC-KT06101-datasheet-v1')"
    )
    page: int = Field(
        ..., description="Page number (1-indexed) where information is found", ge=1
    )
    quote: Optional[str] = Field(
        default=None,
        description="Exact quote or snippet from the source (optional but recommended for numerical values)",
    )
    bbox: Optional[List[float]] = Field(
        default=None,
        description="Bounding box [x1, y1, x2, y2] if available for table/figure",
        min_length=4,
        max_length=4,
    )
    evidence_type: Optional[str] = Field(
        default="text", description="Type of evidence: text, table, or figure"
    )

    @field_validator("evidence_type")
    @classmethod
    def validate_evidence_type(cls, v):
        """Validate evidence type"""
        if v and v not in ["text", "table", "figure"]:
            return "text"  # Default fallback
        return v or "text"

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        """Validate bbox coordinates"""
        if v is not None:
            if len(v) != 4:
                return None
            # Ensure all are numbers
            try:
                bbox = [float(x) for x in v]
                # Basic sanity check: x1 < x2, y1 < y2
                if bbox[0] < bbox[2] and bbox[1] < bbox[3]:
                    return bbox
            except (TypeError, ValueError):
                pass
            return None
        return v


class ClaimAttribution(BaseModel):
    """Attribution for a single claim"""

    claim_id: str = Field(..., description="Identifier for this claim")
    claim_text: str = Field(..., description="The factual claim text")
    citations: List[StructuredCitation] = Field(
        ...,
        description="Citations supporting this claim (at least 1 required)",
        min_length=1,
    )
    confidence: Optional[float] = Field(
        default=None, description="Confidence in this claim (0-1)", ge=0.0, le=1.0
    )


class StructuredAnswer(BaseModel):
    """Complete structured answer with claims and citations"""

    answer: str = Field(..., description="The complete answer text in natural language")
    claims: List[ClaimAttribution] = Field(
        default_factory=list, description="List of factual claims with their citations"
    )

    # Legacy support: flat list of all citations
    citations: List[StructuredCitation] = Field(
        default_factory=list,
        description="Flat list of all unique citations (for backward compatibility)",
    )

    @field_validator("claims")
    @classmethod
    def ensure_all_claims_have_citations(cls, claims):
        """Validate that all claims have at least one citation"""
        for claim in claims:
            if not claim.citations:
                raise ValueError(f"Claim '{claim.claim_id}' has no citations")
        return claims


# Schema for Gemini API (using google.genai.types.Schema)
def get_gemini_citation_schema():
    """
    Get the schema definition for Gemini structured output.

    Returns schema compatible with google.genai.types.Schema
    """
    from google.genai import types

    citation_item = types.Schema(
        type="OBJECT",
        properties={
            "doc_id": types.Schema(type="STRING", description="Document identifier"),
            "page": types.Schema(type="INTEGER", description="Page number (1-indexed)"),
            "quote": types.Schema(
                type="STRING", description="Exact quote from source", nullable=True
            ),
            "bbox": types.Schema(
                type="ARRAY",
                items=types.Schema(type="NUMBER"),
                description="Bounding box [x1,y1,x2,y2] for table/figure",
                nullable=True,
            ),
            "evidence_type": types.Schema(
                type="STRING",
                enum=["text", "table", "figure"],
                description="Type of evidence",
                nullable=True,
            ),
        },
        required=["doc_id", "page"],
    )

    claim_attribution = types.Schema(
        type="OBJECT",
        properties={
            "claim_id": types.Schema(type="STRING"),
            "claim_text": types.Schema(type="STRING"),
            "citations": types.Schema(
                type="ARRAY",
                items=citation_item,
                description="Citations for this claim",
            ),
        },
        required=["claim_id", "claim_text", "citations"],
    )

    schema = types.Schema(
        type="OBJECT",
        properties={
            "answer": types.Schema(type="STRING", description="Complete answer text"),
            "claims": types.Schema(
                type="ARRAY",
                items=claim_attribution,
                description="Factual claims with citations",
            ),
        },
        required=["answer", "claims"],
    )

    return schema


# Simplified schema for backward compatibility (no claims breakdown)
def get_simple_citation_schema():
    """Get simplified citation schema (answer + flat citations list)"""
    from google.genai import types

    citation_item = types.Schema(
        type="OBJECT",
        properties={
            "doc_id": types.Schema(type="STRING"),
            "page": types.Schema(type="INTEGER"),
            "quote": types.Schema(type="STRING", nullable=True),
            "evidence_type": types.Schema(
                type="STRING", enum=["text", "table", "figure"], nullable=True
            ),
        },
        required=["doc_id", "page"],
    )

    schema = types.Schema(
        type="OBJECT",
        properties={
            "answer": types.Schema(type="STRING"),
            "citations": types.Schema(type="ARRAY", items=citation_item),
        },
        required=["answer", "citations"],
    )

    return schema


if __name__ == "__main__":
    # Test schema validation
    import json

    # Test valid structured answer
    test_data = {
        "answer": "Áp suất vận hành tối đa của KT-06101 là 10 bar theo datasheet [Doc 1].",
        "claims": [
            {
                "claim_id": "claim_0",
                "claim_text": "Áp suất vận hành tối đa của KT-06101 là 10 bar",
                "citations": [
                    {
                        "doc_id": "PVCFC-KT06101-datasheet-v1",
                        "page": 15,
                        "quote": "Maximum operating pressure: 10 bar",
                        "evidence_type": "table",
                    }
                ],
            }
        ],
    }

    try:
        answer = StructuredAnswer(**test_data)
        print("✓ Schema validation passed")
        print(f"\nParsed answer:")
        print(f"  Text: {answer.answer}")
        print(f"  Claims: {len(answer.claims)}")
        for claim in answer.claims:
            print(f"    - {claim.claim_text}")
            print(f"      Citations: {len(claim.citations)}")
    except Exception as e:
        print(f"✗ Schema validation failed: {e}")

    # Test invalid: claim without citation
    invalid_data = {
        "answer": "Test",
        "claims": [
            {
                "claim_id": "claim_0",
                "claim_text": "Test claim",
                "citations": [],  # Empty!
            }
        ],
    }

    try:
        answer = StructuredAnswer(**invalid_data)
        print("✗ Should have failed validation")
    except ValueError as e:
        print(f"\n✓ Correctly rejected invalid data: {e}")
