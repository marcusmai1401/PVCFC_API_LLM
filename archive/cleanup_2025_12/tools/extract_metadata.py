#!/usr/bin/env python
"""
Metadata Extraction Utility
============================

Extract structured metadata from file paths for domain filtering in Weaviate.

Extracts:
- equipment_type: compressor, turbine, pump, motor, etc.
- doc_type: datasheet, manual, drawing, pid, etc.
- equipment_id: K06101, KT06101, P06101, etc.
- vendor: HITACHI, HTC, SIEMENS, etc.
- lang: vi/en (default: vi)

Usage:
    from tools.extract_metadata import extract_metadata_from_path

    metadata = extract_metadata_from_path(
        "D:/Data_Raw/K06101_CO2 COMPRESSOR_HITACHI/Data/002_3N4-S4274343.pdf"
    )
    # Returns: {equipment_type: "compressor", equipment_id: "K06101", ...}
"""
import re
from pathlib import Path
from typing import Dict, Optional

# Equipment type patterns (order matters - most specific first)
EQUIPMENT_PATTERNS = [
    (r"CO2[_\s]+COMPRESSOR|COMPRESSOR.*CO2", "compressor"),
    (r"COMPRESSOR", "compressor"),
    (r"TURBINE", "turbine"),
    (r"PUMP", "pump"),
    (r"MOTOR", "motor"),
    (r"HEAT[_\s]+EXCHANGER|EXCHANGER", "exchanger"),
    (r"VESSEL|TANK", "vessel"),
    (r"GEAR[_\s]*BOX|GEARBOX", "gearbox"),
]

# Document type patterns (from folder names and filename keywords)
DOC_TYPE_PATTERNS = [
    # Folder-based (most reliable)
    (r"[\\/]Data[\\/]|[\\/]Datasheet[\\/]", "datasheet"),
    (r"[\\/]Manual[\\/]", "manual"),
    (r"[\\/]Drawing[\\/]", "drawing"),
    (r"[\\/]Instrument[\\/]", "instrument"),
    (r"[\\/]Spare[_\s]*[Pp]arts?[\\/]", "spare_parts"),
    (r"[\\/]Maintenance[\\/]", "maintenance"),
    (r"[\\/]Lube[_\s]*[Oo]il[\\/]", "lube_oil"),
    (r"[\\/]Seal[_\s]*[Ss]ystem[\\/]", "seal_system"),
    # Filename-based
    (r"P\s*&\s*ID|PID|P&I\s+Diagram", "pid"),
    (r"datasheet|data[_\s]sheet", "datasheet"),
    (r"manual|instruction", "manual"),
    (r"drawing|assembly", "drawing"),
    (r"performance[_\s]curve", "performance"),
    (r"foundation|layout", "layout"),
    (r"piping|connection", "piping"),
]

# Equipment ID patterns (with support for dashes, underscores, spaces)
EQUIPMENT_ID_PATTERNS = [
    # With separators first (more specific): K-06101, K_06101, K 06101
    r"(K[-_\s]\d{5})",  # K-06101, K_06101, K 06101
    r"(KT[-_\s]\d{5})",  # KT-06101, KT_06101, KT 06101
    r"(P[-_\s]\d{5})",  # P-06101, P_06101, P 06101
    r"(M[-_\s]\d{5})",  # M-06101, M_06101, M 06101
    r"(E[-_\s]\d{5})",  # E-06101, E_06101, E 06101
    r"(V[-_\s]\d{5})",  # V-06101, V_06101, V 06101
    r"(G[-_\s]\d{5})",  # G-06101, G_06101, G 06101
    # Standard format: K06101, KT06101, etc. (without separators)
    # Use lookahead/behind to match at word boundaries or delimiters
    r"(?<![A-Z0-9])(K\d{5})(?![A-Z0-9])",  # K06101
    r"(?<![A-Z0-9])(KT\d{5})(?![A-Z0-9])",  # KT06101
    r"(?<![A-Z0-9])(P\d{5})(?![A-Z0-9])",  # P06101
    r"(?<![A-Z0-9])(M\d{5})(?![A-Z0-9])",  # M06101 (motor)
    r"(?<![A-Z0-9])(E\d{5})(?![A-Z0-9])",  # E06101 (exchanger)
    r"(?<![A-Z0-9])(V\d{5})(?![A-Z0-9])",  # V06101 (vessel)
    r"(?<![A-Z0-9])(G\d{5})(?![A-Z0-9])",  # G06101 (gear)
]

# Vendor patterns
VENDOR_PATTERNS = [
    "HITACHI",
    "HTC",
    "SIEMENS",
    "ABB",
    "MITSUBISHI",
    "GE",
    "SULZER",
    "ATLAS COPCO",
    "ATLAS",
    "SCHNEIDER",
    "YOKOGAWA",
]


def extract_equipment_type(path_str: str) -> Optional[str]:
    """
    Extract equipment type from path.

    Args:
        path_str: File path (full or relative)

    Returns:
        Equipment type or None

    Examples:
        >>> extract_equipment_type("K06101_CO2 COMPRESSOR_HITACHI/Data/...")
        'compressor'
        >>> extract_equipment_type("KT06101_TURBINE_HTC/Manual/...")
        'turbine'
    """
    path_upper = path_str.upper()

    for pattern, eq_type in EQUIPMENT_PATTERNS:
        if re.search(pattern, path_upper):
            return eq_type

    return "unknown"


