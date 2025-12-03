#!/usr/bin/env python3
"""
Infrastructure Health Check
Validate OpenSearch, Weaviate, Redis before ingestion
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime

results = {"timestamp": datetime.now().isoformat(), "infrastructure": {}}

print("=" * 80)
print("INFRASTRUCTURE HEALTH CHECK")
print("=" * 80)

# ============================================================================
# OpenSearch
# ============================================================================
print("\n[OPENSEARCH] Health Check")
print("-" * 80)

try:
    from opensearchpy import OpenSearch

    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_compress=True,
        timeout=10,
        use_ssl=False,
        verify_certs=False,
    )

    # Test connection
    info = client.info()
    print(f"[OK] OpenSearch connected: v{info['version']['number']}")

    # Check cluster health
    health = client.cluster.health()
    cluster_status = health["status"]

    print(f"     Cluster status: {cluster_status}")
    print(f"     Nodes: {health['number_of_nodes']}")
    print(f"     Data nodes: {health['number_of_data_nodes']}")

    if cluster_status in ["green", "yellow"]:
        print(f"[OK] Cluster healthy ({cluster_status})")
        results["infrastructure"]["opensearch"] = {
            "status": "healthy",
            "cluster_status": cluster_status,
            "version": info["version"]["number"],
        }
    else:
        print(f"[WARN] Cluster status: {cluster_status}")
        results["infrastructure"]["opensearch"] = {
            "status": "degraded",
            "cluster_status": cluster_status,
        }

    # Check required indices
    required_indices = ["rag_chunks", "pvcfc_pid_tags", "pvcfc_pid_spatial_components"]

    print("\n     Indices:")
    for index_name in required_indices:
        exists = client.indices.exists(index=index_name)
        if exists:
            stats = client.indices.stats(index=index_name)
            doc_count = stats["_all"]["primaries"]["docs"]["count"]
            size_bytes = stats["_all"]["primaries"]["store"]["size_in_bytes"]
            print(
                f"       [OK] {index_name:35s} docs={doc_count:6d}  size={size_bytes/(1024*1024):.1f}MB"
            )
        else:
            print(f"       [WARN] {index_name:35s} DOES NOT EXIST")

    # Check disk space
    try:
        stats_all = client.nodes.stats()
        for node_id, node in stats_all["nodes"].items():
            fs = node.get("fs", {}).get("total", {})
            if fs:
                total_gb = fs.get("total_in_bytes", 0) / (1024**3)
                available_gb = fs.get("available_in_bytes", 0) / (1024**3)
                used_percent = (
                    ((total_gb - available_gb) / total_gb * 100) if total_gb > 0 else 0
                )

                print(
                    f"\n     Disk: {available_gb:.1f}GB / {total_gb:.1f}GB available ({used_percent:.1f}% used)"
                )

                if available_gb > 50:
                    print(f"       [OK] Sufficient disk space")
                elif available_gb > 20:
                    print(f"       [WARN] Low disk space")
                else:
                    print(f"       [FAIL] CRITICAL: Disk space too low!")
    except:
        print("       [SKIP] Disk space check")

except Exception as e:
    print(f"[FAIL] OpenSearch connection failed: {e}")
    results["infrastructure"]["opensearch"] = {"status": "error", "error": str(e)}

# ============================================================================
# Weaviate
# ============================================================================
print("\n[WEAVIATE] Health Check")
print("-" * 80)

try:
    import weaviate
    from weaviate.classes.init import Auth

    client = weaviate.connect_to_local(
        host="localhost",
        port=8080,
        grpc_port=50051,
    )

    print("[OK] Weaviate connected")

    # Check if ready
    if client.is_ready():
        print("[OK] Weaviate is ready")

        # Check collection
        try:
            collection = client.collections.get("Chunk")
            print(f"[OK] Collection 'Chunk' exists")

            # Get collection info
            config = collection.config.get()
            print(
                f"     Vector dimensions: {config.vector_config.get('default').vector_index_config.distance}"
            )

            results["infrastructure"]["weaviate"] = {
                "status": "healthy",
                "collection": "Chunk",
            }
        except Exception as e:
            print(f"[WARN] Collection 'Chunk' issue: {e}")
            results["infrastructure"]["weaviate"] = {"status": "warn", "error": str(e)}
    else:
        print("[WARN] Weaviate not ready")
        results["infrastructure"]["weaviate"] = {"status": "not_ready"}

    client.close()

except Exception as e:
    print(f"[FAIL] Weaviate connection failed: {e}")
    results["infrastructure"]["weaviate"] = {"status": "error", "error": str(e)}

# ============================================================================
# Redis (Optional)
# ============================================================================
print("\n[REDIS] Health Check (Optional)")
print("-" * 80)

try:
    import redis

    r = redis.Redis(
        host="localhost",
        port=6379,
        password="pvcfc_redis_2025_secure",
        db=0,
        socket_connect_timeout=2,
        socket_timeout=2,
    )

    # Test ping
    r.ping()
    print("[OK] Redis connected")

    # Get info
    info = r.info()
    print(f"     Version: {info['redis_version']}")
    print(f"     Used memory: {info['used_memory_human']}")
    print(f"     Connected clients: {info['connected_clients']}")

    results["infrastructure"]["redis"] = {
        "status": "healthy",
        "version": info["redis_version"],
    }

except Exception as e:
    print(f"[SKIP] Redis not available (optional): {e}")
    results["infrastructure"]["redis"] = {"status": "not_available"}

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("INFRASTRUCTURE SUMMARY")
print("=" * 80)

services = results["infrastructure"]
critical_services = ["opensearch", "weaviate"]
all_critical_ok = all(
    services.get(svc, {}).get("status") in ["healthy", "degraded", "warn"]
    for svc in critical_services
)

print(f"OpenSearch: {services.get('opensearch', {}).get('status', 'unknown')}")
print(f"Weaviate:   {services.get('weaviate', {}).get('status', 'unknown')}")
print(f"Redis:      {services.get('redis', {}).get('status', 'unknown')} (optional)")

# Save results
output_file = Path("infrastructure_health.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: {output_file}")

print("\n" + "=" * 80)
if all_critical_ok:
    print("[OK] INFRASTRUCTURE: READY FOR INGESTION")
    print("=" * 80)
    sys.exit(0)
else:
    print("[FAIL] INFRASTRUCTURE: CRITICAL SERVICES DOWN")
    print("=" * 80)
    print("\nPlease start missing services:")
    print("  OpenSearch: docker-compose -f docker-compose-opensearch.yml up -d")
    print("  Weaviate: docker-compose -f docker-compose-weaviate.yml up -d")
    sys.exit(1)
