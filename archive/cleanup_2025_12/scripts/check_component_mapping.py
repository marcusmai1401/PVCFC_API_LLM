"""Check component field mapping in spatial index"""
import json

import requests

response = requests.get("http://localhost:9200/pvcfc_pid_spatial_components/_mapping")
mapping = response.json()

properties = (
    mapping.get("pvcfc_pid_spatial_components", {})
    .get("mappings", {})
    .get("properties", {})
)

print("=" * 70)
print("COMPONENT FIELD MAPPING")
print("=" * 70)

if "component" in properties:
    comp_config = properties["component"]
    print(f"\n'component' field configuration:")
    print(json.dumps(comp_config, indent=2))

    field_type = comp_config.get("type", "not specified")
    print(f"\nField type: {field_type}")

    if field_type != "keyword":
        print(f"\n⚠️  WARNING: 'component' is {field_type}, not 'keyword'!")
        print("   This means term queries may not work as expected.")
        print("   Text fields are analyzed/tokenized, keyword fields are not.")
else:
    print("\n❌ 'component' field NOT found in mapping!")

# Check component_type too
if "component_type" in properties:
    ct_config = properties["component_type"]
    print(f"\n'component_type' field:")
    print(f"  Type: {ct_config.get('type')}")
