#!/usr/bin/env python
"""
Phase 2 Semantic Search Smoke Test
==================================

Comprehensive test suite for semantic search with metadata filters.

Tests:
1. Pure semantic search (near_vector)
2. Semantic + equipment_type filter
3. Semantic + doc_type filter
4. Semantic + vendor filter
5. Semantic + combined filters
6. Vector quality checks (non-zero, normalized)
7. Relevance checks (distances are reasonable)
"""
import os
import sys
from datetime import datetime
from typing import Dict, List

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import numpy as np
import weaviate
import weaviate.classes as wvc
from loguru import logger

from app.services.embedding import get_embedding_service


class SemanticSearchTester:
    """Comprehensive semantic search test suite"""

    def __init__(self):
        self.client = None
        self.collection = None
        self.embedding_service = None
        self.test_results = {}

    def setup(self):
        """Initialize connections"""
        logger.info("Initializing embedding service...")
        self.embedding_service = get_embedding_service()

        logger.info("Connecting to Weaviate...")
        self.client = weaviate.connect_to_local(host="localhost", port=8080)
        self.collection = self.client.collections.get("Chunk")

        # Get total count
        agg = self.collection.aggregate.over_all(total_count=True)
        logger.success(f"Connected to Weaviate. Total chunks: {agg.total_count}")

    def teardown(self):
        """Cleanup connections"""
        if self.client:
            self.client.close()

    def test_pure_semantic_search(self) -> bool:
        """Test 1: Pure semantic search without filters"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Pure Semantic Search")
        logger.info("=" * 80)

        query = "CO2 compressor discharge pressure control"
        qvec = self.embedding_service.embed_query(query).tolist()

        res = self.collection.query.near_vector(
            near_vector=qvec,
            limit=10,
            include_vector=True,
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=[
                "doc_id",
                "equipment_type",
                "doc_type",
                "vendor",
                "text",
            ],
        )

        logger.info(f"Query: '{query}'")
        logger.info(f"Results: {len(res.objects)}")

        # Check vector quality
        vector_norms = []
        distances = []

        for i, obj in enumerate(res.objects[:5], 1):
            v = obj.vector
            if isinstance(v, dict):
                first_key = next(iter(v.keys())) if v else None
                v = v.get(first_key) if first_key else None

            vnorm = float(np.linalg.norm(v)) if v is not None else 0.0
            dist = obj.metadata.distance if obj.metadata else None

            vector_norms.append(vnorm)
            distances.append(dist)

            logger.info(
                f"  [{i}] {obj.properties.get('equipment_type'):12s} | "
                f"{obj.properties.get('doc_type'):12s} | "
                f"dist={dist:.4f} | norm={vnorm:.4f}"
            )

        # Validation
        success = True
        if len(res.objects) == 0:
            logger.error("❌ No results returned")
            success = False
        elif all(n > 0.99 and n < 1.01 for n in vector_norms):
            logger.success("✅ All vectors normalized (~1.0)")
        else:
            logger.warning("⚠️  Some vectors not normalized")
            success = False

        if all(d is not None and d < 1.0 for d in distances):
            logger.success("✅ All distances reasonable (< 1.0)")
        else:
            logger.warning("⚠️  Some distances unreasonable")

        self.test_results["pure_semantic"] = success
        return success

    def test_semantic_with_equipment_filter(self) -> bool:
        """Test 2: Semantic search + equipment_type filter"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Semantic + Equipment Type Filter")
        logger.info("=" * 80)

        query = "turbine vibration analysis"
        qvec = self.embedding_service.embed_query(query).tolist()

        res = self.collection.query.near_vector(
            near_vector=qvec,
            limit=5,
            filters=wvc.query.Filter.by_property("equipment_type").equal("turbine"),
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["doc_id", "equipment_type", "doc_type", "vendor"],
        )

        logger.info(f"Query: '{query}' + equipment_type='turbine'")
        logger.info(f"Results: {len(res.objects)}")

        success = True
        for i, obj in enumerate(res.objects, 1):
            eq_type = obj.properties.get("equipment_type")
            dist = obj.metadata.distance if obj.metadata else None

            logger.info(
                f"  [{i}] {eq_type:12s} | {obj.properties.get('doc_type'):12s} | "
                f"{obj.properties.get('vendor'):10s} | dist={dist:.4f}"
            )

            if eq_type != "turbine":
                logger.error(f"❌ Filter failed: expected 'turbine', got '{eq_type}'")
                success = False

        if success and len(res.objects) > 0:
            logger.success("✅ All results match equipment_type filter")

        self.test_results["semantic_equipment_filter"] = success
        return success

    def test_semantic_with_doc_type_filter(self) -> bool:
        """Test 3: Semantic search + doc_type filter"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: Semantic + Doc Type Filter")
        logger.info("=" * 80)

        query = "operational manual procedures"
        qvec = self.embedding_service.embed_query(query).tolist()

        res = self.collection.query.near_vector(
            near_vector=qvec,
            limit=5,
            filters=wvc.query.Filter.by_property("doc_type").equal("manual"),
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["doc_id", "equipment_type", "doc_type"],
        )

        logger.info(f"Query: '{query}' + doc_type='manual'")
        logger.info(f"Results: {len(res.objects)}")

        success = True
        for i, obj in enumerate(res.objects, 1):
            doc_type = obj.properties.get("doc_type")
            dist = obj.metadata.distance if obj.metadata else None

            logger.info(
                f"  [{i}] {doc_type:12s} | {obj.properties.get('equipment_type'):12s} | "
                f"dist={dist:.4f}"
            )

            if doc_type != "manual":
                logger.error(f"❌ Filter failed: expected 'manual', got '{doc_type}'")
                success = False

        if success and len(res.objects) > 0:
            logger.success("✅ All results match doc_type filter")

        self.test_results["semantic_doc_filter"] = success
        return success

    def test_semantic_with_vendor_filter(self) -> bool:
        """Test 4: Semantic search + vendor filter"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: Semantic + Vendor Filter")
        logger.info("=" * 80)

        query = "compressor specifications"
        qvec = self.embedding_service.embed_query(query).tolist()

        res = self.collection.query.near_vector(
            near_vector=qvec,
            limit=5,
            filters=wvc.query.Filter.by_property("vendor").equal("HITACHI"),
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["doc_id", "equipment_type", "vendor"],
        )

        logger.info(f"Query: '{query}' + vendor='HITACHI'")
        logger.info(f"Results: {len(res.objects)}")

        success = True
        for i, obj in enumerate(res.objects, 1):
            vendor = obj.properties.get("vendor")
            dist = obj.metadata.distance if obj.metadata else None

            logger.info(
                f"  [{i}] {vendor:10s} | {obj.properties.get('equipment_type'):12s} | "
                f"dist={dist:.4f}"
            )

            if vendor != "HITACHI":
                logger.error(f"❌ Filter failed: expected 'HITACHI', got '{vendor}'")
                success = False

        if success and len(res.objects) > 0:
            logger.success("✅ All results match vendor filter")

        self.test_results["semantic_vendor_filter"] = success
        return success

    def test_semantic_with_combined_filters(self) -> bool:
        """Test 5: Semantic search + combined filters"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: Semantic + Combined Filters")
        logger.info("=" * 80)

        query = "compressor datasheet technical specifications"
        qvec = self.embedding_service.embed_query(query).tolist()

        res = self.collection.query.near_vector(
            near_vector=qvec,
            limit=5,
            filters=(
                wvc.query.Filter.by_property("equipment_type").equal("compressor")
                & wvc.query.Filter.by_property("doc_type").equal("datasheet")
                & wvc.query.Filter.by_property("vendor").equal("HITACHI")
            ),
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["doc_id", "equipment_type", "doc_type", "vendor"],
        )

        logger.info(
            f"Query: '{query}' + equipment_type='compressor' AND doc_type='datasheet' AND vendor='HITACHI'"
        )
        logger.info(f"Results: {len(res.objects)}")

        success = True
        for i, obj in enumerate(res.objects, 1):
            eq_type = obj.properties.get("equipment_type")
            doc_type = obj.properties.get("doc_type")
            vendor = obj.properties.get("vendor")
            dist = obj.metadata.distance if obj.metadata else None

            logger.info(
                f"  [{i}] {eq_type:12s} | {doc_type:12s} | {vendor:10s} | dist={dist:.4f}"
            )

            if eq_type != "compressor":
                logger.error(f"❌ equipment_type filter failed: got '{eq_type}'")
                success = False
            if doc_type != "datasheet":
                logger.error(f"❌ doc_type filter failed: got '{doc_type}'")
                success = False
            if vendor != "HITACHI":
                logger.error(f"❌ vendor filter failed: got '{vendor}'")
                success = False

        if success and len(res.objects) > 0:
            logger.success("✅ All results match all combined filters")

        self.test_results["semantic_combined_filters"] = success
        return success

    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2 SEMANTIC SEARCH TEST SUMMARY")
        logger.info("=" * 80)

        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}  {test_name.replace('_', ' ').title()}")

        logger.info("-" * 80)
        logger.info(f"Results: {passed}/{total} tests passed")
        logger.info("=" * 80)

        if passed == total:
            logger.success("\n🎉 ALL SEMANTIC SEARCH TESTS PASSED!")
            logger.info("\nPhase 2 is complete and ready for production:")
            logger.info("  ✓ Real embeddings indexed successfully")
            logger.info("  ✓ Semantic search working correctly")
            logger.info("  ✓ Metadata filters working correctly")
            logger.info("  ✓ Vector quality validated")
            logger.info("\nNext steps:")
            logger.info("  - Integrate with RAG pipeline")
            logger.info("  - Add hybrid search (BM25 + semantic)")
            logger.info("  - Test with production queries")
        else:
            logger.warning("\n⚠️  Some tests failed. Please review results above.")


def main():
    tester = SemanticSearchTester()

    try:
        tester.setup()

        # Run all tests
        tester.test_pure_semantic_search()
        tester.test_semantic_with_equipment_filter()
        tester.test_semantic_with_doc_type_filter()
        tester.test_semantic_with_vendor_filter()
        tester.test_semantic_with_combined_filters()

        # Print summary
        tester.print_summary()

    finally:
        tester.teardown()


if __name__ == "__main__":
    main()
