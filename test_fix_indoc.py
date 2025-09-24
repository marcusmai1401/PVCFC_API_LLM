#!/usr/bin/env python3
"""
Test script to verify the fix for in-document questions
"""
import json
import sys

import requests


def test_in_document_query():
    """Test a query that should be in the documents"""

    api_url = "http://localhost:8000/ask"

    # Test query that should be in documents (adjust based on your actual indexed content)
    test_queries = [
        {
            "query": "What is the operating pressure of KT06101?",
            "language": "en",
            "execution_mode": "production",
            "hyde": False,
            "max_context": 5,
        },
        {
            "query": "Áp suất vận hành của KT06101 là bao nhiêu?",
            "language": "vi",
            "execution_mode": "production",
            "hyde": False,
            "max_context": 5,
        },
    ]

    for test in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing query: {test['query']}")
        print(f"{'='*60}")

        try:
            response = requests.post(api_url, json=test, timeout=30)

            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                citations = data.get("citations", [])
                warnings = data.get("warnings", [])

                print(f"✓ Status: SUCCESS")
                print(f"✓ Answer length: {len(answer)} characters")
                print(f"✓ Citations count: {len(citations)}")

                # Check if answer is not empty
                if answer and len(answer.strip()) > 10:
                    print(f"✅ Answer is valid and not empty")
                    print(f"\nAnswer preview (first 200 chars):")
                    print(f"  {answer[:200]}...")
                else:
                    print(f"❌ PROBLEM: Answer is empty or too short!")
                    print(f"  Answer: '{answer}'")

                if warnings:
                    print(f"\n⚠️ Warnings:")
                    for w in warnings:
                        print(f"  - {w}")

                if citations:
                    print(f"\n📌 Citations:")
                    for i, cit in enumerate(citations[:3], 1):
                        print(
                            f"  {i}. Doc: {cit.get('doc_id', 'Unknown')}, Page: {cit.get('page', 'N/A')}"
                        )

            else:
                print(f"❌ API Error: {response.status_code}")
                print(f"Response: {response.text[:500]}")

        except Exception as e:
            print(f"❌ Test failed: {e}")


def test_out_of_document_query():
    """Test a query that should NOT be in the documents (regression test)"""

    api_url = "http://localhost:8000/ask"

    test_query = {
        "query": "What is the average weight of a corgi dog?",
        "language": "en",
        "execution_mode": "production",
        "hyde": False,
        "max_context": 5,
    }

    print(f"\n{'='*60}")
    print(f"Testing OUT-OF-DOCUMENT query: {test_query['query']}")
    print(f"{'='*60}")

    try:
        response = requests.post(api_url, json=test_query, timeout=30)

        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")
            citations = data.get("citations", [])

            print(f"✓ Status: SUCCESS")
            print(f"✓ Answer length: {len(answer)} characters")
            print(f"✓ Citations count: {len(citations)}")

            if answer and len(answer.strip()) > 10:
                print(f"✅ Answer is valid (general knowledge)")
                print(f"\nAnswer preview:")
                print(f"  {answer[:300]}...")
            else:
                print(f"⚠️ Answer might be empty")

        else:
            print(f"❌ API Error: {response.status_code}")

    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("TESTING FIX FOR IN-DOCUMENT QUESTIONS")
    print("=" * 60)

    # Check if API is running
    try:
        health = requests.get("http://localhost:8000/healthz", timeout=2)
        if health.status_code == 200:
            print("✓ API is running")
        else:
            print("❌ API health check failed")
            sys.exit(1)
    except:
        print("❌ API is not running. Please start it with: .\\start_api.ps1")
        sys.exit(1)

    # Run tests
    test_in_document_query()
    test_out_of_document_query()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
