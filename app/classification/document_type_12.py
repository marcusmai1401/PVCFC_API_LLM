"""
Document Type 12-Class Taxonomy
Defines 12 document types for PVCFC technical document classification
"""
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger


class DocumentType12(str, Enum):
    """Document type categories - 4 parent types with Technical Data sub-types"""

    # Parent categories
    P_ID = "P_ID"
    MANAGEMENT_OF_CHANGE = "MANAGEMENT_OF_CHANGE"
    ROOT_CAUSE_ANALYSIS = "ROOT_CAUSE_ANALYSIS"
    TECHNICAL_DATA = "TECHNICAL_DATA"  # Parent category

    # Technical Data sub-categories
    MAINTENANCE_HISTORY = "MAINTENANCE_HISTORY"
    MATERIAL_PARTLIST = "MATERIAL_PARTLIST"
    DATASHEET = "DATASHEET"
    OPERATION_INSTRUCTION = "OPERATION_INSTRUCTION"
    MAINTENANCE_INSTRUCTION = "MAINTENANCE_INSTRUCTION"
    OTHER_TECHNICAL_DOCUMENT = "OTHER_TECHNICAL_DOCUMENT"
    INVENTORY = "INVENTORY"
    PICTURES = "PICTURES"

    UNKNOWN = "UNKNOWN"  # For low-confidence or unclassifiable documents


# Parent categories (top-level)
PARENT_CATEGORIES = [
    DocumentType12.P_ID,
    DocumentType12.MANAGEMENT_OF_CHANGE,
    DocumentType12.ROOT_CAUSE_ANALYSIS,
    DocumentType12.TECHNICAL_DATA,
]

# Technical Data sub-categories
TECHNICAL_DATA_SUB_CATEGORIES = [
    DocumentType12.MAINTENANCE_HISTORY,
    DocumentType12.MATERIAL_PARTLIST,
    DocumentType12.DATASHEET,
    DocumentType12.OPERATION_INSTRUCTION,
    DocumentType12.MAINTENANCE_INSTRUCTION,
    DocumentType12.OTHER_TECHNICAL_DOCUMENT,
    DocumentType12.INVENTORY,
    DocumentType12.PICTURES,
]

# Display names for UI
DISPLAY_NAMES: Dict[str, str] = {
    DocumentType12.P_ID: "P&ID",
    DocumentType12.MANAGEMENT_OF_CHANGE: "Management of Change",
    DocumentType12.ROOT_CAUSE_ANALYSIS: "Root Cause Analysis",
    DocumentType12.TECHNICAL_DATA: "Technical Data",
    DocumentType12.MAINTENANCE_HISTORY: "Maintenance History",
    DocumentType12.MATERIAL_PARTLIST: "Material Partlist",
    DocumentType12.DATASHEET: "Datasheet",
    DocumentType12.OPERATION_INSTRUCTION: "Operation Instruction",
    DocumentType12.MAINTENANCE_INSTRUCTION: "Maintenance Instruction",
    DocumentType12.OTHER_TECHNICAL_DOCUMENT: "Other Technical Document",
    DocumentType12.INVENTORY: "Inventory",
    DocumentType12.PICTURES: "Pictures",
    DocumentType12.UNKNOWN: "Unknown",
}


@dataclass
class DocumentType12Result:
    """Result of document classification with hierarchical parent + sub-category"""

    doc_id: str
    pdf_path: str
    doc_type_12: str  # Fine-grained type (one of DocumentType12 values)
    parent_category: str  # Parent: P_ID, MOC, RCA, or TECHNICAL_DATA
    sub_category: Optional[str] = None  # Sub-category if parent is TECHNICAL_DATA
    confidence: float = 0.0  # 0.0 to 1.0
    method: str = "unknown"  # "rule_only" | "llm_only" | "rule_llm"
    raw_llm_doc_type: Optional[str] = None  # Verbatim from LLM before mapping
    reasoning: Optional[str] = None  # Brief explanation
    timestamp: Optional[str] = None

    def __post_init__(self):
        """Auto-generate timestamp and derive parent/sub if not provided"""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

        # Auto-derive parent and sub-category from doc_type_12 if not provided
        if self.doc_type_12 and not self.parent_category:
            try:
                doc_enum = DocumentType12(self.doc_type_12)
                self.parent_category = get_parent_category(doc_enum).value

                # Set sub_category if this is a Technical Data sub-type
                if is_technical_data_sub_category(doc_enum):
                    self.sub_category = self.doc_type_12
            except ValueError:
                self.parent_category = DocumentType12.UNKNOWN.value

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "doc_id": self.doc_id,
            "pdf_path": self.pdf_path,
            "doc_type_12": self.doc_type_12,
            "parent_category": self.parent_category,
            "sub_category": self.sub_category,
            "confidence": self.confidence,
            "method": self.method,
            "raw_llm_doc_type": self.raw_llm_doc_type,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


