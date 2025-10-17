#!/usr/bin/env python
"""Test all CAD tag extraction imports"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 80)
print("TESTING CAD TAG EXTRACTION IMPORTS")
print("=" * 80)
print()

# Test 1: Config
try:
    from app.config import get_config

    config = get_config()
    print("[OK] Config loaded")
    print(f"  ENABLE_PID_TAGS: {config.ENABLE_PID_TAGS}")
    print(f"  LAYOUT_DIR: {config.LAYOUT_DIR}")
    print(f"  ENTITIES_DIR: {config.ENTITIES_DIR}")
    print(f"  TAGS_INDEX_NAME: {config.TAGS_INDEX_NAME}")
except Exception as e:
    print(f"[ERROR] Config failed: {e}")
    sys.exit(1)

print()

# Test 2: CADLikeGate
try:
    from app.ingestion.cadlike_gate import CADLikeGate, get_cadlike_gate

    gate = get_cadlike_gate()
    print("[OK] CADLikeGate")
except Exception as e:
    print(f"[ERROR] CADLikeGate failed: {e}")
    sys.exit(1)

# Test 3: PageLayoutBuilder
try:
    from app.ingestion.layout import PageLayout, PageLayoutBuilder, TextSpan

    builder = PageLayoutBuilder()
    print("[OK] PageLayoutBuilder")
except Exception as e:
    print(f"[ERROR] PageLayoutBuilder failed: {e}")
    sys.exit(1)

# Test 4: TagExtractor
try:
    from app.ingestion.tags import TagEntity, TagExtractor, TagParts

    extractor = TagExtractor()
    print("[OK] TagExtractor")
except Exception as e:
    print(f"[ERROR] TagExtractor failed: {e}")
    sys.exit(1)

# Test 5: CropGenerator
try:
    from app.ingestion.tags import CropGenerator

    cropper = CropGenerator()
    print("[OK] CropGenerator")
except Exception as e:
    print(f"[ERROR] CropGenerator failed: {e}")
    sys.exit(1)

# Test 6: Orchestrator
try:
    from app.ingestion.tags import TagExtractionOrchestrator

    orchestrator = TagExtractionOrchestrator()
    print("[OK] TagExtractionOrchestrator")
    print(f"  Enabled: {orchestrator.enabled}")
except Exception as e:
    print(f"[ERROR] TagExtractionOrchestrator failed: {e}")
    sys.exit(1)

# Test 7: Tags Retriever
try:
    from app.rag.indexers.opensearch_tags_retriever import OpenSearchTagsRetriever

    print("[OK] OpenSearchTagsRetriever")
except Exception as e:
    print(f"[ERROR] OpenSearchTagsRetriever failed: {e}")
    sys.exit(1)

# Test 8: Hybrid with Tags
try:
    from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever

    print("[OK] HybridWithTagsRetriever")
except Exception as e:
    print(f"[ERROR] HybridWithTagsRetriever failed: {e}")
    sys.exit(1)

# Test 9: Telemetry
try:
    from app.ingestion.tags import TelemetryLogger

    telemetry = TelemetryLogger()
    print("[OK] TelemetryLogger")
except Exception as e:
    print(f"[ERROR] TelemetryLogger failed: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("[SUCCESS] ALL IMPORTS OK")
print("=" * 80)
print()
print("Next steps:")
print("  1. Enable feature: ENABLE_PID_TAGS=true in .env")
print("  2. Create index: python scripts/opensearch/create_tags_index.py")
print("  3. Test: python tools/test_tag_extraction.py --pdf sample.pdf")
print()
