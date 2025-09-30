"""
Tag normalization and processing utilities for equipment tags
"""
import re
from typing import List, Optional, Set


def normalize_tag(tag: str) -> str:
    """
    Normalize equipment tag to standard format.

    Rules:
    - Convert to uppercase
    - Remove spaces and dashes
    - Keep alphanumeric characters only

    Examples:
        "06 PT001" -> "06PT001"
        "PT-001" -> "PT001"
        "04 FE 2046" -> "04FE2046"
        "e04217" -> "E04217"

    Args:
        tag: Raw tag string

    Returns:
        Normalized tag string
    """
    if not tag:
        return ""

    # Convert to uppercase
    tag = tag.upper()

    # Remove spaces, dashes, and other separators
    tag = re.sub(r"[\s\-_/\\]+", "", tag)

    # Keep only alphanumeric characters
    tag = re.sub(r"[^A-Z0-9]", "", tag)

    return tag


def extract_tags_from_text(text: str) -> List[str]:
    """
    Extract potential equipment tags from text.

    Patterns recognized:
    - Alphanumeric sequences like: KT06101, 04FE2046, E04217
    - With separators: 04-FE-2046, 06 PT 001
    - Mixed case: kt06101, Kt06101

    Args:
        text: Text to search for tags

    Returns:
        List of normalized tags found
    """
    if not text:
        return []

    # Pattern to match potential tags
    # Matches sequences of alphanumeric characters with optional separators
    # Examples: 04FE2046, 04-FE-2046, 04 FE 2046, KT06101
    patterns = [
        # Pattern 1: 2+ digits followed by 2+ letters followed by 3+ digits
        r"\b\d{2,}[\s\-_]?[A-Z]{2,}[\s\-_]?\d{3,}\b",
        # Pattern 2: 1-3 letters followed by digits (with optional separators)
        r"\b[A-Z]{1,3}[\s\-_]?\d{2,6}\b",
        # Pattern 3: Complex pattern with multiple segments (but must contain numbers)
        r"\b[A-Z0-9]{2,}(?:[\s\-_][A-Z0-9]{2,}){1,3}\b",
    ]

    # Convert text to uppercase for matching
    text_upper = text.upper()

    found_tags = set()
    for pattern in patterns:
        matches = re.findall(pattern, text_upper)
        for match in matches:
            normalized = normalize_tag(match)
            # Must be at least 4 chars and contain both letters and numbers
            if len(normalized) >= 4 and is_valid_tag(normalized):
                found_tags.add(normalized)

    return sorted(list(found_tags))


def is_valid_tag(tag: str) -> bool:
    """
    Check if a string is a valid equipment tag.

    Valid tags should:
    - Be at least 4 characters long
    - Contain both letters and numbers
    - Start with either digits or specific prefixes (KT, PT, FE, etc.)

    Args:
        tag: Tag to validate

    Returns:
        True if valid tag format
    """
    normalized = normalize_tag(tag)

    if len(normalized) < 4:
        return False

    # Must contain both letters and numbers
    has_letter = any(c.isalpha() for c in normalized)
    has_digit = any(c.isdigit() for c in normalized)

    if not (has_letter and has_digit):
        return False

    # Check for common tag patterns
    # Pattern 1: Starts with 2+ digits (e.g., 04FE2046)
    if re.match(r"^\d{2,}[A-Z]+\d+", normalized):
        return True

    # Pattern 2: Starts with known prefixes
    known_prefixes = [
        "KT",
        "PT",
        "FE",
        "FI",
        "PI",
        "TI",
        "LI",
        "PG",
        "TG",
        "E",
        "P",
        "V",
        "XV",
        "HV",
        "LV",
        "CV",
        "PCV",
        "FCV",
    ]
    for prefix in known_prefixes:
        if normalized.startswith(prefix) and len(normalized) > len(prefix):
            return True

    return False


