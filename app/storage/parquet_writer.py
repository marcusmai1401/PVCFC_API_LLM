"""
Parquet Writer for Chunk Storage

Writes chunks with embeddings to Parquet format with schema validation.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.ingestion.chunkers.base import Chunk

logger = logging.getLogger(__name__)


class ParquetWriter:
    """
    Writes chunks to Parquet format with proper schema and compression.
    """

    # Define Parquet schema
    SCHEMA = pa.schema(
        [
            # Identifiers
            ("chunk_id", pa.string()),
            ("doc_id", pa.string()),
            ("page", pa.int32()),
            ("chunk_index", pa.int32()),
            # Content
            ("text", pa.string()),
            ("content_hash", pa.string()),
            # Chunking metadata
            ("chunk_type", pa.string()),
            ("token_count", pa.int32()),
            ("char_count", pa.int32()),
            # Embeddings
            ("embedding", pa.list_(pa.float32())),
            ("embedding_model", pa.string()),
            ("embedding_timestamp", pa.timestamp("us")),
            # P&ID specific (nullable)
            ("equipment_tags", pa.list_(pa.string())),
            ("bbox_data", pa.string()),
            # Headers/structure (nullable)
            ("headers", pa.list_(pa.string())),
            ("section_header", pa.string()),
            # Provenance
            ("created_at", pa.timestamp("us")),
            ("ingestion_version", pa.string()),
        ]
    )

    def __init__(
        self,
        output_path: Path,
        ingestion_version: str = "1.0.0",
        compression: str = "snappy",
    ):
        """
        Initialize Parquet writer.

        Args:
            output_path: Path to output Parquet file
            ingestion_version: Version tag for this ingestion
            compression: Compression codec (snappy, gzip, zstd)
        """
        self.output_path = Path(output_path)
        self.ingestion_version = ingestion_version
        self.compression = compression

        # Create parent directory
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"ParquetWriter initialized: {self.output_path}")

    def write_chunks(
        self,
        chunks: List[Chunk],
        embeddings: Optional[Dict[str, List[float]]] = None,
        embedding_model: str = "gemini-embedding-001",
    ) -> Dict[str, Any]:
        """
        Write chunks to Parquet with optional embeddings.

        Args:
            chunks: List of Chunk objects
            embeddings: Dict mapping chunk_id -> embedding vector
            embedding_model: Name of embedding model used

        Returns:
            Dictionary with write statistics
        """
        if not chunks:
            logger.warning("No chunks to write")
            return {"total_chunks": 0, "file_size_bytes": 0}

        embeddings = embeddings or {}

        # Convert chunks to records
        records = []
        for chunk in chunks:
            record = self._chunk_to_record(
                chunk, embeddings.get(chunk.chunk_id), embedding_model
            )
            records.append(record)

        # Create DataFrame
        df = pd.DataFrame(records)

        # Convert to PyArrow Table with schema
        table = pa.Table.from_pandas(df, schema=self.SCHEMA)

        # Write to Parquet
        pq.write_table(
            table,
            self.output_path,
            compression=self.compression,
            use_dictionary=True,
            write_statistics=True,
        )

        # Compute statistics
        file_size = self.output_path.stat().st_size
        checksum = self._compute_checksum()

        stats = {
            "total_chunks": len(chunks),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "compression": self.compression,
            "checksum_sha256": checksum,
            "output_path": str(self.output_path),
        }

        logger.info(
            f"✅ Wrote {len(chunks)} chunks to Parquet ({stats['file_size_mb']} MB)"
        )
        return stats

    def _chunk_to_record(
        self, chunk: Chunk, embedding: Optional[List[float]], embedding_model: str
    ) -> Dict[str, Any]:
        """
        Convert Chunk to Parquet record.
        """
        now = datetime.utcnow()

        # Serialize bbox to JSON string if present
        bbox_data = None
        if chunk.metadata.get("bbox"):
            bbox_data = json.dumps(chunk.metadata["bbox"])

        record = {
            # Identifiers
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "page": chunk.page,
            "chunk_index": chunk.chunk_index,
            # Content
            "text": chunk.text,
            "content_hash": chunk.content_hash,
            # Chunking metadata
            "chunk_type": chunk.chunk_type.value
            if hasattr(chunk.chunk_type, "value")
            else str(chunk.chunk_type),
            "token_count": chunk.token_count,
            "char_count": len(chunk.text),
            # Embeddings
            "embedding": embedding,
            "embedding_model": embedding_model if embedding else None,
            "embedding_timestamp": now if embedding else None,
            # P&ID specific
            "equipment_tags": chunk.equipment_tags if chunk.equipment_tags else None,
            "bbox_data": bbox_data,
            # Headers/structure
            "headers": chunk.headers if chunk.headers else None,
            "section_header": chunk.metadata.get("section_header"),
            # Provenance
            "created_at": now,
            "ingestion_version": self.ingestion_version,
        }

        return record

    def _compute_checksum(self) -> str:
        """
        Compute SHA256 checksum of Parquet file.
        """
        sha256 = hashlib.sha256()
        with open(self.output_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def read_chunks(parquet_path: Path) -> pd.DataFrame:
        """
        Read chunks from Parquet file.

        Args:
            parquet_path: Path to Parquet file

        Returns:
            DataFrame with chunks
        """
        return pd.read_parquet(parquet_path)

    @staticmethod
    def get_file_metadata(parquet_path: Path) -> Dict[str, Any]:
        """
        Get metadata from Parquet file.

        Args:
            parquet_path: Path to Parquet file

        Returns:
            Dictionary with file metadata
        """
        parquet_file = pq.ParquetFile(parquet_path)

        metadata = {
            "num_rows": parquet_file.metadata.num_rows,
            "num_columns": parquet_file.metadata.num_columns,
            "num_row_groups": parquet_file.metadata.num_row_groups,
            "serialized_size": parquet_file.metadata.serialized_size,
            "format_version": parquet_file.metadata.format_version,
            "created_by": parquet_file.metadata.created_by,
        }

        return metadata


class IncrementalParquetWriter(ParquetWriter):
    """
    Extends ParquetWriter to support incremental writes with append mode.
    """

    def append_chunks(
        self,
        chunks: List[Chunk],
        embeddings: Optional[Dict[str, List[float]]] = None,
        embedding_model: str = "gemini-embedding-001",
    ) -> Dict[str, Any]:
        """
        Append chunks to existing Parquet file.

        Args:
            chunks: New chunks to append
            embeddings: Embeddings for new chunks
            embedding_model: Embedding model name

        Returns:
            Write statistics
        """
        # Check if file exists
        if not self.output_path.exists():
            logger.info("No existing file, creating new one")
            return self.write_chunks(chunks, embeddings, embedding_model)

        # Read existing chunks
        existing_df = pd.read_parquet(self.output_path)
        logger.info(f"Loaded {len(existing_df)} existing chunks")

        # Convert new chunks to records
        embeddings = embeddings or {}
        new_records = []
        for chunk in chunks:
            record = self._chunk_to_record(
                chunk, embeddings.get(chunk.chunk_id), embedding_model
            )
            new_records.append(record)

        new_df = pd.DataFrame(new_records)

        # Concatenate
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)

        # Write back
        table = pa.Table.from_pandas(combined_df, schema=self.SCHEMA)
        pq.write_table(
            table,
            self.output_path,
            compression=self.compression,
            use_dictionary=True,
            write_statistics=True,
        )

        file_size = self.output_path.stat().st_size
        checksum = self._compute_checksum()

        stats = {
            "total_chunks": len(combined_df),
            "new_chunks": len(chunks),
            "existing_chunks": len(existing_df),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "compression": self.compression,
            "checksum_sha256": checksum,
            "output_path": str(self.output_path),
        }

        logger.info(f"✅ Appended {len(chunks)} chunks (total: {len(combined_df)})")
        return stats


if __name__ == "__main__":
    # Quick sanity test
    logging.basicConfig(level=logging.INFO)

    from app.ingestion.chunkers.base import Chunk

    # Create test chunk
    test_chunk = Chunk(
        chunk_id="test_001",
        doc_id="doc_001",
        text="This is a test chunk for Parquet storage.",
        chunk_type="text",
        page=1,
        chunk_index=0,
        token_count=10,
        content_hash="abc123",
        equipment_tags=["P-101"],
        headers=["Section 1"],
        metadata={"section_header": "Introduction"},
    )

    # Test embedding
    test_embedding = [0.1] * 768

    # Write to Parquet
    output_path = Path("artifacts/test_parquet/test_chunks.parquet")
    writer = ParquetWriter(output_path, ingestion_version="test_v1")

    stats = writer.write_chunks([test_chunk], embeddings={"test_001": test_embedding})

    print("\n📊 Write Statistics:")
    print(json.dumps(stats, indent=2))

    # Read back
    df = ParquetWriter.read_chunks(output_path)
    print(f"\n✅ Read back {len(df)} chunks")
    print(df[["chunk_id", "doc_id", "text", "token_count"]].to_string())

    # Get metadata
    metadata = ParquetWriter.get_file_metadata(output_path)
    print("\n📋 File Metadata:")
    print(json.dumps(metadata, indent=2))
