#!/usr/bin/env python
"""
Phase 1 Smoke Test
==================

Test metadata-filtered search in Weaviate to validate Phase 1 completion.

Tests:
1. Search for compressor-related documents
2. Search for turbine manuals
3. Search with vendor filter (HITACHI)
4. Search with equipment_id filter
5. Verify metadata presence in results
"""
from datetime import datetime

import weaviate
import weaviate.classes as wvc


def test_basic_search(collection):
    """Test 1: Basic search without filters"""
    print("\n1. Basic Search (no filters)")
    print("-" * 60)

    response = collection.query.fetch_objects(limit=3)

    print(f"   Retrieved: {len(response.objects)} objects")
    for i, obj in enumerate(response.objects[:3], 1):
        props = obj.properties
        print(f"\n   Result {i}:")
        print(f"   - doc_id: {props.get('doc_id', 'N/A')}")
        print(f"   - equipment_type: {props.get('equipment_type', 'N/A')}")
        print(f"   - doc_type: {props.get('doc_type', 'N/A')}")
        print(f"   - vendor: {props.get('vendor', 'N/A')}")

    return len(response.objects) > 0


def test_equipment_type_filter(collection):
    """Test 2: Search with equipment_type filter"""
    print("\n2. Equipment Type Filter (compressor)")
    print("-" * 60)

    response = collection.query.fetch_objects(
        filters=wvc.query.Filter.by_property("equipment_type").equal("compressor"),
        limit=3,
    )

    print(f"   Retrieved: {len(response.objects)} objects")
    for i, obj in enumerate(response.objects[:3], 1):
        props = obj.properties
        print(f"\n   Result {i}:")
        print(f"   - doc_id: {props.get('doc_id', 'N/A')}")
        print(f"   - equipment_type: {props.get('equipment_type', 'N/A')}")
        print(f"   - doc_type: {props.get('doc_type', 'N/A')}")
        print(f"   - vendor: {props.get('vendor', 'N/A')}")

        # Verify filter worked
        if props.get("equipment_type") != "compressor":
            print(
                f"   ⚠️  WARNING: Expected compressor, got {props.get('equipment_type')}"
            )
            return False

    return len(response.objects) > 0


def test_doc_type_filter(collection):
    """Test 3: Search with doc_type filter"""
    print("\n3. Doc Type Filter (manual)")
    print("-" * 60)

    response = collection.query.fetch_objects(
        filters=wvc.query.Filter.by_property("doc_type").equal("manual"), limit=3
    )

    print(f"   Retrieved: {len(response.objects)} objects")
    for i, obj in enumerate(response.objects[:3], 1):
        props = obj.properties
        print(f"\n   Result {i}:")
        print(f"   - doc_id: {props.get('doc_id', 'N/A')}")
        print(f"   - equipment_type: {props.get('equipment_type', 'N/A')}")
        print(f"   - doc_type: {props.get('doc_type', 'N/A')}")
        print(f"   - vendor: {props.get('vendor', 'N/A')}")

        # Verify filter worked
        if props.get("doc_type") != "manual":
            print(f"   ⚠️  WARNING: Expected manual, got {props.get('doc_type')}")
            return False

    return len(response.objects) > 0


def test_vendor_filter(collection):
    """Test 4: Search with vendor filter"""
    print("\n4. Vendor Filter (HITACHI)")
    print("-" * 60)

    response = collection.query.fetch_objects(
        filters=wvc.query.Filter.by_property("vendor").equal("HITACHI"), limit=3
    )

    print(f"   Retrieved: {len(response.objects)} objects")
    for i, obj in enumerate(response.objects[:3], 1):
        props = obj.properties
        print(f"\n   Result {i}:")
        print(f"   - doc_id: {props.get('doc_id', 'N/A')}")
        print(f"   - equipment_type: {props.get('equipment_type', 'N/A')}")
        print(f"   - doc_type: {props.get('doc_type', 'N/A')}")
        print(f"   - vendor: {props.get('vendor', 'N/A')}")

        # Verify filter worked
        if props.get("vendor") != "HITACHI":
            print(f"   ⚠️  WARNING: Expected HITACHI, got {props.get('vendor')}")
            return False

    return len(response.objects) > 0


