#!/usr/bin/env python
"""
Build BM25 index from processed documents
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor
from app.ingestion.text_chunker import TextChunker
from app.rag.indexers.bm25_indexer import BM25Indexer


def process_pdfs(
    pdf_dir: Path, output_dir: Path, enable_ocr: bool = False
) -> List[Dict]:
    """Process PDFs and create chunks"""
    logger.info(f"Processing PDFs from {pdf_dir}")
    if enable_ocr:
        logger.info("OCR enabled for scanned pages")

    # Initialize processors
    pdf_processor = PDFProcessor(
        enable_ocr=enable_ocr, ocr_language="eng", ocr_min_confidence=30.0
    )
    chunker = TextChunker(
        chunk_size=1000, chunk_overlap=200, chunking_strategy="semantic"
    )

    # Process PDFs
    documents = pdf_processor.process_directory(pdf_dir)

    # Save processed documents
    docs_dir = output_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    pdf_processor.save_processed_documents(documents, docs_dir)

    # Create chunks
    all_chunks = []
    for doc in documents:
        chunks = chunker.chunk_document(doc.to_dict())
        all_chunks.extend(chunks)

    # Save chunks
    chunks_file = output_dir / "chunks.json"
    chunker.save_chunks(all_chunks, chunks_file)

    logger.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")

    # Convert chunks to dict format for BM25Indexer
    chunk_dicts = []
    for chunk in all_chunks:
        chunk_dicts.append(
            {
                "text": chunk.text,
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "chunk_index": chunk.chunk_index,
                "page_nums": chunk.page_nums,
                **chunk.metadata,
            }
        )

    return chunk_dicts


def build_bm25_index(chunks: List[Dict], output_dir: Path):
    """Build and save BM25 index"""
    logger.info(f"Building BM25 index for {len(chunks)} documents")

    # Initialize indexer
    indexer = BM25Indexer()

    # Build index directly with chunks
    indexer.build_index(chunks)

    # Save index
    output_dir.mkdir(parents=True, exist_ok=True)
    indexer.save_index(str(output_dir))

    logger.info(f"Saved BM25 index to {output_dir}")

    # Test search
    test_query = "CO2 compressor"
    results = indexer.search(test_query, top_k=3)

    logger.info(f"Test search for '{test_query}':")
    for i, result in enumerate(results, 1):
        logger.info(
            f"  {i}. Score: {result['score']:.4f}, Text: {result['text'][:100]}..."
        )


def load_chunks_from_jsonl(jsonl_file: Path) -> List[Dict]:
    """Load chunks from JSONL file with full schema support"""
    chunks = []

    logger.info(f"Loading chunks from JSONL: {jsonl_file}")

    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)

                # Convert to expected format for BM25Indexer
                chunk_dict = {
                    "text": chunk.get("text", ""),
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "page_nums": [],  # Will be populated below
                    "parent_chunk_id": chunk.get("parent_chunk_id"),
                    "heading": chunk.get("heading", ""),
                    "level": chunk.get("level", 0),
                }

                # Handle page numbers - convert page_start/page_end to page_nums
                if "page_start" in chunk and "page_end" in chunk:
                    page_start = chunk["page_start"]
                    page_end = chunk["page_end"]
                    if page_start is not None and page_end is not None:
                        chunk_dict["page_nums"] = list(range(page_start, page_end + 1))
                elif "page_nums" in chunk:
                    chunk_dict["page_nums"] = chunk["page_nums"]

                # Add metadata fields
                if "metadata" in chunk:
                    for key, value in chunk["metadata"].items():
                        if key not in chunk_dict:  # Don't overwrite existing keys
                            chunk_dict[key] = value

                chunks.append(chunk_dict)

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON at line {line_num}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error processing line {line_num}: {e}")
                continue

    logger.info(f"Loaded {len(chunks)} chunks from JSONL")

    # Log sample metadata for verification
    if chunks:
        sample = chunks[0]
        logger.debug(
            f"Sample chunk metadata - doc_type: {sample.get('doc_type')}, "
            f"revision: {sample.get('revision')}, "
            f"parent_chunk_id: {sample.get('parent_chunk_id')}"
        )

    return chunks


def load_table_index(table_index_file: Path) -> List[Dict]:
    """Load table index from JSON file"""
    if not table_index_file.exists():
        logger.warning(f"Table index not found: {table_index_file}")
        return []

    logger.info(f"Loading table index from: {table_index_file}")

    try:
        with open(table_index_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        tables = data.get("tables", [])
        logger.info(f"Loaded {len(tables)} tables from index")

        # Count tables with torque data
        torque_tables = sum(1 for t in tables if t.get("has_torque_data", False))
        logger.info(f"  - {torque_tables} tables contain torque data")

        return tables

    except Exception as e:
        logger.error(f"Failed to load table index: {e}")
        return []


def augment_chunks_with_table_data(
    chunks: List[Dict], table_index: List[Dict]
) -> List[Dict]:
    """
    Augment chunks with table-specific boosting metadata.

    For chunks that contain tables, add:
    - has_table flag
    - table_keywords for boosting
    - has_torque_data flag
    """
    logger.info("Augmenting chunks with table metadata...")

    # Build chunk_id to table mapping
    chunk_to_tables = {}
    for table in table_index:
        chunk_id = table.get("chunk_id")
        if chunk_id:
            if chunk_id not in chunk_to_tables:
                chunk_to_tables[chunk_id] = []
            chunk_to_tables[chunk_id].append(table)

    # Augment chunks
    augmented_count = 0
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if chunk_id in chunk_to_tables:
            tables = chunk_to_tables[chunk_id]

            # Mark as having tables
            chunk["has_table"] = True
            chunk["table_count"] = len(tables)

            # Aggregate keywords from all tables in chunk
            all_keywords = set()
            has_torque = False
            for table in tables:
                keywords = table.get("keywords", [])
                all_keywords.update(keywords)
                if table.get("has_torque_data", False):
                    has_torque = True

            chunk["table_keywords"] = list(all_keywords)
            chunk["has_torque_data"] = has_torque

            # Boost text with keywords for BM25
            # Repeat important keywords to increase their weight
            if all_keywords:
                boost_text = " ".join(list(all_keywords) * 2)  # Repeat 2x for boost
                chunk["text"] = f"{chunk['text']}\n\n[TABLE_KEYWORDS: {boost_text}]"

            augmented_count += 1

    logger.info(f"Augmented {augmented_count} chunks with table metadata")
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Build BM25 index from documents")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/phase1_pilot"),
        help="Directory containing PDF files",
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("artifacts/chunks"),
        help="Directory to save processed chunks",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("artifacts/index/bm25"),
        help="Directory to save BM25 index",
    )
    parser.add_argument(
        "--use-existing-chunks",
        action="store_true",
        help="Use existing chunks instead of processing PDFs",
    )
    parser.add_argument(
        "--enable-ocr",
        action="store_true",
        help="Enable OCR for scanned PDF pages (requires pytesseract)",
    )

    parser.add_argument(
        "--chunks-jsonl",
        type=Path,
        help="Path to chunks JSONL file (alternative to processing PDFs)",
    )

    parser.add_argument(
        "--table-index",
        type=Path,
        help="Path to table_index.json file for table-aware indexing",
    )

    parser.add_argument(
        "--enable-table-boost",
        action="store_true",
        default=True,
        help="Enable table keyword boosting in BM25 (default: True)",
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("BM25 INDEX BUILDER")
    logger.info("=" * 80)

    if args.chunks_jsonl:
        # Load from JSONL
        if not args.chunks_jsonl.exists():
            logger.error(f"JSONL file not found: {args.chunks_jsonl}")
            sys.exit(1)

        chunk_dicts = load_chunks_from_jsonl(args.chunks_jsonl)
    elif args.use_existing_chunks:
        # Load existing chunks
        chunks_file = args.chunks_dir / "chunks.json"
        if not chunks_file.exists():
            logger.error(f"Chunks file not found: {chunks_file}")
            sys.exit(1)

        logger.info(f"Loading chunks from {chunks_file}")
        with open(chunks_file, "r", encoding="utf-8") as f:
            chunk_dicts = json.load(f)
    else:
        # Process PDFs and create chunks
        if not args.input_dir.exists():
            logger.error(f"Input directory not found: {args.input_dir}")
            sys.exit(1)

        chunk_dicts = process_pdfs(args.input_dir, args.chunks_dir, args.enable_ocr)

    # Load table index if available
    table_index = []
    if args.table_index:
        table_index = load_table_index(args.table_index)
    else:
        # Try to auto-detect table_index.json in standard location
        if args.chunks_jsonl:
            # Assume table_index.json is in same directory as chunks.jsonl
            auto_table_index = args.chunks_jsonl.parent / "table_index.json"
            if auto_table_index.exists():
                logger.info(f"Auto-detected table index: {auto_table_index}")
                table_index = load_table_index(auto_table_index)

    # Augment chunks with table metadata if available and enabled
    if table_index and args.enable_table_boost:
        chunk_dicts = augment_chunks_with_table_data(chunk_dicts, table_index)
        logger.info("Table-aware BM25 indexing enabled")
    else:
        logger.info("Standard BM25 indexing (no table boost)")

    # Build BM25 index
    build_bm25_index(chunk_dicts, args.index_dir)

    logger.info("=" * 80)
    logger.info("BM25 index building complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
