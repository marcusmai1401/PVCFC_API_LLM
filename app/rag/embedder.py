"""
Text embedder module for generating embeddings
"""
import logging
from typing import List, Optional, Union

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class TextEmbedder:
    """
    Text embedder for generating document embeddings
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        """
        Initialize text embedder

        Args:
            model_name: Name of the sentence transformer model
            device: Device to use (cpu/cuda)
        """
        self.model_name = model_name

        # Determine device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Load model
        try:
            self.model = SentenceTransformer(model_name, device=self.device)
            logger.info(f"Loaded embedding model: {model_name} on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}")
            raise

    def embed(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Generate embeddings for texts

        Args:
            texts: Text or list of texts to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            Numpy array of embeddings
        """
        # Handle single text
        if isinstance(texts, str):
            texts = [texts]

        try:
            # Generate embeddings
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )

            logger.debug(f"Generated embeddings for {len(texts)} texts")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a single query

        Args:
            query: Query text

        Returns:
            Query embedding as numpy array
        """
        return self.embed(query, show_progress=False)[0]

    def embed_documents(
        self, documents: List[str], batch_size: int = 32, show_progress: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for multiple documents

        Args:
            documents: List of document texts
            batch_size: Batch size for encoding
            show_progress: Whether to show progress

        Returns:
            Document embeddings as numpy array
        """
        return self.embed(documents, batch_size=batch_size, show_progress=show_progress)

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score
        """
        # Normalize embeddings
        norm1 = embedding1 / np.linalg.norm(embedding1)
        norm2 = embedding2 / np.linalg.norm(embedding2)

        # Calculate cosine similarity
        return float(np.dot(norm1, norm2))

    def get_model_info(self) -> dict:
        """
        Get information about the embedding model

        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimension": self.model.get_sentence_embedding_dimension(),
            "max_sequence_length": self.model.max_seq_length,
        }


# Export class
__all__ = ["TextEmbedder"]
