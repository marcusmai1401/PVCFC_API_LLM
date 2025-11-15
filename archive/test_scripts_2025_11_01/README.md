# Test Scripts Archive - 2025-11-01

## Purpose

These scripts were used during the chunk merging and ingestion pipeline investigation on 2025-11-01.

## Scripts Included

### Analysis Scripts
- **analyze_chunk_sizes.py** - Analyze chunk size distribution after ingestion
- **check_final_results.py** - Check final ingestion results
- **check_ingestion.py** - Quick ingestion sanity check

### Testing Scripts
- **test_chunk_merging.py** - Test chunk merge logic (small chunks merged with neighbors)
- **test_page_aware_chunking.py** - Test page-aware chunking strategy
- **test_page_detection_simple.py** - Simple page detection test
- **test_dotenv.py** - Test .env file loading

### Verification Scripts
- **check_cad_score.py** - Check CAD-like detection score for P&ID documents
- **check_test_results.py** - Check test output formatting
- **verify_system.py** - System verification and health check

## Investigation Context

**Date**: 2025-11-01
**Issues Addressed**:
- Chunk size distribution problems (too many small chunks)
- CAD-like detection threshold tuning (0.60 → 0.55)
- Chunk merging feature implementation
- Tags preservation fix (.env loading issues)

**Results**:
- ✅ All features verified working
- ✅ Chunk merging successfully deployed
- ✅ CAD-like detection accurate
- ✅ Tags preservation fixed

## Status

All scripts were **one-time verification tools**. Features tested are now in production and working correctly.

**Archived**: 2025-11-01
**Reason**: Cleanup root directory, keep for historical reference
