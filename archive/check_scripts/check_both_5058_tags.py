import requests

# Search for all tags with suffix 5058
response = requests.post(
    "http://localhost:9200/pvcfc_pid_tags/_search",
    json={"query": {"term": {"suffix": "5058"}}, "size": 20},
)

data = response.json()

if "error" in data:
    print(f"Error: {data['error']}")
    exit(1)

hits = data.get("hits", {}).get("hits", [])

print(f"Found {len(hits)} tags with suffix 5058 in index:")
print()

has_tt = False
has_ti = False

for hit in hits:
    src = hit["_source"]
    unit = src.get("unit", "")
    prefix = src.get("prefix", "")
    suffix = src.get("suffix", "")
    variant = src.get("variant", "")
    page = src.get("page", 0)

    tag_str = f"{unit} {prefix} {suffix} {variant}".strip()
    print(f"  Page {page:3d}: {tag_str}")

    if prefix == "TT" and unit == "04":
        has_tt = True
    if prefix == "TI" and unit == "04":
        has_ti = True

print()
print("=" * 60)
print(f"Has 04 TT 5058: {has_tt}")
print(f"Has 04 TI 5058: {has_ti}")
print("=" * 60)

if not has_ti:
    print("\n❌ TARGET TAG '04 TI 5058' MISSING FROM INDEX")
    if has_tt:
        print("   But '04 TT 5058' exists - possible deduplication issue")
    else:
        print("   Neither TT nor TI with suffix 5058 found - extraction failed")
