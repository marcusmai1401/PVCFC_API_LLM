"""
Re-index page 17 tags to OpenSearch to fix missing 04 TXI 2077
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from opensearchpy import OpenSearch

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
page_num = 17
doc_id = "Ammonia"
index_name = "pvcfc_pid_tags"

print("=" * 80)
print(f"Re-indexing tags from page {page_num}")
print("=" * 80)

# Extract tags
print("\n[1] Extracting tags...")
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, page_num, doc_id)

extractor = TagExtractor()
tags = extractor.extract_tags(layout)

print(f"✓ Extracted {len(tags)} tags from page {page_num}")

# Show TXI 2077
for tag in tags:
    tag_text = f"{tag.parts.unit} {tag.parts.prefix} {tag.parts.suffix}".strip()
    if "TXI" in tag_text and "2077" in tag_text:
        print(f"\n  Target tag found: {tag_text} (confidence: {tag.confidence:.2f})")

# Connect to OpenSearch
print("\n[2] Connecting to OpenSearch...")
client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    ssl_assert_hostname=False,
    ssl_show_warn=False,
)

# Delete existing page 17 tags
print(f"\n[3] Deleting existing page {page_num} tags...")
delete_response = client.delete_by_query(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [{"term": {"page": page_num}}, {"match": {"doc_id": doc_id}}]
            }
        }
    },
)
print(f"✓ Deleted {delete_response['deleted']} existing tags")

# Index new tags
print(f"\n[4] Indexing {len(tags)} tags...")
from opensearchpy.helpers import bulk

actions = []
for tag in tags:
    tag_text = f"{tag.parts.unit} {tag.parts.prefix} {tag.parts.suffix}".strip()
    if tag.parts.variant:
        tag_text += tag.parts.variant

    doc = {
        "_index": index_name,
        "_source": {
            "doc_id": doc_id,
            "page": page_num,
            "tag_text": tag_text,
            "tag_parts": {
                "unit": tag.parts.unit,
                "prefix": tag.parts.prefix,
                "suffix": tag.parts.suffix,
                "variant": tag.parts.variant,
            },
            "confidence": tag.confidence,
            "bbox": tag.bbox,
            "chunk_id": f"{doc_id}_page{page_num}_tag_{tag_text.replace(' ', '_')}",
        },
    }
    actions.append(doc)

success, errors = bulk(client, actions, raise_on_error=False)
print(f"✓ Indexed {success} tags")

if errors:
    print(f"⚠ {len(errors)} errors occurred")

# Verify TXI 2077 is now in index
print("\n[5] Verifying '04 TXI 2077' in index...")
verify_response = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [
                    {"term": {"tag_parts.unit": "04"}},
                    {"term": {"tag_parts.prefix": "TXI"}},
                    {"term": {"tag_parts.suffix": "2077"}},
                ]
            }
        }
    },
)

if verify_response["hits"]["total"]["value"] > 0:
    print("✓ SUCCESS: '04 TXI 2077' is now in the index!")
    hit = verify_response["hits"]["hits"][0]["_source"]
    print(f"  Tag: {hit['tag_text']}")
    print(f"  Page: {hit['page']}")
    print(f"  Confidence: {hit['confidence']:.2f}")
else:
    print("✗ FAILED: '04 TXI 2077' still not in index")

print("\n" + "=" * 80)
print("Re-indexing complete!")
print("=" * 80)
