"""
Complete Pipeline: Clear Data → Ingest → Chunk → Index
With all accuracy fixes enabled (C-2, C-3, M-3, M-4, H-4, H-5)
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set Google Cloud credentials
credentials_path = PROJECT_ROOT / "credentials.json"
if credentials_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
    print(f"✓ Google credentials set: {credentials_path}")
else:
    print(f"⚠️  Google credentials not found at: {credentials_path}")

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor
from app.ingestion.table_extractor import TableExtractor
from app.ingestion.text_chunker import ParentChildChunker


def run_clear_data(skip_confirmation=False):
    """Step 1: Clear all existing data"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: CLEAR ALL EXISTING DATA")
    logger.info("=" * 80 + "\n")

    if not skip_confirmation:
        logger.warning("⚠️  This will DELETE all existing data!")
        response = input("Type 'yes' to continue: ")
        if response.lower() != "yes":
            logger.info("Aborted")
            return False

    # Import and run clear script
    try:
        from scripts.clear_all_data_simple import (
            clear_artifacts,
            clear_opensearch,
            clear_weaviate,
            recreate_opensearch_indexes,
        )

        clear_opensearch()
        clear_weaviate()
        clear_artifacts()
        recreate_opensearch_indexes()

        logger.success("\n✓ Data cleared successfully\n")
        return True

    except Exception as e:
        logger.error(f"Failed to clear data: {e}")
        return False