def test_combined_filters(collection):
    """Test 5: Search with combined filters"""
    print("\n5. Combined Filters (compressor + datasheet + HITACHI)")
    print("-" * 60)

    response = collection.query.fetch_objects(
        filters=(
            wvc.query.Filter.by_property("equipment_type").equal("compressor")
            & wvc.query.Filter.by_property("doc_type").equal("datasheet")
            & wvc.query.Filter.by_property("vendor").equal("HITACHI")
        ),
        limit=3,
    )

    print(f"   Retrieved: {len(response.objects)} objects")
    for i, obj in enumerate(response.objects[:3], 1):
        props = obj.properties
        print(f"\n   Result {i}:")
        print(f"   - doc_id: {props.get('doc_id', 'N/A')}")
        print(f"   - equipment_type: {props.get('equipment_type', 'N/A')}")
        print(f"   - doc_type: {props.get('doc_type', 'N/A')}")
        print(f"   - vendor: {props.get('vendor', 'N/A')}")

        # Verify all filters worked
        if props.get("equipment_type") != "compressor":
            print(
                f"   ⚠️  WARNING: Expected compressor, got {props.get('equipment_type')}"
            )
            return False
        if props.get("doc_type") != "datasheet":
            print(f"   ⚠️  WARNING: Expected datasheet, got {props.get('doc_type')}")
            return False
        if props.get("vendor") != "HITACHI":
            print(f"   ⚠️  WARNING: Expected HITACHI, got {props.get('vendor')}")
            return False

    return len(response.objects) > 0


def test_metadata_completeness(collection):
    """Test 6: Verify metadata completeness"""
    print("\n6. Metadata Completeness Check")
    print("-" * 60)

    response = collection.query.fetch_objects(limit=100)

    total = len(response.objects)
    has_equipment_type = sum(
        1 for obj in response.objects if obj.properties.get("equipment_type")
    )
    has_doc_type = sum(1 for obj in response.objects if obj.properties.get("doc_type"))
    has_vendor = sum(1 for obj in response.objects if obj.properties.get("vendor"))
    has_source_path = sum(
        1 for obj in response.objects if obj.properties.get("source_path")
    )

    print(f"\n   Sample size: {total} objects")
    print(
        f"   - equipment_type present: {has_equipment_type}/{total} ({has_equipment_type/total*100:.1f}%)"
    )
    print(
        f"   - doc_type present: {has_doc_type}/{total} ({has_doc_type/total*100:.1f}%)"
    )
    print(f"   - vendor present: {has_vendor}/{total} ({has_vendor/total*100:.1f}%)")
    print(
        f"   - source_path present: {has_source_path}/{total} ({has_source_path/total*100:.1f}%)"
    )

    # At least 70% should have equipment_type
    return (has_equipment_type / total) >= 0.70


def main():
    print("=" * 80)
    print("PHASE 1 SMOKE TEST")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to Weaviate
    print("\nConnecting to Weaviate...")
    client = weaviate.connect_to_local(host="localhost", port=8080)

    test_results = {}

    try:
        collection = client.collections.get("Chunk")

        # Get total count
        agg = collection.aggregate.over_all(total_count=True)
        total_count = agg.total_count
        print(f"Total objects in collection: {total_count}")

        # Run tests
        test_results["basic_search"] = test_basic_search(collection)
        test_results["equipment_type_filter"] = test_equipment_type_filter(collection)
        test_results["doc_type_filter"] = test_doc_type_filter(collection)
        test_results["vendor_filter"] = test_vendor_filter(collection)
        test_results["combined_filters"] = test_combined_filters(collection)
        test_results["metadata_completeness"] = test_metadata_completeness(collection)

        # Print summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        passed = sum(1 for result in test_results.values() if result)
        total = len(test_results)

        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}  {test_name.replace('_', ' ').title()}")

        print("\n" + "-" * 80)
        print(f"Results: {passed}/{total} tests passed")
        print("=" * 80)

        if passed == total:
            print("\n🎉 ALL TESTS PASSED! Phase 1 is complete.")
            print("\nNext steps:")
            print("  - Run with real embeddings (remove --skip-embedding flag)")
            print("  - Test semantic search queries")
            print("  - Integrate with RAG pipeline")
        else:
            print("\n⚠️  Some tests failed. Please review the results above.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
