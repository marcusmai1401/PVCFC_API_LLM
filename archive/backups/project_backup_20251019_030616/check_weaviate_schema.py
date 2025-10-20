#!/usr/bin/env python
"""Check Weaviate schema to see available properties"""

import sys
from pathlib import Path

import weaviate
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

# Connect
client = weaviate.connect_to_local(
    host=settings.weaviate_host,
    port=settings.weaviate_port,
)

collection = client.collections.get(settings.weaviate_collection)

# Get schema
config = collection.config.get()

print(f"\n{'='*80}")
print(f"Weaviate Collection: {settings.weaviate_collection}")
print(f"{'='*80}\n")

print("Properties:")
for prop in config.properties:
    print(f"  - {prop.name} ({prop.data_type})")

print(f"\n{'='*80}\n")

# Fetch one sample object
print("Sample object:")
response = collection.query.fetch_objects(limit=1)
if response.objects:
    obj = response.objects[0]
    print(f"UUID: {obj.uuid}")
    print("Properties:")
    for key, value in obj.properties.items():
        print(f"  - {key}: {type(value).__name__} = {str(value)[:100]}")
else:
    print("No objects found")

print(f"\n{'='*80}\n")

client.close()