def run_ingestion(input_dir: Path, output_dir: Path):
    """Step 2: PDF Processing + Chunking with all accuracy fixes"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: PDF PROCESSING + CHUNKING")
    logger.info("=" * 80 + "\n")

    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")

    # Check input directory
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return None

    # Count PDF files recursively
    pdf_files = list(input_dir.rglob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files (recursive)\n")

    if len(pdf_files) == 0:
        logger.warning("No PDF files found!")
        return None

    # Show sample files
    logger.info("Sample files (first 10):")
    for pdf in pdf_files[:10]:
        logger.info(f"  - {pdf.name}")
    if len(pdf_files) > 10:
        logger.info(f"  ... and {len(pdf_files) - 10} more\n")

    # Initialize processor with ALL accuracy fixes enabled
    logger.info("Initializing PDF processor with accuracy fixes:")
    logger.info("  ✓ C-2: Page metadata fix")
    logger.info("  ✓ C-3: Confidence score fix (applied at query time)")
    logger.info("  ✓ M-3: Table validation (column consistency + header checks)")
    logger.info("  ✓ M-4: Real-ESRGAN DPI check (<120 DPI)")
    logger.info("  ✓ H-4: Multi-document spatial search (applied at query time)")
    logger.info("  ✓ H-5: Citation regex (already correct)\n")

    processor = PDFProcessor(
        extract_tables=True,  # Enable M-3 table validation
        extract_images=False,
        enable_ocr=True,  # Enable M-4 DPI check
        force_ocr_all_pages=False,
        min_text_length=10,
        table_min_rows=2,  # M-3 validation
        table_min_cols=2,  # M-3 validation
    )

    # Phase 3: Use ParentChildChunker (parent ~1800, child ~400)
    chunker = ParentChildChunker(
        parent_chunk_size=1800,
        parent_overlap=200,
        child_chunk_size=400,
        child_overlap=50,
        min_chunk_size=100,
    )

    # Create output directories
    processed_dir = output_dir / "processed"
    chunks_dir = output_dir / "chunks"
    processed_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting batch processing...\n")
    start_time = time.time()

    # Process all PDFs
    all_chunks = []
    processed_docs = 0
    failed_docs = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        try:
            logger.info(f"[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")

            # Process PDF (with M-4 DPI check enabled)
            pdf_doc = processor.process_pdf(pdf_path)

            if not pdf_doc:
                logger.warning(f"  ⚠️  Failed to process (no content extracted)")
                failed_docs += 1
                continue

            logger.info(
                f"  ✓ Extracted {len(pdf_doc.pages)} pages, {pdf_doc.total_words} words"
            )

            # Chunk document (with C-2 page metadata fix)
            chunks = chunker.chunk_document(pdf_doc.to_dict())

            if chunks:
                logger.info(f"  ✓ Created {len(chunks)} chunks")
                all_chunks.extend([c.to_dict() for c in chunks])

                # Save per-document chunks
                chunk_file = chunks_dir / f"{pdf_path.stem}_chunks.json"
                with open(chunk_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [c.to_dict() for c in chunks], f, indent=2, ensure_ascii=False
                    )

                processed_docs += 1
            else:
                logger.warning(f"  ⚠️  No chunks created")
                failed_docs += 1

            # Progress update every 10 docs
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(pdf_files) - i) / rate
                logger.info(
                    f"\n  Progress: {i}/{len(pdf_files)} ({100*i/len(pdf_files):.1f}%) - ETA: {remaining/60:.1f} min\n"
                )

        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            failed_docs += 1
            continue

    elapsed = time.time() - start_time

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 80 + "\n")
    logger.info(f"Time elapsed: {elapsed/60:.1f} minutes")
    logger.info(f"Documents processed: {processed_docs}/{len(pdf_files)}")
    logger.info(f"Documents failed: {failed_docs}/{len(pdf_files)}")
    logger.info(f"Total chunks created: {len(all_chunks):,}")
    logger.info(
        f"Average chunks/doc: {len(all_chunks)/processed_docs:.1f}"
        if processed_docs > 0
        else "N/A"
    )
    logger.info(f"\nOutput:")
    logger.info(f"  - Chunks: {chunks_dir}")
    logger.info(f"  - Files: {len(list(chunks_dir.glob('*_chunks.json')))} JSON files")

    return all_chunks


def run_indexing(chunks_dir: Path, index_output_dir: Path):
    """Step 3: Build BM25 + FAISS + OpenSearch indexes"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: BUILDING INDEXES")
    logger.info("=" * 80 + "\n")

    # Import indexing modules
    from opensearchpy import OpenSearch

    from app.rag.indexers.bm25_indexer import BM25Indexer
    from app.rag.indexers.faiss_indexer import VectorIndexer
    from app.services.embedding_enhanced import get_embedding_service

    # Load all chunks
    logger.info(f"Loading chunks from {chunks_dir}")
    chunk_files = list(chunks_dir.glob("*_chunks.json"))

    if not chunk_files:
        logger.error("No chunk files found!")
        return False

    logger.info(f"Found {len(chunk_files)} chunk files")

    all_chunks = []
    for chunk_file in chunk_files:
        with open(chunk_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            all_chunks.extend(chunks)

    logger.info(f"Loaded {len(all_chunks):,} total chunks\n")

    # Create output directories
    bm25_dir = index_output_dir / "bm25"
    faiss_dir = index_output_dir / "faiss"
    bm25_dir.mkdir(parents=True, exist_ok=True)
    faiss_dir.mkdir(parents=True, exist_ok=True)

    # Build BM25 index
    logger.info("Building BM25 index...")
    bm25_indexer = BM25Indexer()
    bm25_indexer.build_index(all_chunks)
    bm25_indexer.save_index(str(bm25_dir))
    logger.success(f"✓ BM25 index saved to {bm25_dir}\n")

    # Build FAISS index
    logger.info("Building FAISS index (this will take ~10-20 minutes)...")
    embedding_service = get_embedding_service()

    texts = [chunk["text"] for chunk in all_chunks]
    metadatas = [chunk.get("metadata", {}) for chunk in all_chunks]

    # Embed in batches
    embeddings_list = []
    batch_size = 100
    total_batches = (len(texts) + batch_size - 1) // batch_size

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_num = i // batch_size + 1

        logger.info(f"  Embedding batch {batch_num}/{total_batches}")
        
        # Log memory usage if psutil is available
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            logger.debug(f"  Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")
        except ImportError:
            pass

        t0 = time.time()
        batch_embeddings = embedding_service.embed_texts(batch_texts)
        dt = time.time() - t0
        logger.info(f"  ✓ Batch {batch_num} done in {dt:.2f}s")
        
        embeddings_list.append(batch_embeddings)

    import numpy as np

    embeddings = np.vstack(embeddings_list)

    faiss_indexer = VectorIndexer()
    faiss_indexer.build(embeddings, texts, metadatas)
    faiss_indexer.save(str(faiss_dir))
    logger.success(f"✓ FAISS index saved to {faiss_dir}\n")

    # Index to OpenSearch
    logger.info("Indexing to OpenSearch...")
    opensearch_host = os.getenv("OPENSEARCH_HOST", "localhost")
    opensearch_port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    opensearch_index = os.getenv("OPENSEARCH_INDEX", "rag_chunks")

    client = OpenSearch(
        hosts=[{"host": opensearch_host, "port": opensearch_port}], timeout=60
    )

    # Bulk index
    from opensearchpy.helpers import bulk

    actions = []
    for chunk in all_chunks:
        action = {
            "_index": opensearch_index,
            "_id": chunk["chunk_id"],
            "_source": chunk,
        }
        actions.append(action)

    # Bulk index in chunks to avoid timeouts and better tracking
    chunk_size = 500
    total_actions = len(actions)
    total_success = 0
    total_failed = []
    
    logger.info(f"Indexing {total_actions} chunks to OpenSearch in batches of {chunk_size}...")
    
    for i in range(0, total_actions, chunk_size):
        batch_actions = actions[i : i + chunk_size]
        batch_num = i // chunk_size + 1
        total_batches = (total_actions + chunk_size - 1) // chunk_size
        
        logger.info(f"  Indexing batch {batch_num}/{total_batches} ({len(batch_actions)} docs)")
        
        try:
            s, f = bulk(client, batch_actions, chunk_size=chunk_size, raise_on_error=False, request_timeout=60)
            total_success += s
            if f:
                total_failed.extend(f)
                logger.warning(f"  ⚠️  {len(f)} failed in this batch")
        except Exception as e:
            logger.error(f"  ❌ Batch {batch_num} failed: {e}")
            
    success = total_success
    failed = total_failed
    logger.success(f"✓ Indexed {success:,} chunks to OpenSearch")
    if failed:
        logger.warning(f"⚠️  Failed to index {len(failed)} chunks")

    logger.info("\n" + "=" * 80)
    logger.success("✓ ALL INDEXES BUILT SUCCESSFULLY")
    logger.info("=" * 80 + "\n")

    return True


def main():
    """Main pipeline"""
    logger.info("\n" + "=" * 80)
    logger.info("COMPLETE INGESTION + INDEXING PIPELINE")
    logger.info("With Accuracy Fixes Enabled")
    logger.info("=" * 80 + "\n")

    # Configuration
    input_dir = Path(r"D:\Data_Raw")

    # Use ARTIFACTS_DIR from env, fallback to local artifacts
    artifacts_base = os.getenv("ARTIFACTS_DIR", "artifacts")
    output_dir = Path(artifacts_base) / "ingestion_production"
    index_output_dir = Path(artifacts_base) / "index_production"

    logger.info("Configuration:")
    logger.info(f"  Input: {input_dir}")
    logger.info(f"  Ingestion output: {output_dir}")
    logger.info(f"  Index output: {index_output_dir}\n")

    # Ask for confirmation
    response = input("Start full pipeline? Type 'yes' to continue: ")
    if response.lower() != "yes":
        logger.info("Aborted")
        return

    start_time = time.time()

    # Step 1: Clear data
    if not run_clear_data(skip_confirmation=True):
        logger.error("Failed to clear data")
        return

    # Step 2: Ingest + chunk
    all_chunks = run_ingestion(input_dir, output_dir)
    if not all_chunks:
        logger.error("Failed to ingest documents")
        return

    # Step 3: Build indexes
    chunks_dir = output_dir / "chunks"
    if not run_indexing(chunks_dir, index_output_dir):
        logger.error("Failed to build indexes")
        return

    total_time = time.time() - start_time

    # Final summary
    logger.info("\n" + "=" * 80)
    logger.success("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("=" * 80 + "\n")
    logger.info(f"Total time: {total_time/60:.1f} minutes")
    logger.info(f"Total chunks: {len(all_chunks):,}")
    logger.info(f"\nNext steps:")
    logger.info(f"  1. Test queries with accuracy fixes enabled")
    logger.info(f"  2. Verify C-2 page metadata in chunks")
    logger.info(f"  3. Check M-4 DPI logs for Real-ESRGAN decisions")
    logger.info(f"  4. Test H-4 multi-document spatial search")
    logger.info("=" * 80 + "\n")


if __name__ == "__main__":
    main()
