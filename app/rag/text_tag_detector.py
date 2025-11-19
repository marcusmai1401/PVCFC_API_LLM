"""Text-based P&ID tag detector using page-level extracted text.

This module provides a fallback mechanism for CAD-like tag search when
spatial component clustering (unit/prefix/suffix from pvcfc_pid_spatial_components)
misses tags due to incomplete indexing or OCR quirks.

It operates purely on text_by_page.jsonl and does NOT require bbox/layout.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from loguru import logger

try:
    from app.config import PipelineConfig, get_config  # type: ignore
except Exception:  # pragma: no cover - during tooling/import edge cases
    get_config = None
    PipelineConfig = None  # type: ignore

try:
    import jsonlines
except Exception:  # pragma: no cover - jsonlines should be installed
    jsonlines = None  # type: ignore


@dataclass
class Token:
    """Simple token with span offsets in normalized page text."""

    text: str
    start: int
    end: int


@dataclass
class TagTextHit:
    """Text-based tag detection hit on a specific page."""

    doc_id: str
    page: int
    score: float
    span_start: int
    span_end: int
    context: str


class TextTagDetector:
    """Detect P&ID-like tags from page text only.

    This is designed as a fallback for CAD-like tag search when spatial
    components are incomplete. It searches text_by_page.jsonl for occurrences
    of (unit, prefix, suffix) within a small token window and assigns a
    proximity-based score.
    """

    def __init__(self, cfg: Optional[PipelineConfig] = None, max_docs_cache: int = 16):
        if get_config is not None and cfg is None:
            try:
                cfg = get_config()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"TextTagDetector: get_config() failed: {e}")
                cfg = None

        self.cfg = cfg
        self._doc_pages_cache: Dict[str, List[Dict]] = {}
        self._max_docs_cache = max_docs_cache

        # Resolve text_by_page path
        self.text_by_page_path = None
        if self.cfg is not None and hasattr(self.cfg, "text_by_page_path"):
            self.text_by_page_path = self.cfg.text_by_page_path
        else:
            # Fallback to common default used by PageReranker
            from pathlib import Path

            self.text_by_page_path = Path(
                "artifacts/ingestion_production/text_by_page.jsonl"
            )

        logger.info(
            f"TextTagDetector initialized with text_by_page={self.text_by_page_path}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def find_tag_hits(
        self,
        doc_id: str,
        unit: str,
        prefix: str,
        suffix: str,
        max_gap_tokens: int = 5,
    ) -> List[TagTextHit]:
        """Find pages containing the given tag components.

        Args:
            doc_id: Document ID in text_by_page.jsonl
            unit: Unit number component (e.g., "04", "29")
            prefix: Tag prefix (e.g., "TI", "PI", "MYLK")
            suffix: Numeric/alpha suffix (e.g., "3201", "2202A")
            max_gap_tokens: Maximum token distance between unit/prefix/suffix

        Returns:
            Sorted list of TagTextHit (highest score first)
        """
        if not doc_id:
            logger.debug("TextTagDetector.find_tag_hits called with empty doc_id")
            return []

        rows = self._get_doc_pages(doc_id)
        if not rows:
            return []

        unit_n = self._normalize_component(unit)
        prefix_n = self._normalize_component(prefix)
        suffix_n = self._normalize_component(suffix)

        hits: List[TagTextHit] = []

        for row in rows:
            page = row.get("page")
            raw_text = (row.get("text") or "") if isinstance(row, dict) else ""
            if not raw_text:
                continue

            norm_text = self._normalize_text(raw_text)
            tokens = self._tokenize(norm_text)

            # Primary pattern: unit -> prefix -> suffix within a tight token window
            page_hits = self._find_hits_in_tokens(
                tokens, unit_n, prefix_n, suffix_n, max_gap_tokens
            )

            # Secondary pattern: full-tag window around prefix token (for box-style tags
            # such as "04 MXAK 04204" where the actual text order may be
            # "04204 MXAK 04 ..."). This only adds hits when all three components
            # appear within a small window around the prefix, regardless of order.
            page_hits.extend(
                self._find_full_tag_window_hits(
                    tokens, unit_n, prefix_n, suffix_n, window_tokens=max_gap_tokens
                )
            )

            for span_start, span_end, score in page_hits:
                context = norm_text[max(0, span_start - 40) : span_end + 40]
                hits.append(
                    TagTextHit(
                        doc_id=doc_id,
                        page=int(page) if page is not None else -1,
                        score=float(score),
                        span_start=int(span_start),
                        span_end=int(span_end),
                        context=context,
                    )
                )

        # Sort by score (desc), then by page
        hits.sort(key=lambda h: (-h.score, h.page))
        logger.info(
            f"TextTagDetector: found {len(hits)} text hits for tag"
            f" unit={unit_n}, prefix={prefix_n}, suffix={suffix_n} in doc_id={doc_id}"
        )
        return hits

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_doc_pages(self, doc_id: str) -> List[Dict]:
        """Load all pages for a doc_id from text_by_page.jsonl (cached)."""
        if doc_id in self._doc_pages_cache:
            return self._doc_pages_cache[doc_id]

        if self.text_by_page_path is None:
            logger.warning("TextTagDetector: text_by_page_path is not configured")
            return []

        if jsonlines is None:
            logger.error(
                "TextTagDetector: jsonlines module not available; cannot load text_by_page"
            )
            return []

        try:
            from pathlib import Path

            path = Path(self.text_by_page_path)
            if not path.exists():
                logger.warning(f"TextTagDetector: text_by_page file not found: {path}")
                return []

            rows: List[Dict] = []
            with jsonlines.open(path, mode="r") as reader:
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    if row.get("doc_id") == doc_id:
                        # Expect at least page + text
                        rows.append(
                            {
                                "page": row.get("page"),
                                "text": row.get("text", ""),
                            }
                        )

            # Cache with simple LRU eviction
            if len(self._doc_pages_cache) >= self._max_docs_cache:
                # Remove first inserted key
                oldest_key = next(iter(self._doc_pages_cache))
                del self._doc_pages_cache[oldest_key]

            self._doc_pages_cache[doc_id] = rows
            logger.info(
                f"TextTagDetector: loaded {len(rows)} pages for doc_id={doc_id} "
                f"from {path}"
            )
            return rows

        except Exception as e:  # pragma: no cover - IO/FS errors
            logger.error(
                f"TextTagDetector: failed to load text_by_page for {doc_id}: {e}"
            )
            return []

    @staticmethod
    def _normalize_component(text: str) -> str:
        return (text or "").strip().upper()

    @staticmethod
    def _normalize_text(raw: str) -> str:
        """Normalize page text for token-based matching.

        - Uppercase
        - Collapse all whitespace (space/newline/tab) to single spaces
        """
        text = (raw or "").upper()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _tokenize(text: str) -> List[Token]:
        tokens: List[Token] = []
        for m in re.finditer(r"\b\w+\b", text):
            tokens.append(Token(text=m.group(0), start=m.start(), end=m.end()))
        return tokens

    def _find_hits_in_tokens(
        self,
        tokens: List[Token],
        unit: str,
        prefix: str,
        suffix: str,
        max_gap_tokens: int,
    ) -> List[Tuple[int, int, float]]:
        """Find tag occurrences in token sequence (ordered pattern).

        Primary pattern: unit -> prefix -> suffix, each within
        max_gap_tokens of the next component. This works well for
        vertical "stacked" tags where the reading order preserves the
        natural component sequence.

        Returns:
            List of (span_start, span_end, score)
        """
        if not tokens:
            return []

        hits: List[Tuple[int, int, float]] = []
        n = len(tokens)

        # Helper to compare unit allowing 0-padding differences
        def unit_equal(tok_text: str, unit_text: str) -> bool:
            return tok_text.lstrip("0") == unit_text.lstrip("0") and tok_text != ""

        for k, tk in enumerate(tokens):
            if tk.text != suffix:
                continue

            # Find prefix within window before suffix
            for j in range(max(0, k - max_gap_tokens), k):
                if tokens[j].text != prefix:
                    continue

                # Find unit within window before prefix
                for i in range(max(0, j - max_gap_tokens), j):
                    if not unit_equal(tokens[i].text, unit):
                        continue

                    # Compute span and score
                    span_start = tokens[i].start
                    span_end = tokens[k].end
                    span_len_tokens = k - i + 1  # number of tokens in span

                    # Proximity: fewer tokens between components -> higher score
                    if max_gap_tokens <= 3:
                        proximity = 1.0
                    else:
                        proximity = 1.0 - (span_len_tokens - 3) / (
                            max_gap_tokens - 3 + 1e-6
                        )
                        proximity = max(0.0, min(1.0, proximity))

                    # Order bonus: true for (i < j < k)
                    order_ok = i < j < k
                    order_bonus = 1.0 if order_ok else 0.7

                    score = 0.7 * proximity + 0.3 * order_bonus
                    hits.append((span_start, span_end, float(score)))

                    # Use the closest unit before this prefix
                    break

        return hits

    def _find_full_tag_window_hits(
        self,
        tokens: List[Token],
        unit: str,
        prefix: str,
        suffix: str,
        window_tokens: int,
    ) -> List[Tuple[int, int, float]]:
        """Find tag occurrences by anchoring on prefix and scanning a window.

        This pattern is designed for box-style tags such as "04 MXAK 04204",
        where the true visual layout may be vertical or the text extraction
        order is e.g. "04204 MXAK 04 ...". We:

        - Find each occurrence of the prefix token.
        - Look within a symmetric window of +/- window_tokens tokens.
        - If at least one unit-like token and one suffix token appear in
          that window, we consider it a hit regardless of order.

        The score is based on the token span covering all three components
        plus a small bonus when the natural order unit->prefix->suffix is
        preserved.
        """
        if not tokens or window_tokens <= 0:
            return []

        hits: List[Tuple[int, int, float]] = []
        n = len(tokens)

        def unit_equal(tok_text: str, unit_text: str) -> bool:
            return tok_text.lstrip("0") == unit_text.lstrip("0") and tok_text != ""

        for j, tj in enumerate(tokens):
            if tj.text != prefix:
                continue

            start_idx = max(0, j - window_tokens)
            end_idx = min(n - 1, j + window_tokens)

            unit_indices = [
                idx
                for idx in range(start_idx, end_idx + 1)
                if unit_equal(tokens[idx].text, unit)
            ]
            suffix_indices = [
                idx
                for idx in range(start_idx, end_idx + 1)
                if tokens[idx].text == suffix
            ]

            if not unit_indices or not suffix_indices:
                continue

            for i in unit_indices:
                for k in suffix_indices:
                    # Span covers all three components
                    a = min(i, j, k)
                    b = max(i, j, k)
                    span_start = tokens[a].start
                    span_end = tokens[b].end
                    span_len_tokens = b - a + 1

                    # Proximity: fewer tokens in the window -> higher score
                    if window_tokens <= 3:
                        proximity = 1.0
                    else:
                        proximity = 1.0 - (span_len_tokens - 3) / (
                            window_tokens - 3 + 1e-6
                        )
                        proximity = max(0.0, min(1.0, proximity))

                    order_ok = i < j < k
                    order_bonus = 1.0 if order_ok else 0.8

                    score = 0.7 * proximity + 0.3 * order_bonus
                    hits.append((span_start, span_end, float(score)))

        return hits
