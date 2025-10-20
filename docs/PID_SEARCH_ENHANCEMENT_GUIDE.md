# P&ID Search Enhancement - User Guide

## New Query Capabilities

The P&ID search system now supports flexible, component-based queries with improved tag understanding.

### Query Types

#### 1. SUFFIX-only Query (NEW!)

Search by equipment number only when you don't know the full tag.

**Examples:**
```
Query: "5153"
Result:
  - 04 PAHH 5153A/B/C (page 54)
  - 04 PALL 5153A/B/C (page 54)
  - 04 PI 5153A/B/C (page 54)
  - 04 PXT 5153A/B/C (page 54)

Warning: "4 different prefixes found for suffix 5153"
Suggestion: "Refine with PREFIX: try 'PAHH 5153' or add UNIT: '04 5153'"
```

**When to use:**
- You only remember the number
- Quick lookup across multiple instruments
- Exploring what instruments share a number

#### 2. Component-based Query (NEW!)

Mix and match components for flexible searching.

**Examples:**

**UNIT + SUFFIX:**
```
Query: "04 5153"
Result: All tags in UNIT 04 with SUFFIX 5153
  - 04 PAHH 5153A/B/C
  - 04 PALL 5153A/B/C
  - 04 PI 5153A/B/C
  - 04 PXT 5153A/B/C
```

**PREFIX + SUFFIX:**
```
Query: "PAHH 5153"
Result: All PAHH tags with SUFFIX 5153
  - 04 PAHH 5153A/B/C (page 54)
```

**UNIT + PREFIX:**
```
Query: "04 PAHH"
Result: All PAHH instruments in UNIT 04
  - 04 PAHH 5145
  - 04 PAHH 5153A/B/C
  - ... (all PAHH tags in unit 04)
```

**When to use:**
- Partial information searches
- Finding all instruments of a type in a unit
- Narrowing down from broad to specific

#### 3. Full Tag Query (IMPROVED!)

Search with complete tag, now handles annotations automatically.

**Examples:**
```
Query: "04 PAHH 5153"
Matches:
  - "04 PAHH 5153" (exact)
  - "04 PAHH 5153A/B/C" (with annotation)
  - "04 PAHH 5153 2oo3" (with voting logic)

Note: Annotations (A/B/C, 1oo2) are automatically separated
```

**When to use:**
- You know the complete tag
- Looking for specific instrument
- Most precise results

### Tag Structure

Tags are now parsed into distinct components:

```
Full tag: "04 PAHH 5153A/B/C"

Components:
  UNIT: "04"         (1-3 digits, area/process unit)
  PREFIX: "PAHH"     (2-6 letters, instrument type)
  SUFFIX: "5153"     (3-5 digits only, equipment number)
  VARIANT: ""        (A/B/C if present, not in this example)
  ANNOTATION: "A/B/C" (choice notation or voting logic)
```

### Multi-prefix Scenarios

When multiple instrument types share the same number:

**Example:**
```
Query: "5153"

Grouped Results:
  Group 1: UNIT=04, SUFFIX=5153
    Prefixes: PAHH, PALL, PI, PXT (4 types)
    All on page 54 (co-located)

    Tags:
    - 04 PAHH 5153A/B/C - Pressure Alarm High-High
    - 04 PALL 5153A/B/C - Pressure Alarm Low-Low
    - 04 PI 5153A/B/C   - Pressure Indicator
    - 04 PXT 5153A/B/C  - Pressure Transmitter

Interpretation:
  These 4 instruments form a measurement/control group
  All monitor the same point/equipment (5153)
  Located together on same drawing (page 54)
```

**Refinement strategies:**
1. Add PREFIX: `"PAHH 5153"` → Only pressure alarm high-high
2. Add UNIT: `"04 5153"` → Only in unit 04 (may still have multiple prefixes)
3. Add both: `"04 PAHH 5153"` → Most specific

### Supported Patterns

#### UNIT (Process Unit / Area)
- **Format**: 1-3 digits
- **Examples**: `4`, `04`, `120`
- **Note**: Not always zero-padded

#### PREFIX (Instrument Type)
- **Format**: 2-6 CAPITAL letters
- **Examples**:
  - 2 letters: `IS`, `PI`, `PT`
  - 3 letters: `PAL`, `TAH`, `FIC`
  - 4 letters: `PAHH`, `PALL`, `PSAL`, `TAHH`
  - 5 letters: `PDAHH`, `PDALL`, `FFSAL`
  - 6 letters: Usually labels (HEADER, HEIGHT)

**Important**: `TAH` and `TAHH` are DIFFERENT prefixes!
- `TAH` = Temperature Alarm High
- `TAHH` = Temperature Alarm High-High

#### SUFFIX (Equipment Number)
- **Format**: 3-5 digits only (no letters)
- **Examples**: `501`, `2207`, `5153`, `22076`
- **Note**: Always pure digits in component field

#### VARIANT (Parallel Branch)
- **Format**: Single letter (A, B, or C)
- **Examples**: `A`, `B`, `C`
- **Usage**: Indicates parallel/redundant equipment
- **Example**: `04 ZSL 4047A` has variant=A

#### ANNOTATION (Choices & Logic)
- **Formats**:
  - Choice notation: `A/B`, `A/B/C`
  - Voting logic: `1oo2`, `2oo3`
- **Examples**:
  - `04 PAHH 5153A/B/C` → Choice between A, B, or C
  - `04 PSAL 2207 2oo3` → 2-out-of-3 voting
