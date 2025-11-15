"""
Check CAD-like detection score for P&ID Ammonia file
"""
import sys
from pathlib import Path

from app.ingestion.pdf_processor import PDFProcessor
from app.ingestion.tags.orchestrator import TagExtractionOrchestrator

# File path
pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")

if not pdf_path.exists():
    print(f"❌ File not found: {pdf_path}")
    sys.exit(1)

print("=" * 80)
print("CAD-LIKE DETECTION ANALYSIS")
print("=" * 80)
print(f"File: {pdf_path.name}")
print(f"Total pages: {pdf_path.stat().st_size / (1024*1024):.1f} MB")

# Extract text from PDF
processor = PDFProcessor(enable_ocr=False, extract_tables=False)
pdf_doc = processor.process_pdf(pdf_path)

print(f"\nExtracted text from {pdf_doc.num_pages} pages")

# Initialize orchestrator
orchestrator = TagExtractionOrchestrator()

# Run gate check on document
print("\n" + "=" * 80)
print("RUNNING CAD-LIKE GATE CHECK")
print("=" * 80)

# Get config thresholds
from app.config.pipeline_config import PipelineConfig

config = PipelineConfig()
print(f"\nConfiguration:")
print(f"  ENABLE_PID_TAGS: {config.ENABLE_PID_TAGS}")
print(f"  GATE_MODE: {config.GATE_MODE}")
print(f"  GATE_THRESHOLD: {config.GATE_THRESHOLD}")
print(f"  GRAY_ZONE_LOW: {config.GRAY_ZONE_LOW}")

# Run gate scorer on first few pages
from app.ingestion.tags.gate_scorer import GateScorer

scorer = GateScorer()

# Sample pages to check
sample_pages = [1, 2, 10, 50, 100]
print(f"\n📊 Testing pages: {sample_pages}")

for page_num in sample_pages:
    if page_num > pdf_doc.num_pages:
        continue

    page_content = pdf_doc.pages[page_num - 1]
    page_text = page_content.text
    if not page_text:
        print(f"\n  Page {page_num}: No text found")
        continue

    # Run scorer
    score_result = scorer.score_page(page_text)

    print(f"\n  Page {page_num}:")
    print(f"    Score: {score_result.get('total_score', 0):.2f}")
    print(
        f"    Pass threshold ({config.GATE_THRESHOLD})? {score_result.get('total_score', 0) >= config.GATE_THRESHOLD}"
    )
    print(f"    Breakdown:")
    for key, value in score_result.items():
        if key != "total_score" and isinstance(value, (int, float)):
            print(f"      {key}: {value}")

# Check document-level decision
print("\n" + "=" * 80)
print("DOCUMENT-LEVEL DECISION")
print("=" * 80)

# Compute average score across sampled pages
avg_score = 0
valid_pages = 0
for page_num in sample_pages:
    if page_num > pdf_doc.num_pages:
        continue
    page_text = pdf_doc.pages[page_num - 1].text
    if page_text:
        score_result = scorer.score_page(page_text)
        avg_score += score_result.get("total_score", 0)
        valid_pages += 1

if valid_pages > 0:
    avg_score /= valid_pages
    print(f"\nAverage CAD-like score (across {valid_pages} pages): {avg_score:.2f}")
    print(f"Threshold: {config.GATE_THRESHOLD}")
    print(f"Gray zone: {config.GRAY_ZONE_LOW} - {config.GATE_THRESHOLD}")

    if avg_score >= config.GATE_THRESHOLD:
        print("\n✅ Document PASSES CAD-like detection → Tags should be extracted")
    elif avg_score >= config.GRAY_ZONE_LOW:
        print("\n⚠️  Document in GRAY ZONE → Borderline case")
    else:
        print("\n❌ Document FAILS CAD-like detection → No tags extracted")
        print("\n💡 Possible reasons:")
        print("  1. Text-heavy pages (not typical for CAD drawings)")
        print("  2. Low symbol/code token density")
        print("  3. Missing typical P&ID patterns")
else:
    print("\n❌ No valid pages to analyze")

print("=" * 80)
