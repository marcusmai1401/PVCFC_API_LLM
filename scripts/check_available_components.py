"""Check available doc_ids and sample components in spatial index"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()

print("=" * 70)
print("AVAILABLE DOC_IDs IN SPATIAL INDEX")
print("=" * 70)

doc_ids = indexer.get_all_doc_ids()
print(f"\nTotal unique doc_ids: {len(doc_ids)}")
print("\nDoc IDs:")
for doc_id in doc_ids[:10]:
    count = indexer.get_component_count(doc_id=doc_id)
    print(f"  {doc_id}: {count:,} components")

if len(doc_ids) > 10:
    print(f"  ... and {len(doc_ids) - 10} more")

# Check for P&ID documents
print("\n" + "=" * 70)
print("P&ID DOCUMENTS")
print("=" * 70)

pid_docs = [d for d in doc_ids if "P_ID" in d or "PID" in d]
print(f"\nFound {len(pid_docs)} P&ID documents:")
for doc_id in pid_docs:
    count = indexer.get_component_count(doc_id=doc_id)
    print(f"  {doc_id}")
    print(f"    Components: {count:,}")

# Sample components from first P&ID doc
if pid_docs:
    print("\n" + "=" * 70)
    print(f"SAMPLE COMPONENTS FROM: {pid_docs[0]}")
    print("=" * 70)

    # Get sample of each type
    for comp_type in ["unit", "prefix", "suffix"]:
        comps = indexer.search_components(
            doc_id=pid_docs[0], component_type=comp_type, size=10
        )
        print(f"\n{comp_type.upper()} examples:")
        unique_texts = set()
        for comp in comps[:20]:
            unique_texts.add(comp["component"])
        for text in sorted(unique_texts)[:10]:
            print(f"  {text}")
