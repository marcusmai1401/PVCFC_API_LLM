"""
Document Classification Module
Classifies documents by type and extracts revision information
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class ClassificationRules:
    """Holds classification rules and patterns"""

    # Document type keyword patterns (lowercase)
    TYPE_PATTERNS: Dict[str, List[str]] = None

    # Revision extraction patterns
    REVISION_PATTERNS: List[str] = None

    def __post_init__(self):
        """Initialize default patterns"""
        if self.TYPE_PATTERNS is None:
            self.TYPE_PATTERNS = {
                "P&ID": [
                    "p&id",
                    "p_id",
                    "pid",
                    "piping",
                    "instrumentation",
                    "diagram",
                    "process_flow",
                    "pfd",
                    "p&i_diagram",
                ],
                "Technical Data": [
                    "data_sheet",
                    "datasheet",
                    "technical_data",
                    "spec_sheet",
                    "specification",
                    "technical_specification",
                    "equipment_data",
                    "material_data",
                    "product_data",
                ],
                "Manual": [
                    "manual",
                    "operation",
                    "maintenance",
                    "o&m",
                    "user_guide",
                    "instruction",
                    "handbook",
                    "guidebook",
                    "operating_manual",
                    "service_manual",
                    "installation_manual",
                    "repair_manual",
                ],
                "Drawing": [
                    "drawing",
                    "sketch",
                    "layout",
                    "arrangement",
                    "elevation",
                    "section",
                    "detail",
                    "isometric",
                    "schematic",
                    "blueprint",
                    "cad",
                    "diagram",
                    "plot_plan",
                    "general_arrangement",
                    "ga_",
                ],
                "Procedure": [
                    "procedure",
                    "sop",
                    "standard_operating",
                    "work_instruction",
                    "method_statement",
                    "protocol",
                    "guideline",
                    "process",
                    "safety_procedure",
                    "test_procedure",
                    "commissioning",
                ],
                "Report": [
                    "report",
                    "analysis",
                    "study",
                    "assessment",
                    "evaluation",
                    "review",
                    "audit",
                    "investigation",
                    "summary",
                    "findings",
                    "test_report",
                    "inspection_report",
                    "incident_report",
                ],
                "MOC": [
                    "moc",
                    "management_of_change",
                    "change_management",
                    "modification",
                    "change_request",
                    "change_order",
                    "variation",
                ],
                "RCA": [
                    "rca",
                    "root_cause",
                    "failure_analysis",
                    "incident_analysis",
                    "problem_analysis",
                    "investigation",
                    "corrective_action",
                ],
                "Certificate": [
                    "certificate",
                    "certification",
                    "compliance",
                    "conformance",
                    "calibration",
                    "test_certificate",
                    "material_certificate",
                    "quality_certificate",
                    "inspection_certificate",
                ],
                "Calculation": [
                    "calculation",
                    "calc",
                    "sizing",
                    "design_calculation",
                    "stress_analysis",
                    "load_calculation",
                    "thermal_calculation",
                ],
                "Performance": [
                    "performance",
                    "curve",
                    "characteristic",
                    "efficiency",
                    "capacity",
                    "rating",
                    "performance_curve",
                    "test_curve",
                    "pump_curve",
                    "compressor_curve",
                    "fan_curve",
                ],
                "Checklist": [
                    "checklist",
                    "punchlist",
                    "punch_list",
                    "inspection_list",
                    "commissioning_checklist",
                    "startup_checklist",
                    "qc_checklist",
                ],
                "Schedule": [
                    "schedule",
                    "timeline",
                    "program",
                    "plan",
                    "gantt",
                    "project_schedule",
                    "maintenance_schedule",
                    "shutdown_schedule",
                ],
                "Specification": [
                    "specification",
                    "spec",
                    "requirement",
                    "standard",
                    "design_spec",
                    "functional_spec",
                    "technical_spec",
                    "material_spec",
                    "equipment_spec",
                    "piping_spec",
                ],
                "List": [
                    "list",
                    "register",
                    "inventory",
                    "index",
                    "catalog",
                    "equipment_list",
                    "valve_list",
                    "instrument_list",
                    "material_list",
                    "spare_parts",
                    "bom",
                    "bill_of_material",
                ],
                "Vendor": [
                    "vendor",
                    "supplier",
                    "manufacturer",
                    "oem",
                    "vendor_drawing",
                    "vendor_data",
                    "vendor_document",
                    "shop_drawing",
                    "fabrication_drawing",
                ],
            }

        if self.REVISION_PATTERNS is None:
            self.REVISION_PATTERNS = [
                # Standard revision patterns
                r"[Rr]ev\.?\s*([A-Z0-9]+[A-Z0-9.-]*)",  # Rev.01, REV A, Rev.01-A
                r"[Rr]evision\s*[:=]?\s*([A-Z0-9]+[A-Z0-9.-]*)",
                r"[Vv]ersion\s*[:=]?\s*([0-9]+[.0-9]*)",
                r"[Vv]er\.?\s*([0-9]+[.0-9]*)",
                r"[Vv]([0-9]+[.0-9]*)",  # V1, v2.1
                # Underscore patterns
                r"_[Rr]([0-9]+[A-Z0-9]*)",  # _R1, _R01
                r"_[Rr]ev([0-9]+[A-Z0-9]*)",  # _Rev1
                # Dot patterns
                r"\.r([0-9]+[A-Z0-9]*)\.",  # .r01.
                r"\.rev([0-9]+[A-Z0-9]*)\.",  # .rev0E.
                # Issue/Edition patterns
                r"[Ii]ssue\s*[:=]?\s*([A-Z0-9]+)",
                r"[Ee]dition\s*[:=]?\s*([A-Z0-9]+)",
                # Parenthesis patterns
                r"\(([Rr]ev\.?\s*[A-Z0-9]+)\)",  # (Rev.A)
                r"\([Vv]([0-9]+[.0-9]*)\)",  # (V1.0)
                # Date-based versions (YYYYMMDD)
                r"_(\d{8})(?:_|\.|\s|$)",
                # Sheet/drawing revisions
                r"[Ss]h(?:eet)?\s*[Rr]ev\.?\s*([A-Z0-9]+)",
                r"[Dd]wg\s*[Rr]ev\.?\s*([A-Z0-9]+)",
            ]


class DocumentClassifier:
    """
    Classifies documents based on filename, path, and content patterns
    """

    def __init__(self, rules: Optional[ClassificationRules] = None):
        """
        Initialize classifier with optional custom rules

        Args:
            rules: Custom classification rules, uses defaults if None
        """
        self.rules = rules or ClassificationRules()

        # Compile regex patterns for efficiency
        self._compiled_rev_patterns = [
            re.compile(pattern) for pattern in self.rules.REVISION_PATTERNS
        ]

    def classify(
        self,
        file_path: Path,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Classify document and extract revision

        Args:
            file_path: Path to the document
            first_page_text: Optional text from first page for content-based classification
            metadata: Optional document metadata (title, subject, etc.)

        Returns:
            Tuple of (doc_type, revision)
        """
        doc_type = self._classify_doc_type(file_path, first_page_text, metadata)
        revision = self._extract_revision(file_path, first_page_text, metadata)

        return doc_type, revision

    def _classify_doc_type(
        self,
        file_path: Path,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Determine document type using rule-based classification
        """
        # Prepare search strings
        search_strings = []

        # Add path components
        path_str = str(file_path).lower()
        search_strings.append(path_str)

        # Add filename without extension
        filename_stem = file_path.stem.lower()
        search_strings.append(filename_stem)

        # Add parent directory names
        for parent in file_path.parents:
            if parent.name:
                search_strings.append(parent.name.lower())

        # Add metadata if available
        if metadata:
            for key in ["title", "subject", "keywords"]:
                if metadata.get(key):
                    search_strings.append(str(metadata[key]).lower())

        # Add first page text (limited to first 2000 chars for efficiency)
        if first_page_text:
            search_strings.append(first_page_text[:2000].lower())

        # Score each document type
        type_scores = {}

        for doc_type, patterns in self.rules.TYPE_PATTERNS.items():
            score = 0
            matched_patterns = []

            for pattern in patterns:
                # Use word boundaries for more accurate matching
                pattern_regex = (
                    r"\b" + re.escape(pattern).replace("_", r"[\s_-]?") + r"\b"
                )

                for search_str in search_strings:
                    if re.search(pattern_regex, search_str):
                        # Different weights for different sources
                        if search_str == filename_stem:
                            score += 10  # Highest weight for filename
                        elif search_str == path_str:
                            score += 5  # Medium weight for full path
                        elif (
                            first_page_text
                            and search_str == first_page_text[:2000].lower()
                        ):
                            score += 3  # Lower weight for content
                        else:
                            score += 2  # Lowest weight for other sources

                        matched_patterns.append(pattern)
                        break  # Don't count same pattern multiple times

            if score > 0:
                type_scores[doc_type] = (score, matched_patterns)
                logger.debug(
                    f"Document type '{doc_type}' scored {score} (patterns: {matched_patterns})"
                )

        # Return the highest scoring type, or "unknown" if no matches
        if type_scores:
            best_type = max(type_scores.items(), key=lambda x: x[1][0])
            logger.info(f"Classified as '{best_type[0]}' with score {best_type[1][0]}")
            return best_type[0]

        # Fallback: Try to infer from common filename patterns
        filename_lower = file_path.name.lower()

        # Additional fallback patterns not in main rules
        fallback_patterns = {
            "Drawing": ["dwg", "drw", "ga_", "layout", "arrangement"],
            "List": ["list", "index", "register"],
            "Specification": ["spec", "requirement"],
            "Report": ["report", "analysis"],
            "Procedure": ["procedure", "proc", "sop"],
            "Manual": ["manual", "guide", "handbook"],
        }

        for doc_type, patterns in fallback_patterns.items():
            for pattern in patterns:
                if pattern in filename_lower:
                    logger.info(
                        f"Fallback classified as '{doc_type}' based on filename pattern '{pattern}'"
                    )
                    return doc_type

        return "unknown"

    def _extract_revision(
        self,
        file_path: Path,
        first_page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Extract revision information from various sources
        """
        revision = None

        # Try filename first (most reliable)
        filename = file_path.name
        for pattern in self._compiled_rev_patterns:
            match = pattern.search(filename)
            if match:
                revision = match.group(1)
                logger.debug(
                    f"Found revision '{revision}' in filename using pattern: {pattern.pattern}"
                )
                break

        # If not found in filename, try first page text
        if not revision and first_page_text:
            # Look for revision in common locations
            revision_areas = [
                first_page_text[:500],  # Document header
                first_page_text[-500:],  # Document footer
            ]

            # Also look for revision table
            if (
                "revision" in first_page_text.lower()
                or "record of" in first_page_text.lower()
            ):
                # Extract area around revision mentions
                for match in re.finditer(
                    r"revision|record of", first_page_text, re.IGNORECASE
                ):
                    start = max(0, match.start() - 100)
                    end = min(len(first_page_text), match.end() + 200)
                    revision_areas.append(first_page_text[start:end])

            for area in revision_areas:
                for pattern in self._compiled_rev_patterns:
                    match = pattern.search(area)
                    if match:
                        candidate = match.group(1)
                        # Prefer alphanumeric revisions
                        if revision is None or (
                            len(candidate) <= 10
                            and re.match(r"^[A-Z0-9.-]+$", candidate)
                        ):
                            revision = candidate
                            logger.debug(
                                f"Found revision '{revision}' in document content"
                            )
                            break

        # Clean up revision string
        if revision:
            # Remove common prefixes if they were captured
            revision = re.sub(r"^[Rr]ev\.?\s*", "", revision)
            revision = re.sub(r"^[Vv]er\.?\s*", "", revision)
            revision = re.sub(r"^[Vv]", "", revision)

            # Remove trailing dots and spaces
            revision = revision.rstrip(". ")

            # Ensure it's not too long (probably captured too much)
            if len(revision) > 20:
                revision = None

        return revision

    def classify_with_llm(
        self,
        file_path: Path,
        first_page_text: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Classify document using LLM (placeholder for future implementation)

        Args:
            file_path: Path to the document
            first_page_text: Optional text from first page
            model_name: Optional model to use for classification

        Returns:
            Tuple of (doc_type, revision)
        """
        # First try rule-based classification
        doc_type, revision = self.classify(file_path, first_page_text)

        # If unknown, could use LLM here in the future
        if doc_type == "unknown" and model_name:
            logger.debug(
                f"Would use LLM '{model_name}' for classification (not implemented)"
            )
            # Future: Call local LLM API for classification
            pass

        return doc_type, revision


# Export main class
__all__ = ["DocumentClassifier", "ClassificationRules"]
