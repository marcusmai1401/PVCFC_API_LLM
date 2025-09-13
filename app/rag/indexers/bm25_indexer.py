"""
BM25 Indexer
Offline text search using BM25 algorithm
"""
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import pickle
from rank_bm25 import BM25Okapi
from loguru import logger
import numpy as np


class BM25Indexer:
    """
    BM25-based text search indexer (offline, no API needed)
    """
    
    def __init__(self,
                 k1: float = 1.2,
                 b: float = 0.75,
                 epsilon: float = 0.25):
        """
        Initialize BM25 indexer
        
        Args:
            k1: BM25 k1 parameter (term frequency saturation)
            b: BM25 b parameter (length normalization)
            epsilon: Floor value for IDF
        """
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon
        self.index = None
        self.documents = []
        self.metadata = []
        self.tokenized_docs = []
    
    def build_index(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Build BM25 index from chunks
        
        Args:
            chunks: List of chunk dictionaries
        """
        self.documents = []
        self.metadata = []
        self.tokenized_docs = []
        
        for chunk in chunks:
            # Extract text
            text = chunk.get('text', '')
            self.documents.append(text)
            
            # Store metadata
            meta = {
                'chunk_id': chunk.get('chunk_id'),
                'doc_id': chunk.get('doc_id'),
                'page_start': chunk.get('page_start'),
                'page_end': chunk.get('page_end'),
                'heading': chunk.get('heading'),
                'level': chunk.get('level')
            }
            self.metadata.append(meta)
            
            # Tokenize
            tokens = self._tokenize(text)
            self.tokenized_docs.append(tokens)
        
        # Build BM25 index
        self.index = BM25Okapi(
            self.tokenized_docs,
            k1=self.k1,
            b=self.b,
            epsilon=self.epsilon
        )
        
        logger.info(f"Built BM25 index with {len(self.documents)} documents")
    
    def search(self, 
              query: str, 
              top_k: int = 5,
              min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        Search documents using BM25
        
        Args:
            query: Search query
            top_k: Number of results to return
            min_score: Minimum score threshold
            
        Returns:
            List of search results with scores
        """
        if not self.index:
            logger.warning("Index not built yet")
            return []
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        
        # Get BM25 scores
        scores = self.index.get_scores(query_tokens)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        # Build results
        results = []
        for idx in top_indices:
            score = scores[idx]
            if score < min_score:
                continue
                
            result = {
                'text': self.documents[idx],
                'score': float(score),
                'metadata': self.metadata[idx],
                'rank': len(results) + 1
            }
            results.append(result)
        
        return results
    
    def batch_search(self, 
                    queries: List[str],
                    top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search multiple queries
        
        Args:
            queries: List of search queries
            top_k: Number of results per query
            
        Returns:
            Dictionary mapping queries to results
        """
        results = {}
        for query in queries:
            results[query] = self.search(query, top_k)
        return results
    
    def save_index(self, index_dir: str | Path) -> None:
        """
        Save index to disk
        
        Args:
            index_dir: Directory to save index
        """
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)
        
        # Save BM25 index
        with open(index_dir / "bm25_index.pkl", "wb") as f:
            pickle.dump(self.index, f)
        
        # Save documents
        with open(index_dir / "documents.json", "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)
        
        # Save metadata
        with open(index_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        
        # Save tokenized docs
        with open(index_dir / "tokenized_docs.pkl", "wb") as f:
            pickle.dump(self.tokenized_docs, f)
        
        # Save config
        config = {
            'k1': self.k1,
            'b': self.b,
            'epsilon': self.epsilon,
            'num_documents': len(self.documents)
        }
        with open(index_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Saved index to {index_dir}")
    
    def load_index(self, index_dir: str | Path) -> None:
        """
        Load index from disk
        
        Args:
            index_dir: Directory containing saved index
        """
        index_dir = Path(index_dir)
        
        # Load BM25 index
        with open(index_dir / "bm25_index.pkl", "rb") as f:
            self.index = pickle.load(f)
        
        # Load documents
        with open(index_dir / "documents.json", "r", encoding="utf-8") as f:
            self.documents = json.load(f)
        
        # Load metadata
        with open(index_dir / "metadata.json", "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        
        # Load tokenized docs
        with open(index_dir / "tokenized_docs.pkl", "rb") as f:
            self.tokenized_docs = pickle.load(f)
        
        # Load config
        with open(index_dir / "config.json", "r") as f:
            config = json.load(f)
            self.k1 = config['k1']
            self.b = config['b']
            self.epsilon = config['epsilon']
        
        logger.info(f"Loaded index from {index_dir} ({len(self.documents)} documents)")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization (can be enhanced)
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # Convert to lowercase
        text = text.lower()
        
        # Simple word tokenization
        import re
        tokens = re.findall(r'\b\w+\b', text)
        
        # Remove short tokens
        tokens = [t for t in tokens if len(t) > 2]
        
        return tokens
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get index statistics
        
        Returns:
            Statistics dictionary
        """
        if not self.documents:
            return {'status': 'empty'}
        
        doc_lengths = [len(doc) for doc in self.tokenized_docs]
        
        return {
            'num_documents': len(self.documents),
            'avg_doc_length': np.mean(doc_lengths),
            'min_doc_length': min(doc_lengths),
            'max_doc_length': max(doc_lengths),
            'total_tokens': sum(doc_lengths),
            'unique_tokens': len(set(token for doc in self.tokenized_docs for token in doc))
        }
    
    def rerank(self, 
              results: List[Dict[str, Any]],
              query: str) -> List[Dict[str, Any]]:
        """
        Rerank results (placeholder for more sophisticated reranking)
        
        Args:
            results: Initial search results
            query: Original query
            
        Returns:
            Reranked results
        """
        # For now, just return as-is
        # Could implement cross-encoder reranking later
        return results
