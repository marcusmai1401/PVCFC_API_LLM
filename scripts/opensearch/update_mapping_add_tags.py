"""
Update OpenSearch index mapping to add 'tags' and 'tags_raw' keyword fields.
Safe to run multiple times; will check existing mapping first.
"""
import sys

from opensearchpy import OpenSearch

INDEX_NAME = "rag_chunks"


def field_exists(client: OpenSearch, index: str, field: str) -> bool:
    mapping = client.indices.get_mapping(index=index)
    props = mapping.get(index, {}).get("mappings", {}).get("properties", {})
    return field in props


def add_keyword_field(client: OpenSearch, index: str, field: str):
    body = {"properties": {field: {"type": "keyword", "ignore_above": 256}}}
    client.indices.put_mapping(index=index, body=body)


def main():
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=30,
    )

    changed = False
    for fld in ["tags", "tags_raw"]:
        try:
            if field_exists(client, INDEX_NAME, fld):
                print(f"Field '{fld}' already exists.")
            else:
                print(f"Adding field '{fld}' as keyword...")
                add_keyword_field(client, INDEX_NAME, fld)
                changed = True
        except Exception as e:
            print(f"Failed to update field '{fld}': {e}")
            return 1

    if changed:
        print(
            "Mapping updated. A reindex may be required for existing documents to populate new fields."
        )
    else:
        print("No changes made. Mapping already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
