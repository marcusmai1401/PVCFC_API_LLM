import json
import pickle

print("=" * 80)
print("CHECKING FOR FILE: 002_3N4-S4274343 datasheet for K06101_Rev.02.pdf")
print("=" * 80)

# 1. Check FAISS index
print("\n1. Checking FAISS index...")
try:
    with open("data/indexes/faiss_index/metadata.pkl", "rb") as f:
        faiss_meta = pickle.load(f)

    print(f"   Total chunks in FAISS: {len(faiss_meta)}")

    matches = []
    for i, meta in enumerate(faiss_meta):
        doc_id = meta.get("doc_id", "")
        if "S4274343" in doc_id:
            matches.append((i, meta))

    print(f"   Found {len(matches)} chunks from S4274343:")
    for i, meta in matches[:10]:
        page = meta.get("page", "N/A")
        chunk_id = meta.get("chunk_id", "N/A")
        print(f"     - page={page}, chunk_id={chunk_id[:60]}")

    if len(matches) == 0:
        print("   ❌ FILE NOT FOUND IN FAISS INDEX!")

except Exception as e:
    print(f"   Error loading FAISS: {e}")

# 2. Check BM25 index
print("\n2. Checking BM25 index...")
try:
    # Load via indexer
    import sys

    sys.path.insert(0, ".")
    from app.rag.indexers.bm25_indexer import BM25Indexer

    indexer = BM25Indexer()
    indexer.load_index("data/indexes/bm25")

    print(f"   Total docs in BM25: {indexer.index.get_corpus_size()}")

    # Check doc_ids
    if hasattr(indexer, "doc_ids"):
        matches = [i for i, did in enumerate(indexer.doc_ids) if "S4274343" in did]
        print(f"   Found {len(matches)} chunks from S4274343")

        if len(matches) == 0:
            print("   ❌ FILE NOT FOUND IN BM25 INDEX!")
        else:
            for i in matches[:10]:
                print(f"     - Index {i}: {indexer.doc_ids[i][:80]}")
    else:
        print("   ⚠️  Cannot access doc_ids")

except Exception as e:
    print(f"   Error loading BM25: {e}")

# 3. Check doc_id_map
print("\n3. Checking doc_id_map.json...")
try:
    with open("artifacts/ingestion_production/doc_id_map.json", "r") as f:
        doc_id_map = json.load(f)

    matches = {k: v for k, v in doc_id_map.items() if "S4274343" in k}

    if matches:
        print(f"   ✅ Found in doc_id_map:")
        for doc_id, path in matches.items():
            print(f"     doc_id: {doc_id}")
            print(f"     path: {path}")
    else:
        print("   ❌ NOT FOUND in doc_id_map!")

except Exception as e:
    print(f"   Error loading doc_id_map: {e}")

# 4. Summary
print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print("The file '002_3N4-S4274343 datasheet for K06101_Rev.02.pdf' page 3")
print("contains the CORRECT answer but may not be properly indexed.")
print("\nIf the file is:")
print("  ✅ In doc_id_map BUT ❌ NOT in BM25/FAISS indexes")
print("  → The file exists but was NOT indexed during ingestion!")
print("  → Solution: Re-run ingestion pipeline for this file")
print("=" * 80)
