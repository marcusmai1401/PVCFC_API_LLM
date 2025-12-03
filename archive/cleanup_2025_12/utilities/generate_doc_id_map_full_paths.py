"""
Enhanced doc_id_map Generator with Full PDF Path Mapping
Scans D:\Data_Raw recursively and maps file names to full paths
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional


def scan_pdf_directory(pdf_base_dir: str) -> Dict[str, str]:
    """
    Scan directory recursively and build file_name -> full_path mapping

    Args:
        pdf_base_dir: Base directory to scan (e.g., D:\Data_Raw)

    Returns:
        Dictionary mapping file_name to full absolute path
    """
    print(f"\n📁 Scanning PDF directory: {pdf_base_dir}")
    print("=" * 80)

    base_path = Path(pdf_base_dir)
    if not base_path.exists():
        raise FileNotFoundError(f"Directory not found: {pdf_base_dir}")

    # Find all PDFs recursively
    pdf_files = list(base_path.rglob("*.pdf"))
    print(f"   Found {len(pdf_files)} PDF files")

    # Build mapping: filename -> full path
    file_name_to_path = {}
    duplicates = defaultdict(list)

    for pdf_file in pdf_files:
        file_name = pdf_file.name
        full_path = str(pdf_file.absolute())

        # Track duplicates (same filename in different folders)
        if file_name in file_name_to_path:
            duplicates[file_name].append(full_path)
            # Keep the first occurrence, but warn
            print(f"   ⚠️  Duplicate: {file_name}")
            print(f"      Existing: {file_name_to_path[file_name]}")
            print(f"      New:      {full_path}")
        else:
            file_name_to_path[file_name] = full_path

    if duplicates:
        print(f"\n   ⚠️  Found {len(duplicates)} duplicate file names")
        print("   Using first occurrence for each duplicate")

    print(f"\n   ✅ Built mapping for {len(file_name_to_path)} unique file names")
    return file_name_to_path


def generate_doc_id_map_with_full_paths(
    faiss_metadata_path: str = "data/indexes/faiss_index/metadatas.json",
    output_path: str = "artifacts/ingestion/doc_id_map.json",
    pdf_base_dir: str = "D:\\Data_Raw",
) -> Dict[str, Any]:
    """
    Generate doc_id_map from FAISS metadata with full PDF paths

    Args:
        faiss_metadata_path: Path to FAISS metadatas.json
        output_path: Output path for doc_id_map.json
        pdf_base_dir: Base directory containing PDF files

    Returns:
        Generated doc_id_map dictionary
    """
    print("=" * 80)
    print("  ENHANCED DOC_ID_MAP GENERATOR - Full PDF Paths")
    print("=" * 80)

    # Step 1: Scan PDF directory
    try:
        file_name_to_path = scan_pdf_directory(pdf_base_dir)
    except Exception as e:
        print(f"\n❌ Error scanning PDF directory: {e}")
        raise

    # Step 2: Load FAISS metadata
    print(f"\n📖 Loading FAISS metadata from {faiss_metadata_path}")
    print("=" * 80)

    metadata_file = Path(faiss_metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {faiss_metadata_path}")

    with open(metadata_file, "r", encoding="utf-8") as f:
        all_metadata = json.load(f)

    print(f"   Found {len(all_metadata)} chunks")

    # Step 3: Extract unique documents and map to PDF paths
    print(f"\n🔗 Mapping documents to PDF paths")
    print("=" * 80)

    doc_info = {}
    doc_stats = defaultdict(lambda: {"chunks": 0, "pages": set()})

    matched_count = 0
    unmatched_count = 0
    unmatched_files = set()

    for meta in all_metadata:
        doc_id = meta.get("doc_id")
        if not doc_id:
            continue

        # Track stats
        doc_stats[doc_id]["chunks"] += 1
        if "page" in meta:
            doc_stats[doc_id]["pages"].add(meta["page"])

        # Build doc_info if not already present
        if doc_id not in doc_info:
            file_name = meta.get("file_name", "")

            # Try to find full path
            pdf_path = None
            if file_name and file_name in file_name_to_path:
                pdf_path = file_name_to_path[file_name]
                matched_count += 1
            else:
                # File not found in scan
                if file_name:
                    unmatched_files.add(file_name)
                unmatched_count += 1
                # Use file_name as fallback (relative path)
                pdf_path = file_name if file_name else None

            doc_info[doc_id] = {
                "doc_id": doc_id,
                "file_name": file_name,
                "pdf_path": pdf_path,
                "doc_type": meta.get("doc_type", ""),
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "revision": meta.get("revision", ""),
                "source_format": meta.get("source_format", ""),
            }

    # Add statistics
    for doc_id, info in doc_info.items():
        stats = doc_stats[doc_id]
        info["total_chunks"] = stats["chunks"]
        info["total_pages"] = len(stats["pages"])

    print(f"   ✅ Matched {matched_count}/{len(doc_info)} documents to PDF paths")
    if unmatched_count > 0:
        print(f"   ⚠️  Unmatched: {unmatched_count} documents")
        print(f"\n   Unmatched file names:")
        for fn in sorted(unmatched_files)[:10]:  # Show first 10
            print(f"      - {fn}")
        if len(unmatched_files) > 10:
            print(f"      ... and {len(unmatched_files) - 10} more")

    # Step 4: Save to file
    print(f"\n💾 Saving doc_id_map to {output_path}")
    print("=" * 80)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(doc_info, f, indent=2, ensure_ascii=False)

    print(f"   ✅ Successfully saved {len(doc_info)} entries")

    # Step 5: Show statistics
    print(f"\n📊 Statistics")
    print("=" * 80)

    print(f"   Total documents: {len(doc_info)}")
    print(f"   Total chunks: {len(all_metadata)}")
    print(f"   PDF files found: {len(file_name_to_path)}")
    print(
        f"   Matched to PDFs: {matched_count} ({matched_count/len(doc_info)*100:.1f}%)"
    )

    # Document types
    doc_types = defaultdict(int)
    for info in doc_info.values():
        doc_types[info["doc_type"]] += 1

    print(f"\n   Document types:")
    for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
        print(f"      {doc_type or '(none)'}: {count}")

    # Show sample with full paths
    print(f"\n   Sample entries with full paths:")
    for i, (doc_id, info) in enumerate(list(doc_info.items())[:3]):
        print(f"\n   {i+1}. {doc_id[:60]}...")
        print(f"      file_name: {info['file_name']}")
        print(
            f"      pdf_path: {info['pdf_path'][:80]}..."
            if info["pdf_path"] and len(info["pdf_path"]) > 80
            else f"      pdf_path: {info['pdf_path']}"
        )
        print(f"      doc_type: {info['doc_type']}")
        print(f"      chunks: {info['total_chunks']}, pages: {info['total_pages']}")

    return doc_info


if __name__ == "__main__":
    import sys

    print()

    # Parse arguments
    pdf_base_dir = "D:\\Data_Raw"
    if len(sys.argv) > 1:
        pdf_base_dir = sys.argv[1]
        print(f"📁 Using custom PDF directory: {pdf_base_dir}")
        print()

    try:
        doc_id_map = generate_doc_id_map_with_full_paths(pdf_base_dir=pdf_base_dir)

        print("\n" + "=" * 80)
        print("✅ SUCCESS! doc_id_map.json generated with FULL PDF PATHS")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Restart the API to load the new doc_id_map.json")
        print("     Run: .\\quick_restart.ps1")
        print()
        print("  2. Test PDF citations:")
        print("     Run: python test_pdf_citations.py")
        print()
        print("  3. Verify in API logs:")
        print("     Should see: 'Loaded doc_id_map with 76 entries'")
        print()
        print("🎉 Citations will now show FULL PATHS like:")
        print("   D:\\Data_Raw\\K06101_CO2 COMPRESSOR_HITACHI\\...")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