- **Note**: Separated from core tag for better matching

### API Response Format

#### SUFFIX-only Search Response

```json
{
  "query": "5153",
  "total_tags": 4,
  "has_ambiguity": true,
  "clarification": "Multiple instrument types found. Refine with PREFIX or UNIT.",
  "found_prefixes": ["PAHH", "PALL", "PI", "PXT"],
  "suggestion": "Try: 'PAHH 5153' or '04 5153'",
  "results": [
    {
      "unit": "04",
      "suffix": "5153",
      "prefixes": ["PAHH", "PALL", "PI", "PXT"],
      "pages": [54],
      "co_located": true,
      "warning": "4 different prefixes found for suffix 5153",
      "tags": [
        {
          "tag": "04 PAHH 5153A/B/C",
          "page": 54,
          "bbox": [x0, y0, x1, y1],
          "components": {
            "unit": "04",
            "prefix": "PAHH",
            "suffix": "5153",
            "variant": "",
            "annotation": "A/B/C"
          }
        },
        ...
      ]
    }
  ]
}
```

#### Component Search Response

```json
{
  "query": "04 PAHH 5153",
  "query_type": "component_search",
  "components_used": {
    "unit": "04",
    "prefix": "PAHH",
    "suffix": "5153"
  },
  "total_results": 1,
  "tags": [
    {
      "tag": "04 PAHH 5153A/B/C",
      "page": 54,
      "doc_id": "DOCID_xxx",
      "bbox": [x0, y0, x1, y1],
      "crop_path": "crops/xxx.png",
      "components": {
        "unit": "04",
        "prefix": "PAHH",
        "suffix": "5153",
        "variant": "",
        "annotation": "A/B/C"
      }
    }
  ]
}
```

### Best Practices

#### When to use each query type:

**Use SUFFIX-only when:**
- You only remember the equipment number
- Exploring related instruments
- Quick lookup across the system

**Use Component queries when:**
- You want to narrow down gradually
- Exploring instruments in a specific unit
- Finding all instruments of a type

**Use Full tag when:**
- You know the exact tag
- Need precise results
- Verifying a specific instrument

### Common Prefixes

| Prefix | Full Name | Category |
|--------|-----------|----------|
| **PAHH** | Pressure Alarm High-High | Alarm |
| **PALL** | Pressure Alarm Low-Low | Alarm |
| **PAL** | Pressure Alarm Low | Alarm |
| **PSAL** | Pressure Switch Alarm Low | Alarm |
| **PSAH** | Pressure Switch Alarm High | Alarm |
| **PI** | Pressure Indicator | Indicator |
| **PT** | Pressure Transmitter | Transmitter |
| **PXT** | Pressure Transmitter (variant) | Transmitter |
| **PIC** | Pressure Indicator Controller | Controller |
| **TAH** | Temperature Alarm High | Alarm |
| **TAHH** | Temperature Alarm High-High | Alarm |
| **LSH** | Level Switch High | Switch |
| **LSHH** | Level Switch High-High | Switch |
| **FIC** | Flow Indicator Controller | Controller |
| **IS** | Instrument Switch | Switch |
| **ZSL** | Position Switch Low | Switch |

### Troubleshooting

**Query returns too many results:**
- Add more components: "5153" → "04 5153" → "04 PAHH 5153"

**Query returns no results:**
- Try broader: "04 PAHH 5153" → "PAHH 5153" → "5153"
- Check spelling of PREFIX
- Verify UNIT number

**Ambiguity warning shown:**
- This is expected for SUFFIX-only queries
- Use the suggested refinements
- Review all prefixes listed to find the right instrument

**Tag not found:**
- Check if tag exists in the P&ID
- Try variant: "04 PAHH 5153" vs "04 PAHH 5153A"
- Check page number

### Examples from Actual P&ID

Based on Ammonia Unit P&ID (117 pages):

```python
# Example 1: Finding pressure instruments for equipment 5153
query = "5153"
# Returns: PAHH, PALL, PI, PXT (4 instruments, all on page 54)

# Example 2: Specific pressure alarm
query = "04 PAHH 5153"
# Returns: 04 PAHH 5153A/B/C (exact match)

# Example 3: All instruments in unit 04 with number 501
query = "04 501"
# Returns: 04 IS 501 (instrument switch, pages 53-54)

# Example 4: All PSAL instruments
query = "PSAL"
# Returns: All PSAL (Pressure Switch Alarm Low) tags across the P&ID

# Example 5: Temperature alarms
query = "TAH"
# Returns: All TAH tags (not TAHH - they're different!)
```

### Migration Status

After migration, the system can handle:
- ✅ UNIT variations (1, 04, 120)
- ✅ PREFIX variations (IS, PAHH, PDAHH)
- ✅ SUFFIX-only queries (5153, 501)
- ✅ Component combinations (04 5153, PAHH 5153)
- ✅ Annotation separation (A/B/C, 1oo2)
- ✅ Multi-prefix grouping and warnings
- ✅ Co-location indicators

### Performance

Expected performance after migration:
- **SUFFIX-only search**: ~100-200ms
- **Component search**: ~50-150ms
- **Full tag search**: ~50-100ms
- **Multi-prefix grouping**: +20-50ms overhead

Total query time: <500ms (including retrieval + formatting)

## Support

For questions or issues:
1. Review validation report
2. Check migration logs
3. Consult README_MIGRATION.md
4. Contact system maintainer
