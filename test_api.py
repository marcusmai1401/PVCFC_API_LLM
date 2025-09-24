#!/usr/bin/env python3
"""
Test API connectivity and endpoints
"""
import subprocess
import sys
import threading
import time

import requests


def start_api_server():
    """Start the API server in a subprocess"""
    print("Starting API server...")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--log-level",
        "info",
    ]

    proc = subprocess.Popen(cmd)
    return proc


def test_api():
    """Test API endpoints"""
    base_url = "http://localhost:8000"

    print("\nWaiting for API to start...")
    max_attempts = 20
    for i in range(max_attempts):
        try:
            resp = requests.get(f"{base_url}/healthz", timeout=1)
            if resp.status_code == 200:
                print("✓ API is running!")
                data = resp.json()
                print(f"  Environment: {data.get('app_env')}")
                print(
                    f"  LLM Provider: {data.get('llm_provider')} (Ready: {data.get('llm_provider_ready')})"
                )
                print(f"  Version: {data.get('version')}")
                return True
        except requests.exceptions.ConnectionError:
            print(f"  Attempt {i+1}/{max_attempts}: API not ready yet...")
            time.sleep(1)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(1)

    print("✗ API failed to start after 20 seconds")
    return False


def test_ask_endpoint():
    """Test the /ask endpoint"""
    base_url = "http://localhost:8000"

    print("\nTesting /ask endpoint...")
    try:
        payload = {
            "query": "What is a test query?",
            "max_context": 5,
            "hyde": False,
            "language": "en",
            "execution_mode": "light_only",
        }

        resp = requests.post(f"{base_url}/ask", json=payload, timeout=30)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✓ Answer received: {len(data.get('answer', ''))} chars")
            print(f"  Citations: {len(data.get('citations', []))}")
            print(f"  Confidence: {data.get('confidence', 0)}")
            return True
        else:
            print(f"  ✗ Error: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"  ✗ Error testing /ask: {e}")
        return False


def main():
    """Main test function"""
    print("=" * 60)
    print("PVCFC RAG API Test")
    print("=" * 60)

    # Start API in subprocess
    proc = start_api_server()

    try:
        # Wait a bit for startup
        time.sleep(3)

        # Test health endpoint
        if test_api():
            # Test ask endpoint
            test_ask_endpoint()

        print("\n" + "=" * 60)
        print("Test complete. Press Ctrl+C to stop the server.")
        print("=" * 60)

        # Keep running
        proc.wait()

    except KeyboardInterrupt:
        print("\nStopping server...")
        proc.terminate()
        proc.wait(timeout=5)
        print("Server stopped.")
    except Exception as e:
        print(f"Error: {e}")
        proc.terminate()


if __name__ == "__main__":
    main()
