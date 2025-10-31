"""Test CAD-like gate on Ammonia PDF to see actual score"""
import sys

sys.path.insert(0, ".")

from pathlib import Path

from app.ingestion.cadlike_gate import get_cadlike_gate

pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")

print("=" * 80)
print("CAD-LIKE GATE TEST - Ammonia PDF")
print("=" * 80)
print(f"PDF: {pdf_path.name}")
print(f"Exists: {pdf_path.exists()}")
print()

gate = get_cadlike_gate()

print("Evaluating CAD-like score...")
decision = gate.evaluate(pdf_path)

print("\nGate Decision:")
print(f"  is_cadlike: {decision.is_cadlike}")
print(f"  score: {decision.score:.3f}")
print(f"  threshold: {gate.thresholds['cadlike']}")
print(f"  gray_zone_low: {gate.thresholds['gray_zone_low']}")
print(f"  boosted_by_filename: {decision.boosted_by_filename}")
print()

print("Feature Scores:")
for feature, score in decision.features.items():
    print(f"  {feature}: {score:.3f}")

print()
print(f"Pages sampled: {decision.pages_sampled}")
print(f"Taggy pages: {len(decision.taggy_pages)} pages")
print(f"Taggy pages list: {decision.taggy_pages[:20]}...")

if decision.is_cadlike:
    print("\nResult: PASS - Will extract tags")
else:
    print(
        f"\nResult: FAIL - Score {decision.score:.3f} < threshold {gate.thresholds['cadlike']}"
    )
    print("Tags will NOT be extracted")