def get_doc_type_display_name(doc_type_12: str) -> str:
    """Get human-readable display name for a doc_type_12 code"""
    return DISPLAY_NAMES.get(doc_type_12, doc_type_12)


def get_parent_category(doc_type: DocumentType12) -> DocumentType12:
    """
    Get parent category for a document type

    Args:
        doc_type: Document type (can be parent or sub-category)

    Returns:
        Parent category (P_ID, MOC, RCA, or TECHNICAL_DATA)
    """
    if doc_type in PARENT_CATEGORIES:
        return doc_type
    elif doc_type in TECHNICAL_DATA_SUB_CATEGORIES:
        return DocumentType12.TECHNICAL_DATA
    else:
        return DocumentType12.UNKNOWN


def is_technical_data_sub_category(doc_type: DocumentType12) -> bool:
    """Check if document type is a Technical Data sub-category"""
    return doc_type in TECHNICAL_DATA_SUB_CATEGORIES


def map_llm_label_to_code(llm_label: str) -> DocumentType12:
    """
    Map LLM output label to canonical DocumentType12 code

    Args:
        llm_label: Raw label from LLM (case-insensitive, may have variations)

    Returns:
        DocumentType12 enum value
    """
    if not llm_label:
        return DocumentType12.UNKNOWN

    label_lower = llm_label.lower().strip()

    # Direct mappings (normalized)
    mappings = {
        # P&ID variations
        "p&id": DocumentType12.P_ID,
        "pid": DocumentType12.P_ID,
        "p_id": DocumentType12.P_ID,
        "piping and instrumentation diagram": DocumentType12.P_ID,
        "piping & instrumentation diagram": DocumentType12.P_ID,
        # MOC variations
        "management of change": DocumentType12.MANAGEMENT_OF_CHANGE,
        "moc": DocumentType12.MANAGEMENT_OF_CHANGE,
        "change management": DocumentType12.MANAGEMENT_OF_CHANGE,
        # RCA variations
        "root cause analysis": DocumentType12.ROOT_CAUSE_ANALYSIS,
        "rca": DocumentType12.ROOT_CAUSE_ANALYSIS,
        "root cause": DocumentType12.ROOT_CAUSE_ANALYSIS,
        # Technical Data variations
        "technical data": DocumentType12.TECHNICAL_DATA,
        "technical information": DocumentType12.TECHNICAL_DATA,
        "tech data": DocumentType12.TECHNICAL_DATA,
        # Maintenance History variations
        "maintenance history": DocumentType12.MAINTENANCE_HISTORY,
        "maintenance record": DocumentType12.MAINTENANCE_HISTORY,
        "maintenance log": DocumentType12.MAINTENANCE_HISTORY,
        # Material Partlist variations
        "material partlist": DocumentType12.MATERIAL_PARTLIST,
        "parts list": DocumentType12.MATERIAL_PARTLIST,
        "partlist": DocumentType12.MATERIAL_PARTLIST,
        "parts": DocumentType12.MATERIAL_PARTLIST,
        "bom": DocumentType12.MATERIAL_PARTLIST,
        "bill of materials": DocumentType12.MATERIAL_PARTLIST,
        # Datasheet variations
        "datasheet": DocumentType12.DATASHEET,
        "data sheet": DocumentType12.DATASHEET,
        "spec sheet": DocumentType12.DATASHEET,
        # Operation Instruction variations
        "operation instruction": DocumentType12.OPERATION_INSTRUCTION,
        "operating instruction": DocumentType12.OPERATION_INSTRUCTION,
        "operation manual": DocumentType12.OPERATION_INSTRUCTION,
        "operating manual": DocumentType12.OPERATION_INSTRUCTION,
        "operational guide": DocumentType12.OPERATION_INSTRUCTION,
        # Maintenance Instruction variations
        "maintenance instruction": DocumentType12.MAINTENANCE_INSTRUCTION,
        "maintenance manual": DocumentType12.MAINTENANCE_INSTRUCTION,
        "maintenance guide": DocumentType12.MAINTENANCE_INSTRUCTION,
        "service manual": DocumentType12.MAINTENANCE_INSTRUCTION,
        # Inventory variations
        "inventory": DocumentType12.INVENTORY,
        "stock": DocumentType12.INVENTORY,
        "inventory list": DocumentType12.INVENTORY,
        # Pictures variations
        "pictures": DocumentType12.PICTURES,
        "photos": DocumentType12.PICTURES,
        "images": DocumentType12.PICTURES,
        "photo": DocumentType12.PICTURES,
        "image": DocumentType12.PICTURES,
        # Other/Unknown
        "other": DocumentType12.OTHER_TECHNICAL_DOCUMENT,
        "other technical document": DocumentType12.OTHER_TECHNICAL_DOCUMENT,
        "unknown": DocumentType12.UNKNOWN,
    }

    # Try exact match first
    if label_lower in mappings:
        return mappings[label_lower]

    # Try partial matching for more flexibility
    for key, doc_type in mappings.items():
        if key in label_lower or label_lower in key:
            logger.debug(f"Fuzzy matched '{llm_label}' to {doc_type.value}")
            return doc_type

    # No match found
    logger.warning(f"Could not map LLM label '{llm_label}' to known type")
    return DocumentType12.UNKNOWN