def extract_doc_type(path_str: str) -> Optional[str]:
    """
    Extract document type from path and filename.

    Args:
        path_str: File path (full or relative)

    Returns:
        Document type or None

    Examples:
        >>> extract_doc_type(".../Data/002_3N4-S4274343 datasheet.pdf")
        'datasheet'
        >>> extract_doc_type(".../Manual/Operation manual.pdf")
        'manual'
    """
    # Try folder-based first (more reliable)
    for pattern, doc_type in DOC_TYPE_PATTERNS:
        if re.search(pattern, path_str, re.IGNORECASE):
            return doc_type

    return "other"


def extract_equipment_id(path_str: str) -> Optional[str]:
    """
    Extract equipment ID from path or filename.

    Args:
        path_str: File path (full or relative)

    Returns:
        Equipment ID or None (normalized without separators)

    Examples:
        >>> extract_equipment_id("K06101_CO2 COMPRESSOR/Data/...")
        'K06101'
        >>> extract_equipment_id("K-06101_TURBINE/...")
        'K06101'
        >>> extract_equipment_id("KT_06101_MANUAL/...")
        'KT06101'
    """
    for pattern in EQUIPMENT_ID_PATTERNS:
        match = re.search(pattern, path_str, re.IGNORECASE)
        if match:
            # Normalize: remove separators (-, _, space) and convert to uppercase
            equipment_id = match.group(1).upper()
            equipment_id = (
                equipment_id.replace("-", "").replace("_", "").replace(" ", "")
            )
            return equipment_id

    return None


def extract_vendor(path_str: str) -> Optional[str]:
    """
    Extract vendor/manufacturer from path.

    Args:
        path_str: File path (full or relative)

    Returns:
        Vendor name or None

    Examples:
        >>> extract_vendor("K06101_CO2 COMPRESSOR_HITACHI/...")
        'HITACHI'
        >>> extract_vendor("KT06101_TURBINE_HTC/...")
        'HTC'
    """
    path_upper = path_str.upper()

    for vendor in VENDOR_PATTERNS:
        if vendor in path_upper:
            return vendor

    return None


def detect_language(path_str: str, text: Optional[str] = None) -> str:
    """
    Detect document language.

    Args:
        path_str: File path
        text: Optional text content for better detection

    Returns:
        Language code ('vi', 'en', etc.)

    Note:
        Currently defaults to 'vi' for this project.
        Can be enhanced with text-based detection if needed.
    """
    # Default to Vietnamese for this project
    # Can be enhanced with actual language detection later
    return "vi"


def extract_metadata_from_path(
    source_path: str, doc_id: Optional[str] = None, text: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """
    Extract all metadata from file path.

    Args:
        source_path: Full or relative file path
        doc_id: Optional document ID (for logging)
        text: Optional text content (for language detection)

    Returns:
        Dictionary with metadata fields:
        - equipment_type: str
        - doc_type: str
        - equipment_id: Optional[str]
        - vendor: Optional[str]
        - lang: str

    Examples:
        >>> metadata = extract_metadata_from_path(
        ...     "D:/Data_Raw/K06101_CO2 COMPRESSOR_HITACHI/Data/002_3N4-S4274343.pdf"
        ... )
        >>> metadata['equipment_type']
        'compressor'
        >>> metadata['equipment_id']
        'K06101'
        >>> metadata['vendor']
        'HITACHI'
    """
    metadata = {
        "equipment_type": extract_equipment_type(source_path),
        "doc_type": extract_doc_type(source_path),
        "equipment_id": extract_equipment_id(source_path),
        "vendor": extract_vendor(source_path),
        "lang": detect_language(source_path, text),
    }

    return metadata


def validate_metadata(metadata: Dict[str, Optional[str]]) -> bool:
    """
    Validate extracted metadata.

    Args:
        metadata: Extracted metadata dict

    Returns:
        True if metadata is valid (has at least equipment_type)
    """
    # Minimum requirement: must have equipment_type
    if not metadata.get("equipment_type") or metadata["equipment_type"] == "unknown":
        return False

    return True


def get_extraction_stats(metadatas: list) -> Dict[str, any]:
    """
    Get statistics about metadata extraction quality.

    Args:
        metadatas: List of metadata dicts

    Returns:
        Statistics dict with coverage percentages
    """
    total = len(metadatas)
    if total == 0:
        return {}

    stats = {
        "total": total,
        "equipment_type_coverage": sum(
            1
            for m in metadatas
            if m.get("equipment_type") and m["equipment_type"] != "unknown"
        )
        / total,
        "doc_type_coverage": sum(
            1 for m in metadatas if m.get("doc_type") and m["doc_type"] != "other"
        )
        / total,
        "equipment_id_coverage": sum(1 for m in metadatas if m.get("equipment_id"))
        / total,
        "vendor_coverage": sum(1 for m in metadatas if m.get("vendor")) / total,
    }

    return stats


# For testing
if __name__ == "__main__":
    # Test cases
    test_paths = [
        "D:\\Data_Raw\\K06101_CO2 COMPRESSOR_HITACHI\\Data\\002_3N4-S4274343 datasheet for K06101_Rev.02.pdf",
        "D:\\Data_Raw\\KT06101_TURBINE_HTC\\Manual\\Operating Manual KT06101.pdf",
        "D:\\Data_Raw\\K06101_CO2 COMPRESSOR_HITACHI\\Drawing\\Foundation drawing.pdf",
        "D:\\Data_Raw\\01. P&ID Ammonia Unit Rev12 (04000).pdf",
    ]

    print("Testing metadata extraction:")
    print("=" * 80)

    for path in test_paths:
        print(f"\nPath: {Path(path).name}")
        metadata = extract_metadata_from_path(path)
        for key, value in metadata.items():
            print(f"  {key}: {value}")
        print(f"  Valid: {validate_metadata(metadata)}")
