"""
Centralized Configuration for Pipeline

This module contains all configuration parameters for:
- Text extraction (PDF processing)
- OCR settings
- BM25 indexing
- Page reranking
- Artifact paths

Usage:
    from app.config import PipelineConfig

    config = PipelineConfig()
    min_length = config.MIN_TEXT_LENGTH
    artifacts_dir = config.ARTIFACTS_DIR
"""

import os
from pathlib import Path
from typing import Optional


class PipelineConfig:
    """
    Centralized configuration for the entire ingestion and RAG pipeline.

    All modules should read configuration from this class to ensure consistency.
    Configuration can be overridden via environment variables.
    """

    # ============================================================================
    # PROJECT PATHS
    # ============================================================================

    # Project root directory
    PROJECT_ROOT = Path(__file__).parent.parent.parent

    # Artifacts directory (can be overridden via env var)
    ARTIFACTS_DIR = Path(
        os.environ.get(
            "ARTIFACTS_DIR", str(PROJECT_ROOT / "artifacts" / "ingestion_production")
        )
    )

    # Input documents directory
    DOCUMENTS_DIR = Path(
        os.environ.get("DOCUMENTS_DIR", str(PROJECT_ROOT / "documents"))
    )

    # ============================================================================
    # PID TAGS & CAD-LIKE EXTRACTION PATHS
    # ============================================================================

    # Page layout artifacts (vector drawings + text spans per page)
    LAYOUT_DIR = Path(os.environ.get("LAYOUT_DIR", str(ARTIFACTS_DIR / "page_layout")))

    # Tag entities artifacts (tags.jsonl, relations.jsonl)
    ENTITIES_DIR = Path(os.environ.get("ENTITIES_DIR", str(ARTIFACTS_DIR / "entities")))

    # Bbox crops (PNG images of extracted tags)
    CROPS_DIR = Path(os.environ.get("CROPS_DIR", str(ARTIFACTS_DIR / "crops")))

    # Telemetry logs (runtime metrics per file)
    LOGS_DIR = Path(os.environ.get("LOGS_DIR", str(ARTIFACTS_DIR / "logs")))

    # ============================================================================
    # TEXT EXTRACTION & OCR THRESHOLDS
    # ============================================================================

    # Minimum text length to consider a page valid (chars)
    MIN_TEXT_LENGTH = int(os.environ.get("MIN_TEXT_LENGTH", "10"))

    # Threshold to trigger OCR if extracted text is below this (chars)
    OCR_TRIGGER_THRESHOLD = int(os.environ.get("OCR_TRIGGER_THRESHOLD", "40"))

    # Minimum OCR confidence to accept results (0.0 - 1.0)
    OCR_MIN_CONFIDENCE = float(os.environ.get("OCR_MIN_CONFIDENCE", "0.3"))

    # Maximum pages to extract per document (0 = no limit)
    MAX_PAGES_PER_DOC = int(os.environ.get("MAX_PAGES_PER_DOC", "0"))

    # ============================================================================
    # OCR MODEL CONFIGURATION
    # ============================================================================

    # PaddleOCR detection model directory (local model)
    DET_MODEL_DIR = Path(
        os.environ.get(
            "DET_MODEL_DIR",
            str(
                PROJECT_ROOT
                / "artifacts"
                / "ocr"
                / "paddle"
                / "ppocrv5"
                / "det"
                / "PP-OCRv5_server_det_infer"
            ),
        )
    )

    # PaddleOCR classifier model directory (local model)
    CLS_MODEL_DIR = Path(
        os.environ.get(
            "CLS_MODEL_DIR",
            str(
                PROJECT_ROOT
                / "artifacts"
                / "ocr"
                / "paddle"
                / "ppocrv5"
                / "cls"
                / "ch_ppocr_mobile_v2.0_cls_infer"
            ),
        )
    )

    # PaddleOCR recognition model directory
    # If None, will auto-download official English model
    # After first download, set this to the cached path for offline use

    # Cached English rec model path (auto-downloaded by PaddleOCR)
    _REC_MODEL_CACHED = (
        Path.home() / ".paddleocr" / "whl" / "rec" / "en" / "en_PP-OCRv4_rec_infer"
    )

    REC_MODEL_DIR: Optional[Path] = None
    _rec_model_env = os.environ.get("REC_MODEL_DIR")
    if _rec_model_env:
        REC_MODEL_DIR = Path(_rec_model_env)
    elif _REC_MODEL_CACHED.exists():
        # Use cached model if available (offline-friendly)
        REC_MODEL_DIR = _REC_MODEL_CACHED

    # Language for OCR (used when REC_MODEL_DIR is None)
    OCR_LANG = os.environ.get("OCR_LANG", "en")

    # PaddleOCR detection algorithm
    DET_ALGORITHM = os.environ.get("DET_ALGORITHM", "DB")

    # PaddleOCR recognition algorithm
    REC_ALGORITHM = os.environ.get("REC_ALGORITHM", "SVTR_LCNet")

    # Use GPU for OCR (True/False)
    USE_GPU = os.environ.get("USE_GPU", "False").lower() == "true"

    # Show OCR debug logs
    SHOW_OCR_LOG = os.environ.get("SHOW_OCR_LOG", "False").lower() == "true"

    # ============================================================================
    # BM25 INDEXING CONFIGURATION
    # ============================================================================

    # BM25 k1 parameter (term frequency saturation)
    BM25_K1 = float(os.environ.get("BM25_K1", "1.5"))

    # BM25 b parameter (length normalization)
    BM25_B = float(os.environ.get("BM25_B", "0.75"))

    # BM25 epsilon parameter (IDF floor)
    BM25_EPSILON = float(os.environ.get("BM25_EPSILON", "0.25"))

    # ============================================================================
    # PAGE RERANKING CONFIGURATION
    # ============================================================================

    # Default number of top pages to return per document
    DEFAULT_TOP_K_PAGES = int(os.environ.get("DEFAULT_TOP_K_PAGES", "5"))

    # Minimum BM25 score threshold for page ranking
    PAGE_MIN_SCORE = float(os.environ.get("PAGE_MIN_SCORE", "0.0"))

    # ============================================================================
    # SNIPPET EXTRACTION CONFIGURATION
    # ============================================================================

    # Context window size for snippet extraction (chars)
    SNIPPET_CONTEXT_SIZE = int(os.environ.get("SNIPPET_CONTEXT_SIZE", "200"))

    # Maximum number of snippets per page
    MAX_SNIPPETS_PER_PAGE = int(os.environ.get("MAX_SNIPPETS_PER_PAGE", "3"))

    # ============================================================================
    # SEMANTIC PAGE RERANKING CONFIGURATION
    # ============================================================================

    # Enable hybrid BM25 + semantic scoring when embeddings are available
    ENABLE_PAGE_SEMANTIC = (
        os.environ.get("ENABLE_PAGE_SEMANTIC", "true").lower() == "true"
    )

    # Weights for hybrid fusion: final = w_bm25 * bm25_norm + w_sem * sem_norm
    PAGE_HYBRID_W_BM25 = float(os.environ.get("PAGE_HYBRID_W_BM25", "0.6"))
    PAGE_HYBRID_W_SEM = float(os.environ.get("PAGE_HYBRID_W_SEM", "0.4"))

    # Maximum characters to embed per page (to bound embedding cost)
    PAGE_EMBED_MAX_CHARS = int(os.environ.get("PAGE_EMBED_MAX_CHARS", "8000"))

    # ============================================================================
    # PAGE RANK CACHING CONFIGURATION
    # ============================================================================

    # Enable page rank result caching
    ENABLE_PAGE_RANK_CACHE = (
        os.environ.get("ENABLE_PAGE_RANK_CACHE", "true").lower() == "true"
    )

    # Maximum number of cached page rank results (LRU eviction)
    PAGE_RANK_CACHE_SIZE = int(os.environ.get("PAGE_RANK_CACHE_SIZE", "1024"))

    # Cache TTL in seconds (0 = no expiry)
    PAGE_RANK_CACHE_TTL = int(
        os.environ.get("PAGE_RANK_CACHE_TTL", "1800")
    )  # 30 minutes

    # Enable query embedding caching (for semantic scoring)
    ENABLE_QUERY_EMBED_CACHE = (
        os.environ.get("ENABLE_QUERY_EMBED_CACHE", "true").lower() == "true"
    )

    # Maximum number of cached query embeddings
    QUERY_EMBED_CACHE_SIZE = int(os.environ.get("QUERY_EMBED_CACHE_SIZE", "512"))

    # ============================================================================
    # ARTIFACT FILE PATHS
    # ============================================================================

    @property
    def page_bm25_index_path(self) -> Path:
        """Path to BM25 page index pickle file"""
        return self.ARTIFACTS_DIR / "page_bm25_index.pkl"

    @property
    def text_by_page_path(self) -> Path:
        """Path to text_by_page.jsonl file"""
        return self.ARTIFACTS_DIR / "text_by_page.jsonl"

    @property
    def page_embeddings_path(self) -> Path:
        """Path to page_embeddings NPZ file"""
        return self.ARTIFACTS_DIR / "page_embeddings.npz"

    @property
    def page_metadata_path(self) -> Path:
        """Path to page_metadata.json file"""
        return self.ARTIFACTS_DIR / "page_metadata.json"

    @property
    def doc_metadata_path(self) -> Path:
        """Path to doc_metadata.json file"""
        return self.ARTIFACTS_DIR / "doc_metadata.json"

    # ============================================================================
    # PID TAGS & CAD-LIKE EXTRACTION CONFIGURATION
    # ============================================================================

    # Enable PID tags extraction pipeline
    ENABLE_PID_TAGS = os.environ.get("ENABLE_PID_TAGS", "false").lower() == "true"

    # Gate mode: auto (use scorer), always (force enable), never (disable)
    GATE_MODE = os.environ.get("GATE_MODE", "auto")

    # CAD-like gate threshold
    GATE_THRESHOLD = float(os.environ.get("GATE_THRESHOLD", "0.60"))

    # Gray zone threshold
    GRAY_ZONE_LOW = float(os.environ.get("GRAY_ZONE_LOW", "0.45"))

    # Tag extraction pass threshold
    TAG_PASS_THRESHOLD = float(os.environ.get("TAG_PASS_THRESHOLD", "6.0"))

    # Suffix radius (em units)
    SUFFIX_RADIUS_EM = float(os.environ.get("SUFFIX_RADIUS_EM", "1.0"))

    # Taggy page selection thresholds
    TAGGY_MIN_REGEX_HITS = int(os.environ.get("TAGGY_MIN_REGEX_HITS", "3"))
    TAGGY_MIN_CODE_TOKENS = int(os.environ.get("TAGGY_MIN_CODE_TOKENS", "4"))

    # OpenSearch tags index name
    TAGS_INDEX_NAME = os.environ.get("TAGS_INDEX_NAME", "pvcfc_pid_tags")

    # Enable shape-aware ROI (requires OpenCV)
    ENABLE_SHAPE_AWARE_ROI = (
        os.environ.get("ENABLE_SHAPE_AWARE_ROI", "false").lower() == "true"
    )

    # Lazy crop generation (only generate on query demand)
    LAZY_CROP_GENERATION = (
        os.environ.get("LAZY_CROP_GENERATION", "true").lower() == "true"
    )

    # Config file paths
    CADLIKE_GATE_CONFIG = Path(
        os.environ.get(
            "CADLIKE_GATE_CONFIG", str(PROJECT_ROOT / "config" / "cadlike_gate.yaml")
        )
    )
    TAG_GRAMMAR_CONFIG = Path(
        os.environ.get(
            "TAG_GRAMMAR_CONFIG", str(PROJECT_ROOT / "config" / "tag_grammar.yaml")
        )
    )
    PAGE_FILTERS_CONFIG = Path(
        os.environ.get(
            "PAGE_FILTERS_CONFIG", str(PROJECT_ROOT / "config" / "page_filters.yaml")
        )
    )
    TAGS_INDEX_MAPPING_CONFIG = Path(
        os.environ.get(
            "TAGS_INDEX_MAPPING_CONFIG",
            str(PROJECT_ROOT / "config" / "tags_index_mapping.json"),
        )
    )

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def ensure_artifacts_dir(self):
        """Create artifacts directory if it doesn't exist"""
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    def ensure_pid_tags_dirs(self):
        """Create PID tags-specific directories if they don't exist"""
        self.LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
        self.ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
        self.CROPS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def get_ocr_config(self) -> dict:
        """
        Get OCR configuration as dictionary for PaddleOCR initialization

        Returns:
            Dictionary with OCR config parameters
        """
        config = {
            "use_angle_cls": True,
            "det_algorithm": self.DET_ALGORITHM,
            "rec_algorithm": self.REC_ALGORITHM,
            "use_gpu": self.USE_GPU,
            "show_log": self.SHOW_OCR_LOG,
        }

        # Add model directories
        if self.DET_MODEL_DIR.exists():
            config["det_model_dir"] = str(self.DET_MODEL_DIR)

        if self.CLS_MODEL_DIR.exists():
            config["cls_model_dir"] = str(self.CLS_MODEL_DIR)

        # Handle rec model
        if self.REC_MODEL_DIR is not None and self.REC_MODEL_DIR.exists():
            # Use cached or custom rec model
            config["rec_model_dir"] = str(self.REC_MODEL_DIR)
            config["lang"] = self.OCR_LANG  # Still need lang for other components
        else:
            # Will auto-download official model
            config["rec_model_dir"] = None
            config["lang"] = self.OCR_LANG

        return config

    def validate(self) -> bool:
        """
        Validate configuration

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        # Check thresholds
        if self.MIN_TEXT_LENGTH < 0:
            raise ValueError("MIN_TEXT_LENGTH must be >= 0")

        if self.OCR_TRIGGER_THRESHOLD < 0:
            raise ValueError("OCR_TRIGGER_THRESHOLD must be >= 0")

        if not (0.0 <= self.OCR_MIN_CONFIDENCE <= 1.0):
            raise ValueError("OCR_MIN_CONFIDENCE must be between 0.0 and 1.0")

        if self.BM25_K1 <= 0:
            raise ValueError("BM25_K1 must be > 0")

        if not (0.0 <= self.BM25_B <= 1.0):
            raise ValueError("BM25_B must be between 0.0 and 1.0")

        # Check paths exist (det and cls models must exist)
        if not self.DET_MODEL_DIR.exists():
            raise ValueError(f"Detection model not found: {self.DET_MODEL_DIR}")

        if not self.CLS_MODEL_DIR.exists():
            raise ValueError(f"Classifier model not found: {self.CLS_MODEL_DIR}")

        return True

    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"PipelineConfig(\n"
            f"  MIN_TEXT_LENGTH={self.MIN_TEXT_LENGTH},\n"
            f"  OCR_TRIGGER_THRESHOLD={self.OCR_TRIGGER_THRESHOLD},\n"
            f"  OCR_MIN_CONFIDENCE={self.OCR_MIN_CONFIDENCE},\n"
            f"  BM25_K1={self.BM25_K1}, BM25_B={self.BM25_B},\n"
            f"  ARTIFACTS_DIR={self.ARTIFACTS_DIR}\n"
            f")"
        )


# Singleton instance
_config_instance: Optional[PipelineConfig] = None


def get_config() -> PipelineConfig:
    """
    Get singleton PipelineConfig instance

    Returns:
        PipelineConfig instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = PipelineConfig()
        # Validate on first load
        _config_instance.validate()

    return _config_instance
