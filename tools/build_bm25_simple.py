#!/usr/bin/env python
"""
Build BM25 index from existing processed JSON files
No PDF processing needed, works with PyMuPDF DLL errors
"""
import json
import os
import pickle
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger
from rank_bm25 import BM25Okapi


def load_processed_data(data_dir: Path):
    """Load processed JSON files from data/processed"""
    all_chunks = []

    # Load JSON files
    json_files = list(data_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files")

    for json_file in json_files:
        logger.info(f"Loading {json_file.name}")
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract chunks based on structure
            if isinstance(data, dict):
                # Check if it has chunks key
                if "chunks" in data:
                    chunks = data["chunks"]
                elif "documents" in data:
                    # Process documents to chunks
                    for doc in data["documents"]:
                        if "chunks" in doc:
                            chunks.extend(doc["chunks"])
                        else:
                            # Create a single chunk from document
                            chunk = {
                                "text": doc.get("text", doc.get("content", "")),
                                "doc_id": doc.get("doc_id", json_file.stem),
                                "page": doc.get("page", 1),
                                "metadata": doc.get("metadata", {}),
                            }
                            chunks.append(chunk)
                else:
                    # Assume it's a single document
                    chunk = {
                        "text": data.get("text", data.get("content", str(data))),
                        "doc_id": json_file.stem,
                        "page": 1,
                        "metadata": data.get("metadata", {}),
                    }
                    chunks = [chunk]
            elif isinstance(data, list):
                # List of chunks or documents
                chunks = data
            else:
                logger.warning(f"Unknown structure in {json_file.name}")
                continue

            # Normalize chunks
            for i, chunk in enumerate(chunks):
                if isinstance(chunk, str):
                    chunk = {"text": chunk, "doc_id": json_file.stem, "chunk_id": i}
                elif "text" not in chunk and "content" in chunk:
                    chunk["text"] = chunk["content"]

                # Ensure required fields
                chunk["chunk_id"] = chunk.get("chunk_id", f"{json_file.stem}_{i}")
                chunk["doc_id"] = chunk.get("doc_id", json_file.stem)

                all_chunks.append(chunk)

        except Exception as e:
            logger.error(f"Error loading {json_file.name}: {e}")
            continue

    logger.info(f"Loaded {len(all_chunks)} chunks total")
    return all_chunks


def tokenize(text: str):
    """Simple tokenization for BM25"""
    # Basic tokenization - split on whitespace and punctuation
    import re

    # Keep alphanumeric, spaces, and some technical chars
    text = re.sub(r"[^\w\s\-_.]", " ", text.lower())
    tokens = text.split()
    return [t for t in tokens if len(t) > 1]  # Filter very short tokens


def build_bm25_index(chunks, output_dir: Path):
    """Build and save BM25 index"""
    logger.info(f"Building BM25 index for {len(chunks)} chunks")

    # Extract texts and metadata
    texts = []
    metadatas = []

    for chunk in chunks:
        text = chunk.get("text", "")
        if text:  # Only add non-empty texts
            texts.append(text)
            metadatas.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "page": chunk.get("page", 1),
                    **chunk.get("metadata", {}),
                }
            )

    logger.info(f"Processing {len(texts)} non-empty texts")

    # Tokenize all documents
    tokenized_docs = [tokenize(text) for text in texts]

    # Build BM25 index
    bm25 = BM25Okapi(tokenized_docs)

    # Save index
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save BM25 object
    with open(output_dir / "bm25_index.pkl", "wb") as f:
        pickle.dump(bm25, f)

    # Save texts
    with open(output_dir / "texts.json", "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)

    # Save metadata
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadatas, f, ensure_ascii=False, indent=2)

    # Save tokenized docs for reference
    with open(output_dir / "tokenized_docs.pkl", "wb") as f:
        pickle.dump(tokenized_docs, f)

    logger.info(f"Saved BM25 index to {output_dir}")

    # Test search
    test_queries = ["CO2 compressor", "KT06101", "pressure", "steam turbine"]

    for query in test_queries:
        query_tokens = tokenize(query)
        scores = bm25.get_scores(query_tokens)

        # Get top 3 results
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :3
        ]

        logger.info(f"\nTest search for '{query}':")
        for rank, idx in enumerate(top_indices, 1):
            if scores[idx] > 0:
                logger.info(f"  {rank}. Score: {scores[idx]:.4f}")
                logger.info(f"     Doc: {metadatas[idx]['doc_id']}")
                logger.info(f"     Text: {texts[idx][:100]}...")


def main():
    # Paths
    data_dir = Path("data/processed")
    output_dir = Path("artifacts/index/bm25")

    logger.info("=" * 80)
    logger.info("SIMPLE BM25 INDEX BUILDER")
    logger.info("=" * 80)

    # Load data
    chunks = load_processed_data(data_dir)

    if not chunks:
        logger.error("No chunks loaded!")
        sys.exit(1)

    # Build index
    build_bm25_index(chunks, output_dir)

    logger.info("=" * 80)
    logger.info("BM25 index building complete!")
    logger.info(f"Index saved to: {output_dir}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