def split_multi_line_tag(lines: List[str]) -> Optional[str]:
    """
    Handle P&ID tags that may be split across multiple lines.

    Example:
        Line 1: "04"
        Line 2: "PT"
        Line 3: "4264"
        Result: "04PT4264"

    Args:
        lines: List of text lines that may contain tag parts

    Returns:
        Normalized tag if found, None otherwise
    """
    if not lines:
        return None

    # Concatenate lines and try to extract tag
    combined = "".join(lines)
    tags = extract_tags_from_text(combined)

    if tags:
        return tags[0]  # Return first valid tag found

    # Try alternative: look for pattern across lines
    # This handles cases where tag parts are on separate lines
    parts = []
    for line in lines:
        line = line.strip()
        if re.match(r"^[A-Z0-9\-\s]+$", line.upper()) and len(line) <= 10:
            parts.append(line)

    if len(parts) >= 2:
        combined = "".join(parts)
        normalized = normalize_tag(combined)
        if is_valid_tag(normalized):
            return normalized

    return None


def find_tag_variations(tag: str) -> Set[str]:
    """
    Generate possible variations of a tag for searching.

    For example, "04FE2046" might appear as:
    - "04FE2046"
    - "04-FE-2046"
    - "04 FE 2046"
    - "FE2046" (without unit prefix)
    - "FE-2046"

    Args:
        tag: Normalized tag

    Returns:
        Set of possible variations
    """
    if not tag:
        return set()

    variations = {tag}  # Include original

    # Try to split tag into components
    # Pattern: unit (2 digits) + type (2-3 letters) + number (3-4 digits)
    match = re.match(r"^(\d{2})?([A-Z]{2,3})(\d{3,4})$", tag)
    if match:
        unit, type_code, number = match.groups()

        if unit:
            # With unit prefix
            variations.add(f"{unit}{type_code}{number}")
            variations.add(f"{unit}-{type_code}-{number}")
            variations.add(f"{unit} {type_code} {number}")
            variations.add(f"{unit}_{type_code}_{number}")

            # Without unit prefix
            variations.add(f"{type_code}{number}")
            variations.add(f"{type_code}-{number}")
            variations.add(f"{type_code} {number}")
        else:
            # No unit prefix
            variations.add(f"{type_code}{number}")
            variations.add(f"{type_code}-{number}")
            variations.add(f"{type_code} {number}")

    # Add lowercase variations for searching
    variations_lower = {v.lower() for v in variations}
    variations.update(variations_lower)

    return variations


# Common equipment type codes for reference
EQUIPMENT_CODES = {
    "FE": "Flow Element",
    "FI": "Flow Indicator",
    "FT": "Flow Transmitter",
    "PT": "Pressure Transmitter",
    "PI": "Pressure Indicator",
    "PG": "Pressure Gauge",
    "TI": "Temperature Indicator",
    "TT": "Temperature Transmitter",
    "LI": "Level Indicator",
    "LT": "Level Transmitter",
    "XV": "On/Off Valve",
    "HV": "Hand Valve",
    "CV": "Control Valve",
    "PCV": "Pressure Control Valve",
    "FCV": "Flow Control Valve",
    "E": "Heat Exchanger",
    "P": "Pump",
    "C": "Compressor",
    "V": "Vessel",
    "T": "Tank",
    "KT": "Knockout Tank",
}


def get_equipment_type(tag: str) -> Optional[str]:
    """
    Get equipment type description from tag.

    Args:
        tag: Equipment tag

    Returns:
        Equipment type description if recognized
    """
    normalized = normalize_tag(tag)

    # Check longer codes first to avoid false matches
    # Sort by length descending
    sorted_codes = sorted(
        EQUIPMENT_CODES.items(), key=lambda x: len(x[0]), reverse=True
    )

    for code, description in sorted_codes:
        # Check if code appears in the tag
        # For single letter codes, ensure they're followed by digits
        if len(code) == 1:
            # Single letter codes must be followed by digits
            if re.search(rf"^{code}\d|\d{code}\d", normalized):
                return description
        else:
            # Multi-letter codes can appear anywhere
            if code in normalized:
                return description

    return None
