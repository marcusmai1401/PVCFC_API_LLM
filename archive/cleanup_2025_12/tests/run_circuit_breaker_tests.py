"""
Standalone test runner for circuit breaker tests
Bypasses conftest.py to avoid import errors
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now run pytest programmatically
if __name__ == "__main__":
    import pytest

    # Run tests without loading conftest
    exit_code = pytest.main(
        [
            "tests/test_circuit_breaker.py",
            "-v",
            "--tb=short",
            "--noconftest",
            "--override-ini=python_files=test_circuit_breaker.py",
        ]
    )

    sys.exit(exit_code)
