#!/usr/bin/env python
"""
Debug script to test the /ask API endpoint and identify the exact issue.
"""
import json
import sys

import requests


def test_ask_endpoint():
    """Test the /ask endpoint with various payloads"""
    base_url = "http://localhost:8000"

    print("=" * 60)
    print("Testing PVCFC RAG API /ask endpoint")
    print("=" * 60)

    # Test 1: Check if API is running
    print("\n1. Testing API health...")
    try:
        health_resp = requests.get(f"{base_url}/healthz", timeout=5)
        if health_resp.status_code == 200:
            print(f"✓ API is healthy: {health_resp.json()}")
        else:
            print(f"✗ API health check failed: {health_resp.status_code}")
    except Exception as e:
        print(f"✗ Cannot connect to API: {e}")
        sys.exit(1)

    # Test 2: Simple valid request
    print("\n2. Testing simple valid request...")
    simple_payload = {"query": "What is CO2 compressor?"}

    print(f"Payload: {json.dumps(simple_payload, indent=2)}")

    try:
        response = requests.post(
            f"{base_url}/ask",
            json=simple_payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            print("✓ Request successful!")
            result = response.json()
            print(f"Answer preview: {result.get('answer', '')[:200]}...")
        elif response.status_code == 422:
            print("✗ Validation error (422):")
            print(f"Response: {response.text}")

            # Try to parse validation details
            try:
                error_detail = response.json()
                print("\nValidation details:")
                print(json.dumps(error_detail, indent=2))
            except:
                pass
        else:
            print(f"✗ Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"✗ Request failed: {e}")

    # Test 3: Full request with all optional parameters
    print("\n3. Testing full request with all parameters...")
    full_payload = {
        "query": "Tell me about CO2 compressor specifications",
        "hyde": True,
        "max_context": 8,
        "language": "vi",
        "execution_mode": "production",
    }

    print(f"Payload: {json.dumps(full_payload, indent=2)}")

    try:
        response = requests.post(
            f"{base_url}/ask",
            json=full_payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            print("✓ Full request successful!")
            result = response.json()
            print(f"Answer preview: {result.get('answer', '')[:200]}...")
        elif response.status_code == 422:
            print("✗ Validation error (422):")
            print(f"Response: {response.text}")

            # Try to parse validation details
            try:
                error_detail = response.json()
                print("\nValidation details:")
                if "detail" in error_detail:
                    for error in error_detail["detail"]:
                        print(f"  - Field: {error.get('loc', [])}")
                        print(f"    Error: {error.get('msg', '')}")
                        print(f"    Type: {error.get('type', '')}")
            except:
                pass
        else:
            print(f"✗ Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"✗ Request failed: {e}")

    # Test 4: Empty query (should fail validation)
    print("\n4. Testing empty query (should fail)...")
    empty_payload = {"query": ""}

    print(f"Payload: {json.dumps(empty_payload, indent=2)}")

    try:
        response = requests.post(
            f"{base_url}/ask",
            json=empty_payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        print(f"Status code: {response.status_code}")

        if response.status_code == 422:
            print("✓ Correctly rejected empty query")
            try:
                error_detail = response.json()
                if "detail" in error_detail and error_detail["detail"]:
                    print(
                        f"Validation message: {error_detail['detail'][0].get('msg', '')}"
                    )
            except:
                pass
        else:
            print(f"✗ Unexpected status for empty query: {response.status_code}")

    except Exception as e:
        print(f"✗ Request failed: {e}")

    print("\n" + "=" * 60)
    print("API testing complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_ask_endpoint()
