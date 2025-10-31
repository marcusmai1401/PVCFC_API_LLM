import json

tags = []
with open("output/pid_ingestion/tags.jsonl", encoding="utf-8") as f:
    for line in f:
        tags.append(json.loads(line))

page58_tags = [t for t in tags if t.get("page") == 58]

print(f"Found {len(page58_tags)} tags extracted from page 58:")
print()

# Look for TI or TT tags with suffix 5058
target_tags = [t for t in page58_tags if t.get("suffix") == "5058"]

if target_tags:
    print("Tags with suffix 5058:")
    for t in target_tags:
        variant = f" {t.get('variant')}" if t.get("variant") else ""
        print(f"  {t['unit']} {t['prefix']} {t['suffix']}{variant}")
else:
    print("No tags with suffix 5058 found")

print(f"\nAll TI tags on page 58:")
ti_tags = [t for t in page58_tags if t.get("prefix") == "TI"]
if ti_tags:
    for t in ti_tags:
        variant = f" {t.get('variant')}" if t.get("variant") else ""
        print(f"  {t['unit']} {t['prefix']} {t['suffix']}{variant}")
else:
    print("  (none)")

print(f"\nAll TT tags on page 58:")
tt_tags = [t for t in page58_tags if t.get("prefix") == "TT"]
if tt_tags:
    for t in tt_tags[:15]:  # First 15
        variant = f" {t.get('variant')}" if t.get("variant") else ""
        print(f"  {t['unit']} {t['prefix']} {t['suffix']}{variant}")
    if len(tt_tags) > 15:
        print(f"  ... and {len(tt_tags) - 15} more TT tags")
else:
    print("  (none)")
