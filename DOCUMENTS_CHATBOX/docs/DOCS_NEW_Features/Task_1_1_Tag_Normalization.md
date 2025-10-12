# Task 1.1: Tag Normalization Utilities
**Status**: ✅ COMPLETED
**Date**: 2025-09-27
**Module**: Foundation - Data & Metadata

## Overview
Implemented comprehensive tag normalization and processing utilities for equipment tags to support the Device Search and Page Jump features.

## Implementation Details

### Files Created
1. **`app/utils/tag_utils.py`** - Main utility module with the following functions:
   - `normalize_tag(tag)`: Normalizes equipment tags to standard format
   - `extract_tags_from_text(text)`: Extracts equipment tags from text
   - `is_valid_tag(tag)`: Validates tag format
   - `split_multi_line_tag(lines)`: Handles P&ID tags split across lines
   - `find_tag_variations(tag)`: Generates search variations
   - `get_equipment_type(tag)`: Identifies equipment type from tag

2. **`tests/test_tag_utils.py`** - Comprehensive unit tests (19 tests, all passing)

### Key Features

#### Tag Normalization Rules
- Convert to uppercase
- Remove spaces, dashes, underscores, slashes
- Keep only alphanumeric characters
- Examples:
  - `"06 PT001"` → `"06PT001"`
  - `"04-FE-2046"` → `"04FE2046"`
  - `"e04217"` → `"E04217"`

#### Tag Extraction Patterns
- Recognizes various equipment tag formats:
  - Unit + Type + Number: `04FE2046`
  - Type + Number: `PT001`, `KT06101`
  - With separators: `04-FE-2046`, `06 PT 001`
  - Mixed case: `kt06101`, `Kt06101`

#### Equipment Type Recognition
Supports 20+ equipment codes including:
- Flow: FE, FI, FT
- Pressure: PT, PI, PG
- Temperature: TI, TT
- Level: LI, LT
- Valves: XV, HV, CV, PCV, FCV
- Equipment: E, P, C, V, T, KT

#### Multi-line Tag Support
Handles P&ID tags that may be split across multiple lines:
```
Line 1: "04"
Line 2: "PT"
Line 3: "4264"
Result: "04PT4264"
```

#### Tag Variations Generation
Generates search variations for better matching:
- `"04FE2046"` generates:
  - `"04FE2046"`, `"04-FE-2046"`, `"04 FE 2046"`
  - `"FE2046"`, `"FE-2046"` (without unit prefix)
  - Lowercase versions for case-insensitive search

## Usage Examples

```python
from app.utils.tag_utils import normalize_tag, extract_tags_from_text, get_equipment_type

# Normalize a tag
normalized = normalize_tag("04-FE-2046")  # Returns: "04FE2046"

# Extract tags from text
text = "Check equipment KT06101 and valve 04-FE-2046"
tags = extract_tags_from_text(text)  # Returns: ["04FE2046", "KT06101"]

# Get equipment type
equipment_type = get_equipment_type("04FE2046")  # Returns: "Flow Element"
```

## Testing
- All 19 unit tests pass
- Test coverage includes:
  - Basic normalization
  - Special character handling
  - Mixed case conversion
  - Tag extraction from complex text
  - Tag validation
  - Multi-line tag handling
  - Variation generation
  - Equipment type identification

## Integration Points
This module will be used by:
- **Ingestion Pipeline**: To normalize tags during document processing
- **Search/Retrieval**: To generate tag variations for better matching
- **UI Components**: To normalize user input and display equipment types
- **API Endpoints**: To validate and process tag-based queries

## Next Steps
- Task 1.2: Sync metadata "page" field across BM25/FAISS indices
- Task 1.3: PDF page image rendering pipeline
- Task 1.4: Document classification with LLM
