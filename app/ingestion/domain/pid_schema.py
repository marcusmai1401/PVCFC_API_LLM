"""
P&ID Domain Schema

Defines equipment tags, normalization rules, and synonym dictionaries
for P&ID diagram processing.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class EquipmentType(Enum):
    """Equipment types in P&ID diagrams"""

    PUMP = "Pump"
    HEAT_EXCHANGER = "HeatExchanger"
    VALVE = "Valve"
    COMPRESSOR = "Compressor"
    TANK = "Tank"
    VESSEL = "Vessel"
    INSTRUMENT = "Instrument"
    MOTOR = "Motor"
    FILTER = "Filter"
    SEPARATOR = "Separator"
    UNKNOWN = "Unknown"


@dataclass
class EquipmentTag:
    """Represents an equipment tag extracted from P&ID"""

    tag: str  # Original tag (e.g., "P-101")
    normalized_tag: str  # Normalized form (e.g., "P-101")
    equipment_type: EquipmentType
    prefix: str  # E.g., "P"
    number: str  # E.g., "101"
    suffix: Optional[str] = None  # E.g., "A" in "P-101A"


# Equipment prefix mapping
EQUIPMENT_PREFIX_MAP = {
    "P": EquipmentType.PUMP,
    "HX": EquipmentType.HEAT_EXCHANGER,
    "E": EquipmentType.HEAT_EXCHANGER,  # Also heat exchangers
    "V": EquipmentType.VALVE,
    "C": EquipmentType.COMPRESSOR,
    "K": EquipmentType.COMPRESSOR,
    "T": EquipmentType.TANK,
    "D": EquipmentType.VESSEL,
    "FI": EquipmentType.INSTRUMENT,
    "PI": EquipmentType.INSTRUMENT,
    "TI": EquipmentType.INSTRUMENT,
    "LI": EquipmentType.INSTRUMENT,
    "M": EquipmentType.MOTOR,
    "F": EquipmentType.FILTER,
    "S": EquipmentType.SEPARATOR,
}


# Synonyms dictionary (Vietnamese / English)
EQUIPMENT_SYNONYMS = {
    # Pumps
    "bơm": ["pump", "bơm ly tâm", "centrifugal pump"],
    "pump": ["bơm", "bơm ly tâm"],
    "bơm ly tâm": ["centrifugal pump", "pump", "bơm"],
    "centrifugal pump": ["bơm ly tâm", "pump", "bơm"],
    # Heat Exchangers
    "thiết bị trao đổi nhiệt": ["heat exchanger", "exchanger", "HX"],
    "heat exchanger": ["thiết bị trao đổi nhiệt", "exchanger", "HX"],
    # Valves
    "van": ["valve", "van điều khiển"],
    "valve": ["van", "van điều khiển"],
    "van điều khiển": ["control valve", "valve", "van"],
    "control valve": ["van điều khiển", "valve", "van"],
    # Compressors
    "máy nén": ["compressor", "máy nén khí"],
    "compressor": ["máy nén", "máy nén khí"],
    "máy nén khí": ["gas compressor", "compressor", "máy nén"],
    # Tanks
    "bể chứa": ["tank", "storage tank", "bể"],
    "tank": ["bể chứa", "bể", "storage tank"],
    "bể": ["tank", "bể chứa"],
    # Common units
    "PSI": ["psi", "pound per square inch"],
    "GPM": ["gpm", "gallon per minute"],
    "RPM": ["rpm", "vòng/phút", "revolution per minute"],
    "HP": ["hp", "mã lực", "horsepower"],
    "kW": ["kw", "kilowatt"],
}


def normalize_tag(tag: str) -> str:
    """
    Normalize equipment tag.

    Rules:
    - Convert to uppercase
    - Remove extra spaces
    - Ensure hyphen between prefix and number
    - Strip vendor prefixes if present

    Args:
        tag: Raw tag string

    Returns:
        Normalized tag
    """
    # Convert to uppercase
    tag = tag.upper().strip()

    # Remove extra spaces
    tag = " ".join(tag.split())

    # Strip common vendor prefixes (e.g., "ABC-P-101" → "P-101")
    # Pattern: Vendor code followed by equipment tag
    tag = re.sub(r"^[A-Z]{2,4}-([A-Z]{1,3}-\d+)", r"\1", tag)

    # Ensure hyphen between prefix and number
    # Pattern: Letter(s) followed by digit(s)
    tag = re.sub(r"^([A-Z]{1,3})(\d+)", r"\1-\2", tag)

    return tag


def parse_equipment_tag(tag_text: str) -> Optional[EquipmentTag]:
    """
    Parse equipment tag from text.

    Args:
        tag_text: Text containing equipment tag

    Returns:
        EquipmentTag object or None if not valid
    """
    # Normalize first
    normalized = normalize_tag(tag_text)

    # Pattern: PREFIX-NUMBER(SUFFIX)?
    # Examples: P-101, HX-202A, FI-301
    pattern = r"^([A-Z]{1,3})-?(\d{2,4})([A-Z])?$"
    match = re.match(pattern, normalized)

    if not match:
        return None

    prefix = match.group(1)
    number = match.group(2)
    suffix = match.group(3)

    # Determine equipment type
    equipment_type = EQUIPMENT_PREFIX_MAP.get(prefix, EquipmentType.UNKNOWN)

    # Build normalized tag
    normalized_tag = f"{prefix}-{number}"
    if suffix:
        normalized_tag += suffix

    return EquipmentTag(
        tag=tag_text,
        normalized_tag=normalized_tag,
        equipment_type=equipment_type,
        prefix=prefix,
        number=number,
        suffix=suffix,
    )


def extract_tags_from_text(text: str) -> List[EquipmentTag]:
    """
    Extract all equipment tags from text.

    Args:
        text: Input text

    Returns:
        List of EquipmentTag objects
    """
    # Pattern for equipment tags
    pattern = r"\b([A-Z]{1,3})-?(\d{2,4}[A-Z]?)\b"

    matches = re.findall(pattern, text)
    tags = []

    for prefix, number in matches:
        tag_text = f"{prefix}-{number}"
        parsed_tag = parse_equipment_tag(tag_text)

        if parsed_tag:
            tags.append(parsed_tag)

    return tags


def get_synonyms(term: str) -> List[str]:
    """
    Get synonyms for a term.

    Args:
        term: Input term

    Returns:
        List of synonyms (including the term itself)
    """
    term_lower = term.lower()

    if term_lower in EQUIPMENT_SYNONYMS:
        return [term] + EQUIPMENT_SYNONYMS[term_lower]

    # Check if term is in any synonym list
    for key, synonyms in EQUIPMENT_SYNONYMS.items():
        if term_lower in [s.lower() for s in synonyms]:
            return [term, key] + [s for s in synonyms if s.lower() != term_lower]

    return [term]


def normalize_unit(text: str) -> str:
    """
    Normalize units in text.

    Examples:
    - "150 psi" → "150 PSI"
    - "250 Gpm" → "250 GPM"
    - "3560 rpm" → "3560 RPM"

    Args:
        text: Input text

    Returns:
        Text with normalized units
    """
    # Common unit patterns
    unit_patterns = [
        (r"\b(\d+(?:\.\d+)?)\s*psi\b", r"\1 PSI"),
        (r"\b(\d+(?:\.\d+)?)\s*gpm\b", r"\1 GPM"),
        (r"\b(\d+(?:\.\d+)?)\s*rpm\b", r"\1 RPM"),
        (r"\b(\d+(?:\.\d+)?)\s*hp\b", r"\1 HP"),
        (r"\b(\d+(?:\.\d+)?)\s*kw\b", r"\1 kW"),
        (r"\b(\d+(?:\.\d+)?)\s*°?f\b", r"\1°F"),
        (r"\b(\d+(?:\.\d+)?)\s*°?c\b", r"\1°C"),
    ]

    result = text
    for pattern, replacement in unit_patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Compute simple text similarity based on shared tokens.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0.0 to 1.0)
    """
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)

    return len(intersection) / len(union) if union else 0.0
