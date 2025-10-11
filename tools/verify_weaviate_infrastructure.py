#!/usr/bin/env python
"""
Weaviate Infrastructure Verification Script
============================================

Kiểm tra hạ tầng Weaviate đã sẵn sàng cho migration FAISS → Weaviate.

Requirements:
- Weaviate running at http://localhost:8080
- Python client v4 (weaviate-client>=4.0.0)

Output:
- JSON report với đầy đủ health checks và smoke tests
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import weaviate
    from weaviate.classes.config import Configure, DataType, Property, VectorDistances
    from weaviate.classes.query import Filter
except ImportError:
    print("ERROR: weaviate-client not installed or wrong version!")
    print("Run: pip install 'weaviate-client>=4.0.0'")
    sys.exit(1)


class WeaviateInfraVerifier:
    """Verifier for Weaviate infrastructure readiness."""

    def __init__(self, url: str = "http://localhost:8080"):
        self.url = url
        self.client = None
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "weaviate_url": url,
            "weaviate_version": None,
            "ready": False,
            "live": False,
            "schema_ok": False,
            "chunk_collection_exists": False,
            "properties_ok": False,
            "vectorizer": None,
            "distance": None,
            "grpc_port_ok": False,
            "smoke_insert_ok": False,
            "total_objects_after_insert": 0,
            "test_search_ok": False,
            "latency_ms": {"meta": None, "ready": None, "live": None},
            "notes": [],
        }
        self.logs = []

    def log(self, message: str):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] {message}"
        self.logs.append(log_line)
        print(log_line)

    def add_note(self, note: str):
        """Add note to report."""
        self.report["notes"].append(note)

    def step_1_health_checks(self):
        """Step 1: Health checks (meta, ready, live)."""
        self.log("=" * 80)
        self.log("STEP 1: HEALTH CHECKS")
        self.log("=" * 80)

        try:
            # Connect to Weaviate with gRPC
            self.log(f"Connecting to Weaviate at {self.url}...")
            self.log("Using gRPC port 50051 for high-performance queries")

            from weaviate.classes.init import AdditionalConfig, Timeout

            self.client = weaviate.connect_to_local(
                host="localhost",
                port=8080,
                grpc_port=50051,
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=5, query=30, insert=30)
                ),
            )

            # Check if ready
            start = time.time()
            is_ready = self.client.is_ready()
            ready_latency = (time.time() - start) * 1000

            self.report["ready"] = is_ready
            self.report["latency_ms"]["ready"] = round(ready_latency, 2)

            if is_ready:
                self.log(f"✅ Weaviate is READY (latency: {ready_latency:.2f}ms)")
            else:
                self.log("❌ Weaviate is NOT READY")
                self.add_note("Weaviate not ready - check if container is running")
                return False

            # Check if live
            start = time.time()
            is_live = self.client.is_live()
            live_latency = (time.time() - start) * 1000

            self.report["live"] = is_live
            self.report["latency_ms"]["live"] = round(live_latency, 2)

            if is_live:
                self.log(f"✅ Weaviate is LIVE (latency: {live_latency:.2f}ms)")
            else:
                self.log("❌ Weaviate is NOT LIVE")
                self.add_note("Weaviate not live - check container health")
                return False

            # Get meta (version info)
            try:
                start = time.time()
                meta = self.client.get_meta()
                meta_latency = (time.time() - start) * 1000

                self.report["latency_ms"]["meta"] = round(meta_latency, 2)
                self.report["weaviate_version"] = meta.get("version", "unknown")

                self.log(
                    f"✅ Weaviate version: {self.report['weaviate_version']} (latency: {meta_latency:.2f}ms)"
                )
            except Exception as e:
                self.log(f"⚠️  Could not fetch meta: {e}")
                self.report["weaviate_version"] = "unknown"

            return True

        except Exception as e:
            self.log(f"❌ Health check failed: {e}")
            self.add_note(
                f"Connection failed: {str(e)}. Check if Weaviate container is running on port 8080"
            )
            return False

    def step_2_schema_verification(self):
        """Step 2: Schema verification and creation if needed."""
        self.log("")
        self.log("=" * 80)
        self.log("STEP 2: SCHEMA VERIFICATION")
        self.log("=" * 80)

        try:
            # Check if Chunk collection exists
            collection_exists = self.client.collections.exists("Chunk")
            self.report["chunk_collection_exists"] = collection_exists

            if collection_exists:
                self.log("✅ Collection 'Chunk' exists")

                # Verify schema
                collection = self.client.collections.get("Chunk")
                config = collection.config.get()

                # Check vectorizer
                vectorizer = (
                    config.vectorizer_config.vectorizer.value
                    if config.vectorizer_config
                    else "none"
                )
                self.report["vectorizer"] = vectorizer

                if vectorizer == "none":
                    self.log("✅ Vectorizer: none (manual vectors)")
                else:
                    self.log(f"⚠️  Vectorizer: {vectorizer} (expected: none)")
                    self.add_note(
                        f"Vectorizer is '{vectorizer}', expected 'none' for manual Gemini embeddings"
                    )

                # Check distance metric
                distance = (
                    config.vector_index_config.distance_metric.value
                    if config.vector_index_config
                    else "unknown"
                )
                self.report["distance"] = distance

                if distance.lower() == "cosine":
                    self.log("✅ Distance metric: cosine")
                else:
                    self.log(f"⚠️  Distance metric: {distance} (expected: cosine)")
                    self.add_note(f"Distance metric is '{distance}', expected 'cosine'")

                # Check properties
                expected_props = {
                    "text",
                    "doc_id",
                    "page",
                    "equipment_type",
                    "doc_type",
                    "equipment_id",
                    "vendor",
                    "source_path",
                    "lang",
                }

                # config.properties is a list of Property objects, not dict
                if isinstance(config.properties, list):
                    actual_props = {prop.name for prop in config.properties}
                else:
                    actual_props = set(config.properties.keys())

                missing_props = expected_props - actual_props
                extra_props = actual_props - expected_props

                if not missing_props:
                    self.log(
                        f"✅ All required properties present ({len(actual_props)} total)"
                    )
                    self.report["properties_ok"] = True
                else:
                    self.log(f"⚠️  Missing properties: {missing_props}")
                    self.add_note(f"Missing properties: {missing_props}")
                    self.report["properties_ok"] = False

                if extra_props:
                    self.log(f"ℹ️  Extra properties: {extra_props}")

                self.report["schema_ok"] = (
                    self.report["properties_ok"]
                    and (vectorizer == "none")
                    and (distance.lower() == "cosine")
                )

            else:
                self.log("⚠️  Collection 'Chunk' does not exist - creating...")
                self._create_chunk_collection()

            return self.report["chunk_collection_exists"]

        except Exception as e:
            self.log(f"❌ Schema verification failed: {e}")
            self.add_note(f"Schema verification error: {str(e)}")
            return False

    def _create_chunk_collection(self):
        """Create Chunk collection with proper schema."""
        try:
            self.client.collections.create(
                name="Chunk",
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE,
                    ef_construction=128,
                    ef=64,
                    max_connections=64,
                ),
                properties=[
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="doc_id", data_type=DataType.TEXT),
                    Property(name="page", data_type=DataType.INT),
                    Property(name="equipment_type", data_type=DataType.TEXT),
                    Property(name="doc_type", data_type=DataType.TEXT),
                    Property(name="equipment_id", data_type=DataType.TEXT),
                    Property(name="vendor", data_type=DataType.TEXT),
                    Property(name="source_path", data_type=DataType.TEXT),
                    Property(name="lang", data_type=DataType.TEXT),
                ],
            )

            self.log("✅ Collection 'Chunk' created successfully")
            self.report["chunk_collection_exists"] = True
            self.report["schema_ok"] = True
            self.report["properties_ok"] = True
            self.report["vectorizer"] = "none"
            self.report["distance"] = "cosine"

        except Exception as e:
            self.log(f"❌ Failed to create collection: {e}")
            self.add_note(f"Collection creation failed: {str(e)}")
            raise

    def step_3_smoke_test(self):
        """Step 3: Smoke test - insert and query."""
        self.log("")
        self.log("=" * 80)
        self.log("STEP 3: SMOKE TEST")
        self.log("=" * 80)

        try:
            collection = self.client.collections.get("Chunk")

            # Insert test object
            self.log("Inserting test object...")

            # Create dummy 768-dimensional vector (small random values)
            np.random.seed(42)
            test_vector = np.random.randn(768).astype(np.float32) * 0.01

            test_properties = {
                "text": "CO2 compressor 4th stage discharge pressure example line",
                "doc_id": "DOC_demo_0001",
                "page": 3,
                "equipment_type": "compressor",
                "doc_type": "datasheet",
                "equipment_id": "K-06101",
                "vendor": "atlas copco",
                "source_path": "C:/docs/CO2_COMPRESSOR/demo.pdf",
                "lang": "en",
            }

            uuid = collection.data.insert(
                properties=test_properties, vector=test_vector.tolist()
            )

            self.log(f"✅ Test object inserted (UUID: {uuid})")
            self.report["smoke_insert_ok"] = True

            # Wait a bit for indexing
            time.sleep(0.5)

            # Count objects (this uses gRPC)
            self.log("Counting objects in collection (via gRPC)...")
            try:
                result = collection.aggregate.over_all(total_count=True)
                total = result.total_count

                self.report["total_objects_after_insert"] = total
                self.report["grpc_port_ok"] = True  # Aggregation worked = gRPC OK
                self.log(f"✅ Total objects in Chunk: {total}")
                self.log("✅ gRPC port 50051 working correctly")

                if total < 1:
                    self.add_note(
                        "No objects found after insert - potential indexing issue"
                    )
            except Exception as e:
                self.log(f"❌ Aggregation failed (gRPC issue): {e}")
                self.add_note(
                    f"gRPC aggregation failed: {str(e)}. Check if port 50051 is exposed."
                )
                self.report["grpc_port_ok"] = False
                return False

            # Test search with filter
            self.log("Testing filtered search...")

            search_results = collection.query.near_vector(
                near_vector=test_vector.tolist(),
                limit=1,
                filters=Filter.by_property("equipment_type").equal("compressor"),
            )

            if search_results.objects:
                self.log(
                    f"✅ Search successful - found {len(search_results.objects)} result(s)"
                )

                # Verify returned object
                obj = search_results.objects[0]
                if obj.properties.get("doc_id") == "DOC_demo_0001":
                    self.log("✅ Returned object matches inserted test data")
                    self.report["test_search_ok"] = True
                else:
                    self.log(
                        f"⚠️  Returned unexpected object: {obj.properties.get('doc_id')}"
                    )
                    self.add_note("Search returned unexpected object")
            else:
                self.log("⚠️  Search returned no results")
                self.add_note(
                    "Vector search with filter returned no results - potential issue with HNSW index"
                )

            return self.report["test_search_ok"]

        except Exception as e:
            self.log(f"❌ Smoke test failed: {e}")
            self.add_note(f"Smoke test error: {str(e)}")
            import traceback

            self.log(traceback.format_exc())
            return False

    def generate_report(self):
        """Generate final report."""
        self.log("")
        self.log("=" * 80)
        self.log("VERIFICATION REPORT")
        self.log("=" * 80)

        # Summary
        all_ok = (
            self.report["ready"]
            and self.report["live"]
            and self.report["schema_ok"]
            and self.report["smoke_insert_ok"]
            and self.report["test_search_ok"]
        )

        if all_ok:
            self.log("✅ ALL CHECKS PASSED - Weaviate is ready for migration!")
            self.report["notes"].append(
                "Infrastructure ready for FAISS → Weaviate migration"
            )
        else:
            self.log("⚠️  SOME CHECKS FAILED - Review notes for issues")

        self.log("")
        self.log("Report JSON:")
        report_json = json.dumps(self.report, indent=2)
        print(report_json)

        # Save to file
        report_file = (
            PROJECT_ROOT / "reports" / "weaviate_infrastructure_verification.json"
        )
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_json)

        self.log("")
        self.log(f"Report saved to: {report_file}")

        return all_ok

    def run(self):
        """Run full verification."""
        self.log("Starting Weaviate infrastructure verification...")
        self.log(f"Target: {self.url}")
        self.log("")

        try:
            # Step 1: Health checks
            if not self.step_1_health_checks():
                self.log("")
                self.log("❌ Health checks failed - stopping verification")
                return False

            # Step 2: Schema verification
            if not self.step_2_schema_verification():
                self.log("")
                self.log("❌ Schema verification failed - stopping verification")
                return False

            # Step 3: Smoke test
            self.step_3_smoke_test()

            # Generate report
            return self.generate_report()

        except Exception as e:
            self.log(f"❌ Verification failed with exception: {e}")
            import traceback

            self.log(traceback.format_exc())
            self.add_note(f"Fatal error: {str(e)}")
            return False

        finally:
            if self.client:
                try:
                    self.client.close()
                    self.log("Connection closed.")
                except:
                    pass


def main():
    """Main entry point."""
    verifier = WeaviateInfraVerifier()
    success = verifier.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
