#!/usr/bin/env python
"""
Pre-Flight Indexing Check: Service Readiness Validation
========================================================

Purpose: Verify all services and data are ready before running indexing pipeline
Checks:
1. Infrastructure heartbeat (OpenSearch + Weaviate)
2. Embedding API validity (Gemini)
3. Schema & index status
4. Data compatibility dry run

Author: Auto-generated diagnostic script
Date: 2025-11-27
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv

env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from {env_path}\n")

# Configuration
CHUNKS_FILE = Path(r"D:\PVCFC_Artifacts\ingestion_production\chunks\chunks.jsonl")

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")


def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")


def print_separator(char="=", width=80):
    print(char * width)


def check_infrastructure() -> bool:
    """Check 1: Infrastructure Heartbeat"""
    print_separator()
    print("CHECK 1: INFRASTRUCTURE HEARTBEAT")
    print_separator()

    all_ok = True

    # Check OpenSearch
    print("\n🔍 Checking OpenSearch...")
    try:
        from opensearchpy import OpenSearch

        host = os.getenv("OPENSEARCH_HOST", "localhost")
        port = int(os.getenv("OPENSEARCH_PORT", "9200"))

        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            timeout=10,
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )

        # Ping server
        info = client.info()
        print_success(f"OpenSearch connected: {info['version']['number']}")
        print(f"   Cluster: {info['cluster_name']}")

    except Exception as e:
        print_error(f"OpenSearch connection failed: {e}")
        all_ok = False

    # Check Weaviate
    print("\n🔍 Checking Weaviate...")
    try:
        import weaviate

        host = os.getenv("WEAVIATE_HOST", "localhost")
        port = int(os.getenv("WEAVIATE_PORT", "8080"))
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

        client = weaviate.connect_to_local(host=host, port=port, grpc_port=grpc_port)

        if client.is_ready():
            meta = client.get_meta()
            print_success(f"Weaviate ready: {meta.get('version', 'unknown')}")
        else:
            print_error("Weaviate not ready")
            all_ok = False

        client.close()

    except Exception as e:
        print_error(f"Weaviate connection failed: {e}")
        all_ok = False

    return all_ok


def check_embedding_api() -> bool:
    """Check 2: Embedding API Validity"""
    print("\n")
    print_separator()
    print("CHECK 2: EMBEDDING API VALIDITY")
    print_separator()

    print("\n🔍 Testing Gemini Embedding API...")

    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print_error("GEMINI_API_KEY not found in environment")
            return False

        genai.configure(api_key=api_key)

        # Test embedding
        test_text = "test pre-flight connectivity"
        result = genai.embed_content(
            model="models/embedding-001",
            content=test_text,
            task_type="retrieval_document",
        )

        embedding = result["embedding"]
        dimension = len(embedding)

        print_success(f"Embedding API working (Dimension: {dimension})")
        print(f"   Model: embedding-001")
        print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")

        return True

    except Exception as e:
        print_error(f"Embedding API failed: {e}")
        return False


def check_schemas() -> bool:
    """Check 3: Schema & Index Status"""
    print("\n")
    print_separator()
    print("CHECK 3: SCHEMA & INDEX STATUS")
    print_separator()

    all_ok = True

    # Check OpenSearch Index
    print("\n🔍 Checking OpenSearch index...")
    try:
        from opensearchpy import OpenSearch

        host = os.getenv("OPENSEARCH_HOST", "localhost")
        port = int(os.getenv("OPENSEARCH_PORT", "9200"))
        index_name = os.getenv("OPENSEARCH_INDEX", "rag_chunks")

        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            timeout=10,
            use_ssl=False,
        )

        if client.indices.exists(index=index_name):
            count_response = client.count(index=index_name)
            doc_count = count_response["count"]

            if doc_count == 0:
                print_success(f"Index '{index_name}' exists and is empty (ready)")
            else:
                print_warning(
                    f"Index '{index_name}' exists with {doc_count:,} documents"
                )
                print(f"   Consider cleaning before indexing or proceed to append")
        else:
            print_info(f"Index '{index_name}' does not exist (will be created)")

    except Exception as e:
        print_warning(f"Could not check OpenSearch index: {e}")

    # Check Weaviate Collection
    print("\n🔍 Checking Weaviate collection...")
    try:
        import weaviate

        host = os.getenv("WEAVIATE_HOST", "localhost")
        port = int(os.getenv("WEAVIATE_PORT", "8080"))
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        collection_name = os.getenv("WEAVIATE_COLLECTION", "Chunk")

        client = weaviate.connect_to_local(host=host, port=port, grpc_port=grpc_port)

        if client.collections.exists(collection_name):
            collection = client.collections.get(collection_name)

            # Get count via aggregate
            agg = collection.aggregate.over_all(total_count=True)
            count = agg.total_count

            if count == 0:
                print_success(
                    f"Collection '{collection_name}' exists and is empty (ready)"
                )
            else:
                print_warning(
                    f"Collection '{collection_name}' exists with {count:,} objects"
                )
                print(f"   Consider wiping before full indexing run")
        else:
            print_info(
                f"Collection '{collection_name}' does not exist (will be created)"
            )

        client.close()

    except Exception as e:
        print_warning(f"Could not check Weaviate collection: {e}")

    return all_ok


def check_data_compatibility() -> bool:
    """Check 4: Data Compatibility Dry Run"""
    print("\n")
    print_separator()
    print("CHECK 4: DATA COMPATIBILITY DRY RUN")
    print_separator()

    print(f"\n🔍 Loading sample chunk from: {CHUNKS_FILE}")

    if not CHUNKS_FILE.exists():
        print_error(f"Chunks file not found: {CHUNKS_FILE}")
        return False

    try:
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()

            if not first_line:
                print_error("Chunks file is empty")
                return False

            chunk = json.loads(first_line)

            # Validate required fields
            required_fields = ["text", "doc_id", "metadata"]
            missing_fields = [f for f in required_fields if f not in chunk]

            if missing_fields:
                print_error(f"Sample chunk missing fields: {missing_fields}")
                return False

            print_success("Sample chunk validation passed")
            print(f"   Chunk ID: {chunk.get('chunk_id', 'N/A')}")
            print(f"   Doc ID: {chunk.get('doc_id', 'N/A')}")
            print(f"   Text length: {len(chunk['text'])} chars")
            print(f"   Metadata keys: {list(chunk['metadata'].keys())}")

            print_info("Chunk format compatible with indexing pipeline")

            return True

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in chunks file: {e}")
        return False
    except Exception as e:
        print_error(f"Error reading chunks file: {e}")
        return False


def main():
    """Main pre-flight check execution"""
    print_separator()
    print("PRE-FLIGHT INDEXING CHECK")
    print_separator()
    print("Verifying all services and data are ready for indexing\n")

    # Run all checks
    results = {
        "infrastructure": False,
        "embedding": False,
        "schemas": False,
        "data": False,
    }

    try:
        results["infrastructure"] = check_infrastructure()

        if not results["infrastructure"]:
            print_error("\nInfrastructure check failed - cannot proceed")
            raise SystemExit(1)

        results["embedding"] = check_embedding_api()

        if not results["embedding"]:
            print_error("\nEmbedding API check failed - cannot proceed")
            raise SystemExit(1)

        results["schemas"] = check_schemas()
        results["data"] = check_data_compatibility()

        if not results["data"]:
            print_error("\nData compatibility check failed - cannot proceed")
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        print_error(f"Unexpected error during checks: {e}")
        raise SystemExit(1)

    # Final verdict
    print("\n")
    print_separator()
    print("🎯 FINAL VERDICT")
    print_separator()

    all_passed = all(results.values())

    print(f"\n📊 Check Results:")
    for check_name, passed in results.items():
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        print(f"   {check_name.capitalize():<15} {status}")

    if all_passed:
        print(f"\n{GREEN}{'=' * 80}{RESET}")
        print(f"{GREEN}🚀 GO FOR INDEXING{RESET}")
        print(f"{GREEN}{'=' * 80}{RESET}")
        print(f"\nAll systems ready. You can now run:")
        print(f"  python scripts/utilities/index_production_chunks.py")
    else:
        print(f"\n{RED}{'=' * 80}{RESET}")
        print(f"{RED}❌ NO-GO - FIX ISSUES BEFORE INDEXING{RESET}")
        print(f"{RED}{'=' * 80}{RESET}")
        print(f"\nResolve the failed checks above before proceeding")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
