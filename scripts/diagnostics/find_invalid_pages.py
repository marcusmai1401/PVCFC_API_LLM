import json

import chromadb
from chromadb.config import Settings

# Load PDF page counts
print("Loading PDF page counts...")
with open(
    "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\ingestion\\pdf_page_counts.json",
    "r",
    encoding="utf-8",
) as f:
    page_counts = json.load(f)

print(f"Loaded page counts for {len(page_counts)} documents")

# Connect to ChromaDB
print("\nConnecting to ChromaDB...")
client = chromadb.PersistentClient(
    path="C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\chroma_db",
    settings=Settings(anonymized_telemetry=False),
)

# Get collection
collection = client.get_collection(name="pdf_documents")
count = collection.count()
print(f"Collection has {count} chunks")

# Get all data (in batches if needed)
print("\nFetching all chunks from ChromaDB...")
batch_size = 1000
all_invalid = []

for offset in range(0, count, batch_size):
    limit = min(batch_size, count - offset)
    print(
        f"Processing batch {offset//batch_size + 1} (offset {offset}, limit {limit})..."
    )

    results = collection.get(limit=limit, offset=offset, include=["metadatas"])

    # Check each chunk
    for idx, metadata in enumerate(results["metadatas"]):
        doc_id = metadata.get("doc_id", "")
        page_num = metadata.get("page_num")

        if doc_id in page_counts and page_num is not None:
            actual_page_count = page_counts[doc_id]
            # Page numbers are 0-indexed, so valid range is 0 to (page_count - 1)
            if page_num >= actual_page_count:
                all_invalid.append(
                    {
                        "doc_id": doc_id,
                        "chunk_page": page_num,
                        "actual_pages": actual_page_count,
                        "file_name": metadata.get("file_name", "Unknown"),
                    }
                )

print(f"\n{'='*70}")
print(f"RESULTS: Found {len(all_invalid)} invalid page references")
print(f"{'='*70}")

if all_invalid:
    # Group by document
    by_doc = {}
    for item in all_invalid:
        doc_id = item["doc_id"]
        if doc_id not in by_doc:
            by_doc[doc_id] = []
        by_doc[doc_id].append(item)

    print(f"\nAffected documents: {len(by_doc)}\n")

    for doc_id, items in list(by_doc.items())[:10]:  # Show first 10 docs
        print(f"Doc: {items[0]['file_name']}")
        print(f"  Doc ID: {doc_id[:60]}...")
        print(f"  Actual pages: {items[0]['actual_pages']}")
        print(f"  Invalid references: {len(items)}")
        invalid_pages = sorted(set(item["chunk_page"] for item in items))
        print(
            f"  Invalid page numbers: {invalid_pages[:10]}{'...' if len(invalid_pages) > 10 else ''}"
        )
        print()

    # Save detailed report
    report_file = (
        "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\invalid_page_references.json"
    )
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(by_doc, f, indent=2, ensure_ascii=False)
    print(f"✓ Detailed report saved to: {report_file}")
else:
    print("\n✓ No invalid page references found!")
    print("All page numbers are within valid ranges.")
