"""
Document Classification API Router
Provides endpoints for document classification and taxonomy management

Endpoints:
- POST /api/classification/classify - Trigger classification for a document
- GET /api/classification/taxonomy - Get taxonomy structure
- GET /api/classification/documents/by-category - Get documents grouped by category
- GET /api/classification/categories - Get list of all categories
- GET /api/classification/doc-types - Get list of all doc types

Requirements: 9.1, 9.2, 9.3
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.classification.classifier import ClassificationResult
from app.classification.pipeline import ClassificationPipeline, get_classification_pipeline
from app.classification.taxonomy import (
    DocumentCategory,
    DocumentTaxonomy,
    get_taxonomy,
)

router = APIRouter(prefix="/classification", tags=["classification"])


# Request/Response models
class ClassifyRequest(BaseModel):
    """Request to classify a document"""
    doc_id: str = Field(..., description="Document ID to classify")
    pdf_path: Optional[str] = Field(None, description="Path to PDF file (if not using doc_id lookup)")
    force_reclassify: bool = Field(False, description="Force reclassification even if already classified")


class ClassificationResultModel(BaseModel):
    """Classification result response"""
    category: str
    doc_type: str
    confidence: float
    status: str
    dominant_content: str
    reasoning: Optional[str] = None
    method: str


class TaxonomyCategoryModel(BaseModel):
    """Category information"""
    name: str
    display_name: str
    doc_types: list[str]
    description: str


class TaxonomyResponseModel(BaseModel):
    """Taxonomy structure response"""
    categories: list[TaxonomyCategoryModel]
    total_categories: int
    total_doc_types: int


class DocumentMetadataModel(BaseModel):
    """Document metadata for tree view"""
    doc_id: str
    filename: str
    category: str
    doc_type: str
    classification_status: str
    classification_confidence: float
    pdf_path: Optional[str] = None


class DocumentsByCategoryResponse(BaseModel):
    """Response for documents grouped by category"""
    category: str
    doc_types: dict[str, list[DocumentMetadataModel]]
    total_documents: int


# Dependencies
def get_pipeline_dependency() -> ClassificationPipeline:
    """
    Get ClassificationPipeline singleton instance
    
    Uses the factory function from pipeline module which handles:
    - CADLikeGate integration (if available)
    - DocumentClassifier initialization
    - AdaptivePageSampler initialization
    """
    return get_classification_pipeline()


def get_taxonomy_instance() -> DocumentTaxonomy:
    """Get DocumentTaxonomy singleton instance"""
    return get_taxonomy()


@router.post(
    "/classify",
    response_model=ClassificationResultModel,
    summary="Classify Document",
    description="""
    Trigger classification for a specific document.
    
    The classification pipeline:
    1. Runs CADLikeGate guardrail first (if CAD_score >= 0.55, force P&ID)
    2. If not P&ID, runs AI classification with Gemini 2.5 Flash
    3. If confidence < 0.5, marks as UNCATEGORIZED + NEEDS_REVIEW
    
    Requirements: 9.1
    """
)
async def classify_document(
    request: ClassifyRequest,
    pipeline: ClassificationPipeline = Depends(get_pipeline_dependency)
) -> ClassificationResultModel:
    """
    Trigger classification for a specific document
    
    Args:
        request: Classification request with doc_id or pdf_path
        
    Returns:
        ClassificationResultModel with classification results
    """
    logger.info(f"Classification request for doc_id={request.doc_id}")
    
    # Determine PDF path
    pdf_path = None
    if request.pdf_path:
        pdf_path = Path(request.pdf_path)
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"PDF file not found: {request.pdf_path}"
            )
    else:
        # TODO: Look up PDF path from doc_id in database
        raise HTTPException(
            status_code=400,
            detail="pdf_path is required (doc_id lookup not yet implemented)"
        )
    
    try:
        result = pipeline.classify_with_fallback(pdf_path)
        
        return ClassificationResultModel(
            category=result.category,
            doc_type=result.doc_type,
            confidence=result.confidence,
            status=result.status,
            dominant_content=result.dominant_content,
            reasoning=result.reasoning,
            method=result.method
        )
        
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


@router.get(
    "/taxonomy",
    response_model=TaxonomyResponseModel,
    summary="Get Taxonomy",
    description="""
    Get the document taxonomy structure with all categories and doc_types.
    
    Returns the 4-category taxonomy:
    - ENGINEERING_DESIGN: P&ID, Drawing, Technical Data
    - VENDOR_EQUIPMENT: Datasheet, Material Partlist, Vendor Manual
    - OPERATIONS_MAINTENANCE: Operation Instruction, Maintenance Instruction, etc.
    - SAFETY_MANAGEMENT: MOC, RCA, Pictures
    - UNCATEGORIZED: Unknown (for low confidence)
    
    Requirements: 9.2
    """
)
async def get_taxonomy_endpoint(
    taxonomy: DocumentTaxonomy = Depends(get_taxonomy_instance)
) -> TaxonomyResponseModel:
    """
    Get document taxonomy structure
    
    Returns:
        TaxonomyResponseModel with all categories and doc_types
    """
    categories = []
    
    for cat_name, cat_info in taxonomy.CATEGORIES.items():
        categories.append(TaxonomyCategoryModel(
            name=cat_name,
            display_name=cat_info["display_name"],
            doc_types=cat_info["doc_types"],
            description=cat_info.get("description", "")
        ))
    
    return TaxonomyResponseModel(
        categories=categories,
        total_categories=len(categories),
        total_doc_types=len(taxonomy.get_all_doc_types())
    )


@router.get(
    "/documents/by-category",
    response_model=list[DocumentsByCategoryResponse],
    summary="Get Documents by Category",
    description="""
    Get documents grouped by category for tree view display.
    
    Returns documents organized by category and doc_type for building
    a hierarchical tree view in the UI. Supports filtering by category,
    doc_type, and classification status.
    
    Requirements: 9.3
    """
)
async def get_documents_by_category(
    category: Optional[str] = Query(
        None,
        description="Filter by specific category"
    ),
    doc_type: Optional[str] = Query(
        None,
        description="Filter by specific doc_type"
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by classification status (classified, needs_review, pending)"
    ),
    taxonomy: DocumentTaxonomy = Depends(get_taxonomy_instance)
) -> list[DocumentsByCategoryResponse]:
    """
    Get documents grouped by category for tree view
    
    Args:
        category: Optional category filter
        doc_type: Optional doc_type filter
        status: Optional status filter
        
    Returns:
        List of DocumentsByCategoryResponse
    """
    logger.info(
        f"Get documents by category: category={category}, "
        f"doc_type={doc_type}, status={status}"
    )
    
    # Validate category if provided
    if category and not taxonomy.is_valid_category(category):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category: {category}"
        )
    
    # Validate doc_type if provided
    if doc_type and not taxonomy.is_valid_doc_type(doc_type):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type: {doc_type}"
        )
    
    # TODO: Query actual documents from database
    # For now, return empty structure based on taxonomy
    
    results = []
    
    categories_to_query = [category] if category else taxonomy.get_all_categories()
    
    for cat in categories_to_query:
        doc_types_dict = {}
        
        cat_doc_types = taxonomy.get_doc_types_for_category(cat)
        if doc_type:
            cat_doc_types = [dt for dt in cat_doc_types if dt == doc_type]
        
        for dt in cat_doc_types:
            # TODO: Query documents for this category/doc_type
            doc_types_dict[dt] = []
        
        results.append(DocumentsByCategoryResponse(
            category=cat,
            doc_types=doc_types_dict,
            total_documents=0  # TODO: Count actual documents
        ))
    
    return results


@router.get(
    "/categories",
    response_model=list[str],
    summary="Get Categories",
    description="Get list of all valid category names"
)
async def get_categories(
    taxonomy: DocumentTaxonomy = Depends(get_taxonomy_instance)
) -> list[str]:
    """Get list of all valid category names"""
    return taxonomy.get_all_categories()


@router.get(
    "/doc-types",
    response_model=list[str],
    summary="Get Doc Types",
    description="Get list of all valid doc_type names"
)
async def get_doc_types(
    category: Optional[str] = Query(
        None,
        description="Filter by category"
    ),
    taxonomy: DocumentTaxonomy = Depends(get_taxonomy_instance)
) -> list[str]:
    """
    Get list of all valid doc_type names
    
    Args:
        category: Optional category to filter doc_types
        
    Returns:
        List of doc_type names
    """
    if category:
        if not taxonomy.is_valid_category(category):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category}"
            )
        return taxonomy.get_doc_types_for_category(category)
    
    return taxonomy.get_all_doc_types()
