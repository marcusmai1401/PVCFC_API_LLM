#!/usr/bin/env python
"""
Single-Pass Fix: Rebuild Indexes + Add Metadata
=================================================

Giải quyết 2 vấn đề cùng lúc:
1. Rebuild BM25/FAISS từ chunks hiện có (fix missing docs)
2. Thêm metadata (equipment_type, doc_type, etc.) từ source path

Chỉ cần chạy 1 lần!
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def extract_metadata_from_path(source_path: str, doc_id: str) -> dict:
    """
    Extract equipment metadata from file path.

    Examples:
        K06101_CO2 COMPRESSOR_HITACHI/Data/002_3N4-S4274343...
        → equipment_type: compressor, equipment_id: K06101, doc_type: datasheet, vendor: HITACHI

        KT06101_TURBINE_HTC/Data/07087-CP22-KT06101...
        → equipment_type: turbine, equipment_id: KT06101, doc_type: datasheet, vendor: HTC
    """
    metadata = {}

    # Equipment type từ path
    path_upper = source_path.upper()
    if "COMPRESSOR" in path_upper:
        metadata["equipment_type"] = "compressor"
    elif "TURBINE" in path_upper:
        metadata["equipment_type"] = "turbine"
    elif "PUMP" in path_upper:
        metadata["equipment_type"] = "pump"
    elif "MOTOR" in path_upper:
        metadata["equipment_type"] = "motor"
    elif "EXCHANGER" in path_upper or "HEAT EXCHANGER" in path_upper:
        metadata["equipment_type"] = "exchanger"
    elif "VESSEL" in path_upper:
        metadata["equipment_type"] = "vessel"
    else:
        metadata["equipment_type"] = "unknown"

    # Equipment ID từ filename pattern
    # Patterns: K06101, KT06101, P06101, etc.
    match = re.search(
        r"\b(K\d{5}|KT\d{5}|P\d{5}|M\d{5}|E\d{5}|V\d{5})\b", source_path, re.IGNORECASE
    )
    if match:
        metadata["equipment_id"] = match.group(1).upper()
    else:
        metadata["equipment_id"] = None

    # Doc type từ folder/filename
    if (
        "/Data/" in source_path
        or "\\Data\\" in source_path
        or "datasheet" in path_upper
    ):
        metadata["doc_type"] = "datasheet"
    elif (
        "/Manual/" in source_path
        or "\\Manual\\" in source_path
        or "manual" in path_upper
    ):
        metadata["doc_type"] = "manual"
    elif (
        "/Drawing/" in source_path
        or "\\Drawing\\" in source_path
        or "drawing" in path_upper
    ):
        metadata["doc_type"] = "drawing"
    elif "P&ID" in source_path or "PID" in path_upper:
        metadata["doc_type"] = "pid"
    elif "/Spare" in source_path or "spare part" in path_upper:
        metadata["doc_type"] = "spare_parts"
    elif "/Instrument/" in source_path or "instrument" in path_upper:
        metadata["doc_type"] = "instrument"
    elif "/Maintenance/" in source_path or "maintenance" in path_upper:
        metadata["doc_type"] = "maintenance"
    else:
        metadata["doc_type"] = "other"

    # Vendor từ path
    vendors = ["HITACHI", "HTC", "SIEMENS", "ABB", "MITSUBISHI", "GE", "SULZER"]
    for vendor in vendors:
        if vendor in path_upper:
            metadata["vendor"] = vendor
            break
    else:
        metadata["vendor"] = None

    # Language (default Vietnamese for this project)
    metadata["lang"] = "vi"

    return metadata


def enrich_chunks_with_metadata(chunks_dir: Path, doc_id_map_path: Path):
    """
    Load chunks, enrich với metadata, save lại.

    Returns:
        List of enriched chunks
    """
    logger.info("=" * 80)
    logger.info("STEP 1: ENRICH CHUNKS WITH METADATA")
    logger.info("=" * 80)

    # Load doc_id_map
    logger.info(f"Loading doc_id_map from {doc_id_map_path}")
    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    logger.info(f"Loaded {len(doc_id_map)} documents in doc_id_map")

    # Load all chunks
    chunk_files = list(chunks_dir.glob("*_chunks.json"))
    logger.info(f"Found {len(chunk_files)} chunk files")

    all_chunks = []
    enriched_count = 0
    missing_in_map = []

    for chunk_file in chunk_files:
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)

            # Get doc_id from first chunk
            if not chunks:
                continue

            doc_id = chunks[0].get("doc_id")
            if not doc_id:
                logger.warning(f"No doc_id in {chunk_file.name}")
                continue

            # Get source path from doc_id_map
            source_path = doc_id_map.get(doc_id)
            if not source_path:
                missing_in_map.append(doc_id)
                # Use filename as fallback
                source_path = chunk_file.stem.replace("_chunks", "")

            # Extract metadata
            auto_metadata = extract_metadata_from_path(source_path, doc_id)

            # Enrich each chunk
            for chunk in chunks:
                # Add to existing metadata (không ghi đè)
                if "metadata" not in chunk:
                    chunk["metadata"] = {}

                chunk["metadata"].update(auto_metadata)

                # Also add as top-level fields cho dễ query
                chunk.setdefault("equipment_type", auto_metadata["equipment_type"])
                chunk.setdefault("doc_type", auto_metadata["doc_type"])
                chunk.setdefault("equipment_id", auto_metadata["equipment_id"])
                chunk.setdefault("vendor", auto_metadata["vendor"])
                chunk.setdefault("lang", auto_metadata["lang"])
                chunk.setdefault("source_path", source_path)

                all_chunks.append(chunk)

            enriched_count += 1

            # Save enriched version
            with open(chunk_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to process {chunk_file.name}: {e}")

    logger.info(
        f"✓ Enriched {enriched_count} files with {len(all_chunks)} total chunks"
    )

    if missing_in_map:
        logger.warning(
            f"⚠️  {len(missing_in_map)} doc_ids not found in doc_id_map (used filename fallback)"
        )

    return all_chunks


def rebuild_indexes(chunks: list, output_base: Path):
    """
    Rebuild BM25 and FAISS indexes từ chunks.
    """
    logger.info("=" * 80)
    logger.info("STEP 2: REBUILD INDEXES")
    logger.info("=" * 80)

    from app.rag.indexers.bm25_indexer import BM25Indexer
    from app.rag.indexers.faiss_indexer import VectorIndexer
    from app.services.embedding_enhanced import get_embedding_service

    # Build BM25
    logger.info("Building BM25 index...")
    bm25_output = output_base / "bm25"
    bm25_output.mkdir(parents=True, exist_ok=True)

    bm25_indexer = BM25Indexer()
    bm25_indexer.build_index(chunks)
    bm25_indexer.save_index(str(bm25_output))
    logger.info(f"✓ BM25 index saved to {bm25_output}")

    # Build FAISS
    logger.info("Building FAISS index...")
    logger.info("⚠️  This will take 10-20 minutes for embedding...")

    faiss_output = output_base / "faiss"
    faiss_output.mkdir(parents=True, exist_ok=True)

    embedding_service = get_embedding_service()

    texts = [chunk["text"] for chunk in chunks]
    metadatas = []
    for chunk in chunks:
        # Create enriched metadata
        meta = {
            "doc_id": chunk.get("doc_id"),
            "chunk_id": chunk.get("chunk_id"),
            "page": chunk.get("page", chunk.get("page_start", 1)),
            "equipment_type": chunk.get("equipment_type"),
            "doc_type": chunk.get("doc_type"),
            "equipment_id": chunk.get("equipment_id"),
            "vendor": chunk.get("vendor"),
            "source_path": chunk.get("source_path"),
        }
        metadatas.append(meta)

    # Embed in batches
    import numpy as np

    embeddings_list = []
    batch_size = 100
    total_batches = (len(texts) + batch_size - 1) // batch_size

    start_time = datetime.now()

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_num = i // batch_size + 1

        logger.info(f"Embedding batch {batch_num}/{total_batches}")
        batch_embeddings = embedding_service.embed_texts(batch_texts)
        embeddings_list.append(batch_embeddings)

        if batch_num % 10 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = batch_num / elapsed
            remaining = (total_batches - batch_num) / rate
            logger.info(f"  ETA: {remaining/60:.1f} min")

    embeddings = np.vstack(embeddings_list)
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"✓ Embedding completed in {elapsed/60:.1f} minutes")

    # Build FAISS index
    faiss_indexer = VectorIndexer()
    faiss_indexer.build(embeddings, texts, metadatas)
    faiss_indexer.save(str(faiss_output))
    logger.info(f"✓ FAISS index saved to {faiss_output}")


def verify_fix(doc_id_to_check: str, bm25_dir: Path, faiss_dir: Path):
    """
    Verify that the missing document is now in indexes.
    """
    logger.info("=" * 80)
    logger.info("STEP 3: VERIFY FIX")
    logger.info("=" * 80)

    from app.rag.indexers.bm25_indexer import BM25Indexer
    from app.rag.indexers.faiss_indexer import VectorIndexer

    # Check BM25
    logger.info("Checking BM25 index...")
    bm25_indexer = BM25Indexer()
    bm25_indexer.load_index(str(bm25_dir))

    found_in_bm25 = any(
        doc_id_to_check in doc.get("doc_id", "") for doc in bm25_indexer.documents
    )
    logger.info(f"  Doc found in BM25: {found_in_bm25}")

    # Check FAISS
    logger.info("Checking FAISS index...")
    faiss_indexer = VectorIndexer()
    faiss_indexer.load(str(faiss_dir))

    found_in_faiss = any(doc_id_to_check in doc for doc in faiss_indexer.documents)
    logger.info(f"  Doc found in FAISS: {found_in_faiss}")

    if found_in_bm25 and found_in_faiss:
        logger.info("✅ SUCCESS: Document is now in both indexes!")
        return True
    else:
        logger.error("❌ FAILED: Document still missing from indexes")
        return False


def main():
    """
    Single-pass fix: enrich metadata + rebuild indexes.
    """
    logger.info("=" * 80)
    logger.info("SINGLE-PASS FIX: METADATA + INDEXES")
    logger.info("=" * 80)

    # Paths
    ingestion_dir = Path("artifacts/ingestion_production")
    chunks_dir = ingestion_dir / "chunks"
    doc_id_map_path = ingestion_dir / "doc_id_map.json"

    output_dir = Path("artifacts/index")

    # Verify paths exist
    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        return 1

    if not doc_id_map_path.exists():
        logger.error(f"doc_id_map.json not found: {doc_id_map_path}")
        return 1

    # Step 1: Enrich chunks with metadata
    enriched_chunks = enrich_chunks_with_metadata(chunks_dir, doc_id_map_path)

    if not enriched_chunks:
        logger.error("No chunks loaded")
        return 1

    logger.info(f"Total chunks to index: {len(enriched_chunks)}")

    # Step 2: Rebuild indexes
    rebuild_indexes(enriched_chunks, output_dir)

    # Step 3: Verify fix for the problematic document
    problem_doc_id = "DOCID_K06101_CO2_COMPRESSOR_HITACHI_K06101_CO2_COMPRESSOR_HITACHI_Data_002_3N4-S427434_1be298a4"

    success = verify_fix(problem_doc_id, output_dir / "bm25", output_dir / "faiss")

    if success:
        logger.info("=" * 80)
        logger.info("✅ ALL DONE! Indexes are now complete with metadata.")
        logger.info("=" * 80)
        logger.info("Next steps:")
        logger.info(
            "1. Test query: 'What is the 4th stage discharge pressure for K06101?'"
        )
        logger.info("2. Verify citation is now correct (002_3N4-S4274343 page 3)")
        logger.info("3. If OK, proceed with Weaviate migration")
        return 0
    else:
        logger.error("Fix failed. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
