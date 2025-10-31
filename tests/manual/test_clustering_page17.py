"""
Test: Spatial clustering on page 17
Verify that 04 TXI 2077 cluster is found
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.rag.spatial import SpatialComponentExtractor
from app.rag.spatial.component_clusterer import ComponentClusterer

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
doc_id = "Ammonia"
page_num = 17

print("=" * 80)
print(f"TEST: Spatial Clustering - Page {page_num}")
print("=" * 80)

# Step 1: Extract components
print("\n[1] Extracting components...")
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, page_num, doc_id)

extractor = SpatialComponentExtractor()
components = extractor.extract_components(layout)

units = [c for c in components if c.component_type == "unit"]
prefixes = [c for c in components if c.component_type == "prefix"]
suffixes = [c for c in components if c.component_type == "suffix"]

print(
    f"✓ Components: {len(units)} units, {len(prefixes)} prefixes, {len(suffixes)} suffixes"
)

# Step 2: Find target components
print("\n[2] Finding target components...")
target_units = [c for c in units if c.text == "04"]
target_prefixes = [c for c in prefixes if c.text == "TXI"]
target_suffixes = [c for c in suffixes if c.text == "2077"]

print(f"  '04' units: {len(target_units)}")
print(f"  'TXI' prefixes: {len(target_prefixes)}")
print(f"  '2077' suffixes: {len(target_suffixes)}")

if not (target_units and target_prefixes and target_suffixes):
    print("✗ ERROR: Missing target components!")
    sys.exit(1)

# Step 3: Run clusterer on target components only
print("\n[3] Testing clustering on target components...")
clusterer = ComponentClusterer(
    max_distance_mm=25.0, alignment_tolerance_mm=5.0, min_cluster_score=0.6
)

target_clusters = clusterer.find_tag_clusters(
    units=target_units, prefixes=target_prefixes, suffixes=target_suffixes
)

print(f"✓ Found {len(target_clusters)} clusters from target components")

if target_clusters:
    for i, cluster in enumerate(target_clusters, 1):
        print(f"\n  Cluster {i}: {cluster.tag_text}")
        print(f"    Score: {cluster.score:.3f}")
        print(f"    BBox: {cluster.bbox}")
        print(f"    Unit: {cluster.unit.text} at {cluster.unit.center}")
        print(f"    Prefix: {cluster.prefix.text} at {cluster.prefix.center}")
        print(f"    Suffix: {cluster.suffix.text} at {cluster.suffix.center}")

# Step 4: Run clusterer on ALL components
print("\n[4] Testing clustering on ALL components...")
all_clusters = clusterer.find_tag_clusters(
    units=units, prefixes=prefixes, suffixes=suffixes
)

print(f"✓ Found {len(all_clusters)} total clusters on page")

# Find 04 TXI 2077 cluster
txi_2077_cluster = None
for cluster in all_clusters:
    if (
        cluster.unit.text == "04"
        and cluster.prefix.text == "TXI"
        and cluster.suffix.text == "2077"
    ):
        txi_2077_cluster = cluster
        break

print("\n" + "=" * 80)
print("RESULTS:")
print("=" * 80)

if txi_2077_cluster:
    print(f"✓ SUCCESS: Found '04 TXI 2077' cluster!")
    print(f"  Score: {txi_2077_cluster.score:.3f}")
    print(f"  BBox: {txi_2077_cluster.bbox}")
    print(f"  Page: {txi_2077_cluster.page}")
else:
    print("✗ FAILED: '04 TXI 2077' cluster not found")
    print(f"  Total clusters found: {len(all_clusters)}")
    if all_clusters:
        print("\n  Top 5 clusters found:")
        for i, c in enumerate(all_clusters[:5], 1):
            print(f"    {i}. {c.tag_text} (score: {c.score:.3f})")
    sys.exit(1)

print("\n✓ TEST PASSED!")
