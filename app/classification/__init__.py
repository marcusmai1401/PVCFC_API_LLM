"""
Document Classification Module

Provides two classification systems:
1. 12-type taxonomy (legacy) - document_type_12.py
2. 4-category taxonomy (v2.0) - taxonomy.py, classifier.py, sampler.py, pipeline.py

The 4-category system is designed for Knowledge Management and Deep Discovery Search.
"""

# Legacy 12-type taxonomy exports
from app.classification.document_type_12 import (
    PARENT_CATEGORIES,
    TECHNICAL_DATA_SUB_CATEGORIES,
    DocumentType12,
    DocumentType12Result,
    get_doc_type_display_name as get_doc_type_12_display_name,
    get_parent_category,
    is_technical_data_sub_category,
    map_llm_label_to_code,
)

# New 4-category taxonomy exports (v2.0)
from app.classification.taxonomy import (
    ClassificationMethod,
    ClassificationStatus,
    DocumentCategory,
    DocumentTaxonomy,
    get_taxonomy,
    get_doc_type_display_name,
)

from app.classification.sampler import (
    AdaptivePageSampler,
    SamplingResult,
)

from app.classification.classifier import (
    ClassificationResult,
    DocumentClassifier,
    PageAnalysis,
)

from app.classification.pipeline import (
    CAD_SCORE_THRESHOLD,
    ClassificationFallback,
    ClassificationPipeline,
    PipelineResult,
    create_classification_pipeline,
    get_classification_pipeline,
    reset_pipeline_singleton,
)

__all__ = [
    # Legacy 12-type taxonomy
    "DocumentType12",
    "DocumentType12Result",
    "PARENT_CATEGORIES",
    "TECHNICAL_DATA_SUB_CATEGORIES",
    "map_llm_label_to_code",
    "get_doc_type_12_display_name",
    "get_parent_category",
    "is_technical_data_sub_category",
    # New 4-category taxonomy (v2.0)
    "DocumentCategory",
    "DocumentTaxonomy",
    "ClassificationStatus",
    "ClassificationMethod",
    "get_taxonomy",
    "get_doc_type_display_name",
    # Sampler
    "AdaptivePageSampler",
    "SamplingResult",
    # Classifier
    "DocumentClassifier",
    "ClassificationResult",
    "PageAnalysis",
    # Pipeline
    "ClassificationPipeline",
    "ClassificationFallback",
    "PipelineResult",
    "CAD_SCORE_THRESHOLD",
    "get_classification_pipeline",
    "create_classification_pipeline",
    "reset_pipeline_singleton",
]