# Rule-based classification patterns
# These are high-confidence patterns that can skip LLM classification

RULE_PATTERNS: Dict[DocumentType12, List[str]] = {
    DocumentType12.P_ID: [
        r"\bp[_\s&-]?i[_\s&-]?d\b",
        r"\bpid\b",
        r"piping.*instrumentation",
        r"process.*flow.*diagram",
    ],
    DocumentType12.MANAGEMENT_OF_CHANGE: [
        r"\bmoc\b",
        r"management.*of.*change",
        r"change.*management",
        r"change.*request",
        r"modification.*request",
    ],
    DocumentType12.ROOT_CAUSE_ANALYSIS: [
        r"\brca\b",
        r"root.*cause",
        r"failure.*analysis",
        r"incident.*analysis",
    ],
    DocumentType12.MAINTENANCE_HISTORY: [
        r"maintenance.*history",
        r"maintenance.*record",
        r"maintenance.*log",
        r"repair.*history",
        r"service.*history",
    ],
    DocumentType12.MATERIAL_PARTLIST: [
        r"parts?.*list",
        r"partlist",
        r"\bbom\b",
        r"bill.*of.*material",
        r"material.*list",
        r"spare.*parts",
    ],
    DocumentType12.DATASHEET: [
        r"data.*sheet",
        r"datasheet",
        r"spec.*sheet",
        r"specification.*sheet",
    ],
    DocumentType12.TECHNICAL_DATA: [
        r"technical.*data",
        r"performance.*curve",
        r"expected.*performance",
        r"design.*data",
        r"technical.*spec",
    ],
    DocumentType12.OPERATION_INSTRUCTION: [
        r"operat(ion|ing).*instruction",
        r"operat(ion|ing).*manual",
        r"operat(ion|ing).*guide",
        r"user.*manual",
        r"user.*guide",
    ],
    DocumentType12.MAINTENANCE_INSTRUCTION: [
        r"maintenance.*instruction",
        r"maintenance.*manual",
        r"maintenance.*guide",
        r"service.*manual",
        r"repair.*manual",
    ],
    DocumentType12.INVENTORY: [
        r"\binventory\b",
        r"stock.*list",
        r"equipment.*list",
        r"asset.*list",
    ],
    DocumentType12.PICTURES: [
        r"\b(photo|image|picture)s?\b",
        r"site.*photos?",
        r"equipment.*photos?",
        r"visual.*inspection",
    ],
}


