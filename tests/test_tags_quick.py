from app.rag.normalizers.tag_normalizer import TagNormalizer

t = TagNormalizer()
tests = [
    "E04217",
    "P04201A",
    "K04301",
    "T04201",
    "R04201",
    "F04201",
    "C04302",
    "V04201",
]

print("ALL TAG TYPES TEST:")
print("=" * 50)
for tag in tests:
    result = t.extract_tags(tag)
    if result:
        print(f'  {tag:10} -> OK   ({result[0]["type"]})')
    else:
        print(f"  {tag:10} -> FAIL (not detected)")

print("=" * 50)
print(
    "All tests passed!"
    if all(t.extract_tags(tag) for tag in tests)
    else "Some tests failed"
)
