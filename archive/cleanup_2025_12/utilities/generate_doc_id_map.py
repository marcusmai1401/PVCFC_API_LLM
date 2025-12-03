"""
Generate doc_id_map.json from FAISS index metadata
Maps doc_id to file information for PDF citations
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict


def generate_doc_id_map(
    faiss_metadata_path: str = "data/indexes/faiss_index/metadatas.json",
    output_path: str = "artifacts/ingestion/doc_id_map.json",
    pdf_base_dir: str = None,
) -> Dict[str, Any]:
    """
    Generate doc_id_map from FAISS metadata

    Args:
        faiss_metadata_path: Path to FAISS metadatas.json
        output_path: Output path for doc_id_map.json
        pdf_base_dir: Optional base directory for PDF files

    Returns:
        Generated doc_id_map dictionary
    """
    print(f"📖 Loading metadata from {faiss_metadata_path}...")

    # Load FAISS metadata
    metadata_file = Path(faiss_metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {faiss_metadata_path}")

    with open(metadata_file, "r", encoding="utf-8") as f:
        all_metadata = json.load(f)

    print(f"   Found {len(all_metadata)} chunks")

    # Extract unique documents
    doc_info = {}
    doc_stats = defaultdict(lambda: {"chunks": 0, "pages": set()})

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

            # Construct PDF path
            if pdf_base_dir and file_name:
                pdf_path = str(Path(pdf_base_dir) / file_name)
            else:
                # Use relative path or file name
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

    print(f"\n✅ Generated doc_id_map for {len(doc_info)} documents")
    print(f"   Total chunks: {len(all_metadata)}")

    # Show sample
    print("\n📊 Sample entries:")
    for i, (doc_id, info) in enumerate(list(doc_info.items())[:3]):
        print(f"\n   {i+1}. {doc_id[:50]}...")
        print(f"      File: {info['file_name']}")
        print(f"      Type: {info['doc_type']}")
        print(f"      Chunks: {info['total_chunks']}, Pages: {info['total_pages']}")

    # Create output directory
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to file
    print(f"\n💾 Saving to {output_path}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(doc_info, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully saved {len(doc_info)} entries")

    # Statistics
    doc_types = defaultdict(int)
    for info in doc_info.values():
        doc_types[info["doc_type"]] += 1

    print("\n📈 Document types:")
    for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
        print(f"   {doc_type or '(none)'}: {count}")

    return doc_info


if __name__ == "__main__":
    import sys

    print("=" * 80)
    print("  DOC_ID_MAP GENERATOR")
    print("=" * 80)
    print()

    # Parse arguments
    pdf_base_dir = None
    if len(sys.argv) > 1:
        pdf_base_dir = sys.argv[1]
        print(f"📁 Using PDF base directory: {pdf_base_dir}")
        print()
    else:
        print("💡 No PDF base directory specified. Using file_name as pdf_path.")
        print(
            "   To specify PDF directory, run: python generate_doc_id_map.py <pdf_dir>"
        )
        print()

    try:
        doc_id_map = generate_doc_id_map(pdf_base_dir=pdf_base_dir)

        print("\n" + "=" * 80)
        print("✅ SUCCESS! doc_id_map.json generated")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Restart the API to load the new doc_id_map.json")
        print("  2. Test citations - they should now show file names")
        print()

        if not pdf_base_dir:
            print("⚠️  Note: pdf_path is set to file_name only.")
            print("   To use full paths, re-run with PDF directory:")
            print("   python generate_doc_id_map.py data/pdfs")
            print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
