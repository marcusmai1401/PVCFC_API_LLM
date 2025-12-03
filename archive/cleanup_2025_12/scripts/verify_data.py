#!/usr/bin/env python
"""
Verify Weaviate Data
====================

Quick script to verify indexed data in Weaviate.
"""
import weaviate
import weaviate.classes as wvc


def main():
    print("=" * 80)
    print("Weaviate Data Verification")
    print("=" * 80)

    # Connect to Weaviate
    print("\nConnecting to Weaviate...")
    client = weaviate.connect_to_local(host="localhost", port=8080)

    try:
        # Get collection
        collection = client.collections.get("Chunk")

        # Total count
        print("\n1. Total Count:")
        agg = collection.aggregate.over_all(total_count=True)
        print(f"   Total objects: {agg.total_count}")

        # Sample a few objects
        print("\n2. Sample Objects:")
        response = collection.query.fetch_objects(limit=3)

        for i, obj in enumerate(response.objects, 1):
            print(f"\n   Object {i}:")
            print(f"   - doc_id: {obj.properties.get('doc_id')}")
            print(f"   - page: {obj.properties.get('page')}")
            print(f"   - equipment_type: {obj.properties.get('equipment_type')}")
            print(f"   - doc_type: {obj.properties.get('doc_type')}")
            print(f"   - equipment_id: {obj.properties.get('equipment_id')}")
            print(f"   - vendor: {obj.properties.get('vendor')}")
            print(
                f"   - text (first 100 chars): {obj.properties.get('text', '')[:100]}..."
            )

        # Check metadata distribution
        print("\n3. Metadata Distribution:")

        # Equipment types
        print("\n   Equipment Types:")
        for eq_type in ["compressor", "turbine", "pump", "motor", "unknown"]:
            agg_result = collection.aggregate.over_all(
                filters=wvc.query.Filter.by_property("equipment_type").equal(eq_type),
                total_count=True,
            )
            count = agg_result.total_count if agg_result else 0
            print(f"     - {eq_type}: {count}")

        # Doc types
        print("\n   Doc Types:")
        for doc_type in ["datasheet", "manual", "drawing", "pid", "other"]:
            agg_result = collection.aggregate.over_all(
                filters=wvc.query.Filter.by_property("doc_type").equal(doc_type),
                total_count=True,
            )
            count = agg_result.total_count if agg_result else 0
            print(f"     - {doc_type}: {count}")

        # Vendors
        print("\n   Vendors (top 5):")
        for vendor in ["HITACHI", "HTC", "ATLAS", "SIEMENS", "ABB"]:
            agg_result = collection.aggregate.over_all(
                filters=wvc.query.Filter.by_property("vendor").equal(vendor),
                total_count=True,
            )
            count = agg_result.total_count if agg_result else 0
            if count > 0:
                print(f"     - {vendor}: {count}")

        print("\n" + "=" * 80)
        print("Verification Complete!")
        print("=" * 80)

    finally:
        client.close()


if __name__ == "__main__":
    main()
