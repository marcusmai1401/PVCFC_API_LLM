"""
Document Taxonomy - 4-Category Classification System
Defines the standardized taxonomy for PVCFC document classification v2.0

This module coexists with document_type_12.py which uses a different 12-type taxonomy.
The 4-category system is designed for Knowledge Management and Deep Discovery Search.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class DocumentCategory(str, Enum):
    """
    4 main document categories for PVCFC Knowledge Management
    """
    ENGINEERING_DESIGN = "ENGINEERING_DESIGN"
    VENDOR_EQUIPMENT = "VENDOR_EQUIPMENT"
    OPERATIONS_MAINTENANCE = "OPERATIONS_MAINTENANCE"
    SAFETY_MANAGEMENT = "SAFETY_MANAGEMENT"
    UNCATEGORIZED = "UNCATEGORIZED"


class ClassificationStatus(str, Enum):
    """Classification status for documents"""
    CLASSIFIED = "classified"
    NEEDS_REVIEW = "needs_review"
    PENDING = "pending"


class ClassificationMethod(str, Enum):
    """Method used for classification"""
    CADLIKE_GATE = "cadlike_gate"
    AI_CLASSIFIER = "ai_classifier"
    MANUAL = "manual"


@dataclass
class DocumentTaxonomy:
    """
    4-Category Document Taxonomy for PVCFC
    
    Categories:
    - ENGINEERING_DESIGN: P&ID, Drawing, Technical Data
    - VENDOR_EQUIPMENT: Datasheet, Material Partlist, Vendor Manual
    - OPERATIONS_MAINTENANCE: Operation Instruction, Maintenance Instruction, 
                              Maintenance History, Inventory
    - SAFETY_MANAGEMENT: MOC, RCA, Pictures
    - UNCATEGORIZED: Unknown (for low confidence or unclassifiable)
    """
    
    CATEGORIES: Dict[str, Dict] = None
    
    def __init__(self):
        self.CATEGORIES = {
            DocumentCategory.ENGINEERING_DESIGN.value: {
                "display_name": "Engineering Design",
                "doc_types": ["P&ID", "Drawing", "Technical Data"],
                "description": "Engineering drawings and technical design documents"
            },
            DocumentCategory.VENDOR_EQUIPMENT.value: {
                "display_name": "Vendor Equipment",
                "doc_types": ["Datasheet", "Material Partlist", "Vendor Manual"],
                "description": "Equipment documentation from vendors"
            },
            DocumentCategory.OPERATIONS_MAINTENANCE.value: {
                "display_name": "Operations & Maintenance",
                "doc_types": [
                    "Operation Instruction",
                    "Maintenance Instruction",
                    "Maintenance History",
                    "Inventory"
                ],
                "description": "Operational and maintenance documentation"
            },
            DocumentCategory.SAFETY_MANAGEMENT.value: {
                "display_name": "Safety Management",
                "doc_types": ["MOC", "RCA", "Pictures"],
                "description": "Safety and change management documents"
            },
            DocumentCategory.UNCATEGORIZED.value: {
                "display_name": "Uncategorized",
                "doc_types": ["Unknown"],
                "description": "Documents pending classification or requiring manual review"
            }
        }
    
    def get_all_categories(self) -> List[str]:
        """Get list of all category names"""
        return list(self.CATEGORIES.keys())
    
    def get_doc_types_for_category(self, category: str) -> List[str]:
        """Get list of doc_types for a given category"""
        if category in self.CATEGORIES:
            return self.CATEGORIES[category]["doc_types"]
        return []
    
    def get_all_doc_types(self) -> List[str]:
        """Get flat list of all doc_types across all categories"""
        all_types = []
        for cat_info in self.CATEGORIES.values():
            all_types.extend(cat_info["doc_types"])
        return all_types
    
    def get_category_for_doc_type(self, doc_type: str) -> Optional[str]:
        """Find which category a doc_type belongs to"""
        for category, info in self.CATEGORIES.items():
            if doc_type in info["doc_types"]:
                return category
        return None
    
    def is_valid_category(self, category: str) -> bool:
        """Check if category is valid"""
        return category in self.CATEGORIES
    
    def is_valid_doc_type(self, doc_type: str) -> bool:
        """Check if doc_type is valid"""
        return doc_type in self.get_all_doc_types()
    
    def is_valid_category_doc_type_pair(self, category: str, doc_type: str) -> bool:
        """Check if doc_type belongs to the specified category"""
        if not self.is_valid_category(category):
            return False
        return doc_type in self.CATEGORIES[category]["doc_types"]
    
    def get_display_name(self, category: str) -> str:
        """Get human-readable display name for category"""
        if category in self.CATEGORIES:
            return self.CATEGORIES[category]["display_name"]
        return category
    
    def to_dict(self) -> Dict:
        """Convert taxonomy to dictionary for API response"""
        return {
            "categories": self.CATEGORIES,
            "total_categories": len(self.CATEGORIES),
            "total_doc_types": len(self.get_all_doc_types())
        }


# Singleton instance for easy access
_taxonomy_instance: Optional[DocumentTaxonomy] = None


def get_taxonomy() -> DocumentTaxonomy:
    """Get singleton taxonomy instance"""
    global _taxonomy_instance
    if _taxonomy_instance is None:
        _taxonomy_instance = DocumentTaxonomy()
    return _taxonomy_instance


# Display name mappings for doc_types
DOC_TYPE_DISPLAY_NAMES: Dict[str, str] = {
    "P&ID": "P&ID (Piping & Instrumentation Diagram)",
    "Drawing": "Engineering Drawing",
    "Technical Data": "Technical Data",
    "Datasheet": "Equipment Datasheet",
    "Material Partlist": "Material/Parts List",
    "Vendor Manual": "Vendor Manual",
    "Operation Instruction": "Operation Instruction",
    "Maintenance Instruction": "Maintenance Instruction",
    "Maintenance History": "Maintenance History",
    "Inventory": "Inventory",
    "MOC": "Management of Change",
    "RCA": "Root Cause Analysis",
    "Pictures": "Pictures/Photos",
    "Unknown": "Unknown"
}


def get_doc_type_display_name(doc_type: str) -> str:
    """Get human-readable display name for doc_type"""
    return DOC_TYPE_DISPLAY_NAMES.get(doc_type, doc_type)
