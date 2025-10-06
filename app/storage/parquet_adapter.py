"""
Parquet Adapter for Index Builders

Provides utilities to read chunks from Parquet format for BM25/FAISS builders.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ParquetAdapter:
    """
    Adapter to read chunks from Parquet for downstream index builders.
    """

    @staticmethod
    def load_chunks_for_bm25(parquet_path: Path) -> List[Dict[str, Any]]:
        """
        Load chunks from Parquet and convert to BM25Indexer format.

        Expected BM25 format:
        {
            "text": str,
            "chunk_id": str,
            "doc_id": str,
            "chunk_index": int,
            "page_nums": List[int],
            "heading": str (optional),
            "level": int (optional),
            ... other metadata
        }

        Args:
            parquet_path: Path to chunks Parquet file

        Returns:
            List of chunk dictionaries for BM25Indexer
        """
        logger.info(f"Loading chunks from Parquet: {parquet_path}")

        df = pd.read_parquet(parquet_path)
        logger.info(f"Loaded {len(df)} chunks from Parquet")

        chunks = []
        for _, row in df.iterrows():
            chunk_dict = {
                "text": row["text"],
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "chunk_index": int(row["chunk_index"]),
                "page_nums": [int(row["page"])] if pd.notna(row["page"]) else [],
                "chunk_type": row["chunk_type"],
                "token_count": int(row["token_count"]),
                "char_count": int(row["char_count"]),
                "ingestion_version": row["ingestion_version"],
            }

            # Add section headers if present
            if pd.notna(row["section_header"]):
                chunk_dict["heading"] = row["section_header"]

            # Add headers list if present
            hdrs = row["headers"]
            if hdrs is not None:
                try:
                    if len(hdrs) > 0:
                        chunk_dict["headers_list"] = list(hdrs)
                except:
                    pass

            # Add equipment tags if present (for P&ID chunks)
            tags = row["equipment_tags"]
            if tags is not None:
                try:
                    if len(tags) > 0:
                        chunk_dict["equipment_tags"] = list(tags)
                except:
                    pass

            # Add bbox data if present
            if pd.notna(row["bbox_data"]):
                try:
                    chunk_dict["bbox"] = json.loads(row["bbox_data"])
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to parse bbox_data for chunk {row['chunk_id']}"
                    )

            chunks.append(chunk_dict)

        logger.info(f"✅ Converted {len(chunks)} chunks for BM25")
        return chunks

    @staticmethod
    def load_chunks_for_faiss(
        parquet_path: Path, filter_embedded: bool = True
    ) -> tuple[List[str], List[Dict[str, Any]], Optional[List[List[float]]]]:
        """
        Load chunks from Parquet and convert to FAISS format.

        Expected FAISS format:
        - texts: List[str]
        - metadata: List[Dict]
        - embeddings (optional): List[List[float]]

        Args:
            parquet_path: Path to chunks Parquet file
            filter_embedded: Only include chunks with embeddings

        Returns:
            Tuple of (texts, metadata, embeddings)
        """
        logger.info(f"Loading chunks from Parquet: {parquet_path}")

        df = pd.read_parquet(parquet_path)

        # Filter to only chunks with embeddings
        if filter_embedded:
            df = df[df["embedding"].notna()]
            logger.info(f"Filtered to {len(df)} chunks with embeddings")
        else:
            logger.info(f"Loaded {len(df)} chunks (some may not have embeddings)")

        texts = []
        metadatas = []
        embeddings = []

        for _, row in df.iterrows():
            texts.append(row["text"])

            # Build metadata dict
            metadata = {
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "page": int(row["page"]) if pd.notna(row["page"]) else None,
                "chunk_index": int(row["chunk_index"]),
                "chunk_type": row["chunk_type"],
                "token_count": int(row["token_count"]),
                "ingestion_version": row["ingestion_version"],
            }

            # Add section header if present
            if pd.notna(row["section_header"]):
                metadata["section_header"] = row["section_header"]

            # Add equipment tags if present
            tags = row["equipment_tags"]
            if tags is not None:
                try:
                    if len(tags) > 0:
                        metadata["equipment_tags"] = list(tags)
                except:
                    pass

            metadatas.append(metadata)

            # Add embedding if present
            emb = row["embedding"]
            if emb is not None:
                try:
                    embeddings.append(list(emb))
                except:
                    pass

        # Return None for embeddings if not all chunks have them
        embeddings_result = embeddings if len(embeddings) == len(texts) else None

        logger.info(f"✅ Loaded {len(texts)} texts, {len(metadatas)} metadata")
        if embeddings_result:
            logger.info(
                f"   Pre-computed embeddings available: {len(embeddings_result)}"
            )
        else:
            logger.info("   No pre-computed embeddings (will need to generate)")

        return texts, metadatas, embeddings_result

    @staticmethod
    def get_parquet_stats(parquet_path: Path) -> Dict[str, Any]:
        """
        Get statistics about Parquet file contents.

        Args:
            parquet_path: Path to chunks Parquet file

        Returns:
            Dictionary with statistics
        """
        df = pd.read_parquet(parquet_path)

        stats = {
            "total_chunks": len(df),
            "chunks_with_embeddings": df["embedding"].notna().sum(),
            "chunks_without_embeddings": df["embedding"].isna().sum(),
            "unique_documents": df["doc_id"].nunique(),
            "chunk_types": df["chunk_type"].value_counts().to_dict(),
            "avg_token_count": df["token_count"].mean(),
            "avg_char_count": df["char_count"].mean(),
            "total_pages": df[df["page"].notna()]["page"].nunique(),
        }

        # Check for P&ID chunks with equipment tags
        pid_chunks = df[df["chunk_type"] == "pid"]
        if len(pid_chunks) > 0:
            stats["pid_chunks"] = len(pid_chunks)
            stats["pid_chunks_with_tags"] = pid_chunks["equipment_tags"].notna().sum()

        return stats


if __name__ == "__main__":
    # Quick test with synthetic data
    logging.basicConfig(level=logging.INFO)

    from pathlib import Path

    from app.ingestion.chunkers.base import Chunk
    from app.storage.parquet_writer import ParquetWriter

    # Create test chunks
    test_chunks = [
        Chunk(
            chunk_id="chunk_001",
            doc_id="doc_001",
            text="This is a test chunk about CO2 compression.",
            chunk_type="text",
            page=1,
            chunk_index=0,
            token_count=10,
            content_hash="hash1",
            headers=["Section 1"],
            metadata={"section_header": "Introduction"},
        ),
        Chunk(
            chunk_id="chunk_002",
            doc_id="doc_001",
            text="P-101 pump specifications and torque data.",
            chunk_type="pid",
            page=2,
            chunk_index=1,
            token_count=8,
            content_hash="hash2",
            equipment_tags=["P-101"],
            metadata={},
        ),
    ]

    # Generate test embeddings
    test_embeddings = {"chunk_001": [0.1] * 768, "chunk_002": [0.2] * 768}

    # Write to Parquet
    output_path = Path("artifacts/test_adapter/test_chunks.parquet")
    writer = ParquetWriter(output_path, ingestion_version="test_v1")
    writer.write_chunks(test_chunks, embeddings=test_embeddings)

    # Test BM25 adapter
    print("\n=== Testing BM25 Adapter ===")
    bm25_chunks = ParquetAdapter.load_chunks_for_bm25(output_path)
    print(f"Loaded {len(bm25_chunks)} chunks for BM25")
    print(f"Sample: {bm25_chunks[0]}")

    # Test FAISS adapter
    print("\n=== Testing FAISS Adapter ===")
    texts, metas, embs = ParquetAdapter.load_chunks_for_faiss(output_path)
    print(f"Loaded {len(texts)} texts, {len(metas)} metadata")
    if embs:
        print(f"Pre-computed embeddings: {len(embs)} vectors of dim {len(embs[0])}")

    # Test stats
    print("\n=== Parquet Statistics ===")
    stats = ParquetAdapter.get_parquet_stats(output_path)
    print(json.dumps(stats, indent=2))