def apply_rule_based_classification(
    filename: str,
    file_path: Optional[Path] = None,
    path_metadata: Optional[Dict] = None,
) -> Tuple[Optional[DocumentType12], float]:
    """
    Apply rule-based classification using filename and path patterns

    Args:
        filename: Name of the file
        file_path: Full path to the file (optional)
        path_metadata: Metadata extracted from path (optional, from extract_metadata_from_path)

    Returns:
        Tuple of (doc_type_12, confidence) or (None, 0.0) if no confident match
    """
    # Check folder-based hints first (high confidence)
    if file_path:
        path_str = str(file_path).lower()

        # Drawing folder → Technical Data or Datasheet
        if "\\drawing\\" in path_str or "/drawing/" in path_str:
            logger.info("Folder hint: Drawing -> TECHNICAL_DATA")
            return DocumentType12.TECHNICAL_DATA, 0.85

        # Manual folder → Operation/Maintenance Instruction
        if "\\manual\\" in path_str or "/manual/" in path_str:
            # Try to distinguish operation vs maintenance
            if "maintenance" in filename.lower() or "service" in filename.lower():
                logger.info(
                    "Folder hint: Manual (maintenance) -> MAINTENANCE_INSTRUCTION"
                )
                return DocumentType12.MAINTENANCE_INSTRUCTION, 0.85
            else:
                logger.info("Folder hint: Manual -> OPERATION_INSTRUCTION")
                return DocumentType12.OPERATION_INSTRUCTION, 0.85

        # Lube oil system → Technical Data
        if "lube" in path_str and "oil" in path_str:
            logger.info("Folder hint: Lube oil system -> TECHNICAL_DATA")
            return DocumentType12.TECHNICAL_DATA, 0.8

        # Instrument folder → Technical Data or Datasheet
        if "\\instrument\\" in path_str or "/instrument/" in path_str:
            logger.info("Folder hint: Instrument -> TECHNICAL_DATA")
            return DocumentType12.TECHNICAL_DATA, 0.8

        # Seal system → Technical Data
        if "seal" in path_str and "system" in path_str:
            logger.info("Folder hint: Seal system -> TECHNICAL_DATA")
            return DocumentType12.TECHNICAL_DATA, 0.8

    # Prepare search strings
    search_strings = []

    # Add filename (most important)
    filename_lower = filename.lower()
    search_strings.append(filename_lower)

    # Add path components if available
    if file_path:
        path_str = str(file_path).lower()
        search_strings.append(path_str)

        # Add parent directory names
        for parent in file_path.parents:
            if parent.name:
                search_strings.append(parent.name.lower())

    # Add path metadata hints if available
    if path_metadata:
        # Old doc_type from extract_metadata_from_path
        if "doc_type" in path_metadata:
            old_doc_type = str(path_metadata["doc_type"]).lower()
            search_strings.append(old_doc_type)

        # Equipment type might give hints
        if "equipment_type" in path_metadata:
            eq_type = str(path_metadata["equipment_type"]).lower()
            search_strings.append(eq_type)

    # Score each document type
    type_scores: Dict[DocumentType12, int] = {}

    for doc_type, patterns in RULE_PATTERNS.items():
        score = 0
        matched_patterns = []

        for pattern in patterns:
            regex = re.compile(pattern, re.IGNORECASE)

            for idx, search_str in enumerate(search_strings):
                if regex.search(search_str):
                    # Weight by source: filename > path > metadata
                    if idx == 0:  # filename
                        score += 10
                    elif idx == 1:  # full path
                        score += 5
                    else:  # other sources
                        score += 2

                    matched_patterns.append(pattern)
                    break  # Don't count same pattern multiple times

        if score > 0:
            type_scores[doc_type] = score
            logger.debug(
                f"Rule-based: '{doc_type.value}' scored {score} "
                f"(patterns: {matched_patterns})"
            )

    # Return highest scoring type if confidence is high enough
    if type_scores:
        best_type = max(type_scores.items(), key=lambda x: x[1])
        doc_type, score = best_type

        # Confidence mapping: score >= 10 (filename match) = high confidence
        if score >= 10:
            confidence = 0.9
        elif score >= 5:
            confidence = 0.75
        else:
            confidence = 0.6

        logger.info(
            f"Rule-based classification: {doc_type.value} "
            f"(score={score}, confidence={confidence})"
        )
        return doc_type, confidence

    # No confident match
    return None, 0.0


def should_use_llm(
    rule_result: Optional[DocumentType12],
    rule_confidence: float,
    llm_confidence_threshold: float = 0.85,
) -> bool:
    """
    Decide whether to call LLM based on rule-based classification result

    Args:
        rule_result: Result from rule-based classification (None if no match)
        rule_confidence: Confidence of rule-based result (0.0 if no match)
        llm_confidence_threshold: Minimum confidence to skip LLM (default 0.85)

    Returns:
        True if LLM should be called, False if rule-based result is sufficient
    """
    # No rule match -> use LLM
    if rule_result is None:
        return True

    # Low confidence -> use LLM
    if rule_confidence < llm_confidence_threshold:
        return True

    # High confidence rule match -> skip LLM
    return False


# Export main types and functions
__all__ = [
    "DocumentType12",
    "DocumentType12Result",
    "DISPLAY_NAMES",
    "get_doc_type_display_name",
    "map_llm_label_to_code",
    "apply_rule_based_classification",
    "should_use_llm",
]
