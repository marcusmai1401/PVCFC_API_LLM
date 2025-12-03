#!/usr/bin/env python
"""Comprehensive verification of page fix"""

import sys
from collections import Counter
from pathlib import Path

import weaviate
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

# Connect
client = weaviate.connect_to_local(
    host=settings.weaviate_host,
    port=settings.weaviate_port,
)

collection = client.collections.get(settings.weaviate_collection)

print("\n" + "=" * 80)
print("COMPREHENSIVE PAGE NUMBER VERIFICATION")
print("=" * 80 + "\n")

# 1. Count all objects
print("1. TOTAL COUNT")
print("-" * 80)
all_objects = []
cursor = None
batch_size = 100

while True:
    if cursor:
        response = collection.query.fetch_objects(
            limit=batch_size,
            after=cursor,
            return_properties=["page", "text", "doc_id"],
        )
    else:
        response = collection.query.fetch_objects(
            limit=batch_size,
            return_properties=["page", "text", "doc_id"],
        )

    if not response.objects:
        break

    all_objects.extend(response.objects)

    if len(response.objects) < batch_size:
        break

    cursor = response.objects[-1].uuid

total_count = len(all_objects)
print(f"Total objects in Weaviate: {total_count}")
print()

# 2. Page statistics
print("2. PAGE NUMBER STATISTICS")
print("-" * 80)

page_none = 0
page_zero = 0
page_valid = 0
page_values = []

for obj in all_objects:
    page = obj.properties.get("page")

    if page is None:
        page_none += 1
    elif page == 0:
        page_zero += 1
    else:
        page_valid += 1
        page_values.append(page)

print(f"Page = None:  {page_none:>6} ({page_none/total_count*100:>5.1f}%)")
print(f"Page = 0:     {page_zero:>6} ({page_zero/total_count*100:>5.1f}%)")
print(f"Page > 0:     {page_valid:>6} ({page_valid/total_count*100:>5.1f}%)")
print()

if page_valid > 0:
    print(f"Valid page stats:")
    print(f"  Min page:  {min(page_values)}")
    print(f"  Max page:  {max(page_values)}")
    print(f"  Avg page:  {sum(page_values)/len(page_values):.1f}")
print()

# 3. Page distribution
print("3. PAGE DISTRIBUTION (by range)")
print("-" * 80)

page_ranges = Counter()
for page in page_values:
    range_key = f"{(page//100)*100:>3d}-{(page//100)*100+99:>3d}"
    page_ranges[range_key] += 1

for range_key in sorted(page_ranges.keys()):
    count = page_ranges[range_key]
    bar = "█" * int(count / max(page_ranges.values()) * 40)
    print(f"Pages {range_key}: {count:>5} {bar}")
print()

# 4. Sample random objects with different page ranges
print("4. RANDOM SAMPLE (different page ranges)")
print("-" * 80)

# Get samples from different page ranges
import random

samples_per_range = {
    "low (1-100)": [
        obj for obj in all_objects if 1 <= obj.properties.get("page", 0) <= 100
    ],
    "mid (100-500)": [
        obj for obj in all_objects if 100 < obj.properties.get("page", 0) <= 500
    ],
    "high (>500)": [obj for obj in all_objects if obj.properties.get("page", 0) > 500],
}

for range_name, objects in samples_per_range.items():
    if objects:
        sample = random.choice(objects)
        page = sample.properties.get("page")
        text = sample.properties.get("text", "")

        # Check if page marker exists in text
        has_marker = f"<!-- Page {page} -->" in text
        marker_status = "✅ HAS MARKER" if has_marker else "⚠️  NO MARKER"

        print(f"{range_name}: Page {page:>4} {marker_status}")
        print(f"  UUID: {str(sample.uuid)[:16]}...")
        print(f"  Text: {text[:80]}...")
        print()

# 5. Check for suspicious patterns
print("5. SUSPICIOUS PATTERNS CHECK")
print("-" * 80)

# Check fallback pages (page=1 might be fallback)
page_one_count = sum(1 for obj in all_objects if obj.properties.get("page") == 1)
print(f"Objects with page=1: {page_one_count} ({page_one_count/total_count*100:.1f}%)")

# Sample page=1 objects to see if they're real or fallback
page_one_objects = [obj for obj in all_objects if obj.properties.get("page") == 1]
if page_one_objects:
    sample = random.choice(page_one_objects)
    text = sample.properties.get("text", "")
    has_marker = "<!-- Page 1 -->" in text
    print(
        f"  Sample page=1 object has marker: {'YES ✅' if has_marker else 'NO (likely fallback) ⚠️'}"
    )
    print(f"  Text preview: {text[:100]}...")
print()

# 6. Verify page markers match stored page
print("6. PAGE MARKER CONSISTENCY CHECK")
print("-" * 80)

mismatch_count = 0
sample_size = min(100, total_count)
samples = random.sample(all_objects, sample_size)

for obj in samples:
    stored_page = obj.properties.get("page")
    text = obj.properties.get("text", "")

    # Try to extract page from marker
    import re

    markers = re.findall(r"<!-- Page (\d+) -->", text)
    if markers:
        marker_page = int(markers[0])
        if marker_page != stored_page:
            mismatch_count += 1
            if mismatch_count <= 3:  # Show first 3 mismatches
                print(f"⚠️  MISMATCH: UUID {str(obj.uuid)[:16]}...")
                print(f"   Stored: {stored_page}, Marker: {marker_page}")
                print(f"   Text: {text[:80]}...")
                print()

if mismatch_count == 0:
    print(f"✅ All {sample_size} sampled objects have consistent page numbers!")
else:
    print(f"⚠️  Found {mismatch_count}/{sample_size} mismatches")
print()

# 7. Final verdict
print("=" * 80)
print("FINAL VERDICT")
print("=" * 80)

issues = []
if page_none > 0:
    issues.append(f"❌ {page_none} objects with page=None")
if page_zero > 0:
    issues.append(f"❌ {page_zero} objects with page=0")
if mismatch_count > 0:
    issues.append(f"⚠️  {mismatch_count}/{sample_size} marker mismatches")

if not issues:
    print("✅ ALL CHECKS PASSED!")
    print(f"   - {total_count} objects total")
    print(f"   - {page_valid} objects with valid pages (100%)")
    print(f"   - Page range: {min(page_values)} to {max(page_values)}")
    print(f"   - No mismatches detected")
else:
    print("⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"   {issue}")

print("=" * 80 + "\n")

client.close()
