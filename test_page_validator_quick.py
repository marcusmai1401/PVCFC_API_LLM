"""Quick test for page number validator"""
import sys

sys.path.insert(0, ".")


# Mock logger
class FakeLogger:
    @staticmethod
    def warning(msg):
        print(f"⚠️  {msg}")

    @staticmethod
    def error(msg):
        print(f"❌ {msg}")

    @staticmethod
    def debug(msg):
        pass


# Replace logger in module
import app.utils.page_number_validator as pnv

pnv.logger = FakeLogger()

from app.utils.page_number_validator import validate_and_normalize_page

# Run tests
print("=" * 60)
print("Page Number Validator Tests")
print("=" * 60)

test1 = validate_and_normalize_page(0, "opensearch")
assert test1 == 1, f"Test 1 failed: expected 1, got {test1}"
print(f"✅ Test 1 PASS: 0-indexed → {test1}")

test2 = validate_and_normalize_page(5, "citation")
assert test2 == 5, f"Test 2 failed: expected 5, got {test2}"
print(f"✅ Test 2 PASS: 1-indexed unchanged → {test2}")

test3 = validate_and_normalize_page(None, "fallback")
assert test3 == 1, f"Test 3 failed: expected 1, got {test3}"
print(f"✅ Test 3 PASS: None → {test3}")

test4 = validate_and_normalize_page(-5, "invalid")
assert test4 == 1, f"Test 4 failed: expected 1, got {test4}"
print(f"✅ Test 4 PASS: Negative → {test4}")

print("=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
