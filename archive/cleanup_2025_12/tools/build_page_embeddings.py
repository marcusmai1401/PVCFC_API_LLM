"""
Build Page Embeddings - Phase 1 Semantic Ranking

Generates page-level embeddings aligned with the BM25 page index.
Outputs a compressed NPZ file containing:
- embeddings: float32 array of shape (N_pages, D)
- doc_ids: list[str] length N_pages
- pages: int array length N_pages

Usage:
  python tools/build_page_embeddings.py --provider local --model BAAI/bge-small-en-v1.5
  python tools/build_page_embeddings.py --help
"""

import argparse
import json
import pickle

# Ensure project root is on sys.path when running as a script
import sys
from pathlib import Path
from pathlib import Path as _Path
from typing import Dict, List, Tuple

import jsonlines
import numpy as np
from loguru import logger

try:
    _PROJECT_ROOT = _Path(__file__).resolve().parents[1]
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))
except Exception as _e:
    logger.debug(f"Failed to set project root on sys.path: {_e}")

# Import config and services
try:
    from app.config import get_config

    CONFIG = get_config()
except Exception as e:
    CONFIG = None
    logger.warning(f"Config not available: {e}")

try:
    from app.services.embedding_enhanced import UniversalEmbeddingService
except Exception as e:
    logger.error(f"Embedding service not available: {e}")
    raise

try:
    from app.utils.text_processing import clean_text_for_snippet

    CLEAN_AVAILABLE = True
except Exception:
    CLEAN_AVAILABLE = False


def _load_bm25_order(index_path: Path) -> Tuple[List[str], List[int]]:
    """Load doc_ids and pages arrays from BM25 index for ordering"""
    if not index_path.exists():
        raise FileNotFoundError(f"BM25 index not found: {index_path}")
    with open(index_path, "rb") as f:
        data = pickle.load(f)
    return data["doc_ids"], data["pages"]


def _load_text_by_page(text_path: Path) -> Dict[Tuple[str, int], str]:
    """Load text_by_page.jsonl to a dict keyed by (doc_id, page)"""
    if not text_path.exists():
        raise FileNotFoundError(f"text_by_page.jsonl not found: {text_path}")
    mapping: Dict[Tuple[str, int], str] = {}
    with jsonlines.open(text_path) as reader:
        for obj in reader:
            doc_id = obj["doc_id"]
            page = int(obj["page"])  # ensure int
            text = obj.get("text", "") or ""
            mapping[(doc_id, page)] = text
    return mapping


def _prepare_texts(
    order_doc_ids: List[str],
    order_pages: List[int],
    text_map: Dict[Tuple[str, int], str],
    max_chars: int,
) -> List[str]:
    """Prepare texts aligned with BM25 order, cleaned and truncated."""
    texts: List[str] = []
    missing = 0
    for doc_id, page in zip(order_doc_ids, order_pages):
        text = text_map.get((doc_id, int(page)), "")
        if CLEAN_AVAILABLE:
            text = clean_text_for_snippet(text)
        if len(text) > max_chars:
            text = text[:max_chars]
        if not text:
            missing += 1
        texts.append(text)
    if missing:
        logger.warning(f"{missing} pages had empty text (after cleaning)")
    return texts


def build_embeddings(
    provider: str, model: str, batch_size: int, out_path: Path
) -> Path:
    """Build page embeddings and save to NPZ file"""
    # Resolve paths from config or defaults
    artifacts_dir = (
        CONFIG.ARTIFACTS_DIR if CONFIG else Path("artifacts/ingestion_production")
    )
    page_index_path = (
        CONFIG.page_bm25_index_path if CONFIG else artifacts_dir / "page_bm25_index.pkl"
    )
    text_by_page_path = (
        CONFIG.text_by_page_path if CONFIG else artifacts_dir / "text_by_page.jsonl"
    )

    logger.info(f"Loading BM25 ordering from {page_index_path}")
    doc_ids, pages = _load_bm25_order(page_index_path)

    logger.info(f"Loading text_by_page from {text_by_page_path}")
    text_map = _load_text_by_page(text_by_page_path)

    logger.info("Preparing texts for embedding (aligned with BM25 order)")
    max_chars = CONFIG.PAGE_EMBED_MAX_CHARS if CONFIG else 8000
    texts = _prepare_texts(doc_ids, pages, text_map, max_chars=max_chars)

    logger.info(f"Total pages to embed: {len(texts)}")

    # Initialize embedding service
    service = UniversalEmbeddingService(provider=provider, model_name=model)

    # Compute embeddings in batches
    embeddings = service.embed_texts(texts, batch_size=batch_size)
    if not isinstance(embeddings, np.ndarray):
        embeddings = np.asarray(embeddings, dtype=np.float32)

    # Verify dimensions
    dim = embeddings.shape[1]
    logger.info(f"Embeddings generated: shape={embeddings.shape}")

    # Save as NPZ (compressed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(out_path),
        embeddings=embeddings.astype(np.float32, copy=False),
        doc_ids=np.array(doc_ids, dtype=object),
        pages=np.array(pages, dtype=np.int32),
        dim=np.int32(dim),
        provider=np.array([provider], dtype=object),
        model=np.array([model], dtype=object),
    )
    logger.info(f"✅ Page embeddings saved to {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Build page embeddings aligned with BM25 index",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        default="local",
        choices=["local", "gemini"],
        help="Embedding provider",
    )
    parser.add_argument(
        "--model", default="BAAI/bge-small-en-v1.5", help="Embedding model name"
    )
    parser.add_argument(
        "--batch-size", type=int, default=64, help="Batch size for embedding"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output NPZ path (default: config.page_embeddings_path)",
    )

    args = parser.parse_args()

    out_path = (
        Path(args.output)
        if args.output
        else (
            CONFIG.page_embeddings_path
            if CONFIG
            else Path("artifacts/ingestion_production/page_embeddings.npz")
        )
    )

    try:
        build_embeddings(args.provider, args.model, args.batch_size, out_path)
    except Exception as e:
        logger.error(f"Failed to build embeddings: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
