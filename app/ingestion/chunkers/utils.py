"""
Chunking Utilities

Helper functions for token counting, text normalization, and chunking operations.
"""

import re
from typing import List, Optional


def estimate_tokens(text: str, method: str = "simple") -> int:
    """
    Estimate token count for text.

    Args:
        text: Input text
        method: Estimation method ('simple', 'tiktoken', or 'accurate')

    Returns:
        Estimated token count
    """
    if method == "tiktoken" or method == "accurate":
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            # Fallback to simple if tiktoken not available
            pass

    # Simple estimate: 1 token ≈ 4 characters
    # Adjusted for technical text and mixed languages
    char_count = len(text)

    # More accurate for different character types
    # ASCII/Latin: ~4 chars/token
    # CJK: ~1.5 chars/token
    # Technical symbols: variable

    # Rough heuristic
    return max(1, char_count // 4)


def normalize_whitespace(text: str, preserve_paragraphs: bool = True) -> str:
    """
    Normalize whitespace in text.

    Args:
        text: Input text
        preserve_paragraphs: Whether to preserve paragraph breaks

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if preserve_paragraphs:
        # Preserve double newlines (paragraph breaks)
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)
        # Preserve paragraph breaks but normalize them to double newline
        text = re.sub(r"\n\n+", "\n\n", text)
        # Remove spaces at line starts/ends
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
    else:
        # Replace all newlines with spaces
        text = text.replace("\n", " ")
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)

    return text.strip()


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.

    Simple sentence splitting that handles common cases.
    Not perfect but good enough for chunking.

    Args:
        text: Input text

    Returns:
        List of sentences
    """
    # Pattern for sentence endings
    # Handles: . ! ? followed by space/newline/end
    # Avoids splitting on: Mr. Dr. etc. numbers like 3.14

    # First, protect common abbreviations
    text = text.replace("Mr.", "Mr<DOT>")
    text = text.replace("Mrs.", "Mrs<DOT>")
    text = text.replace("Dr.", "Dr<DOT>")
    text = text.replace("Prof.", "Prof<DOT>")
    text = text.replace("Sr.", "Sr<DOT>")
    text = text.replace("Jr.", "Jr<DOT>")
    text = text.replace("Inc.", "Inc<DOT>")
    text = text.replace("Ltd.", "Ltd<DOT>")
    text = text.replace("Co.", "Co<DOT>")
    text = text.replace("vs.", "vs<DOT>")
    text = text.replace("etc.", "etc<DOT>")
    text = text.replace("e.g.", "e<DOT>g<DOT>")
    text = text.replace("i.e.", "i<DOT>e<DOT>")

    # Split on sentence endings
    pattern = r"([.!?]+)\s+"
    parts = re.split(pattern, text)

    # Recombine sentences with their punctuation
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        sentence = parts[i]
        if i + 1 < len(parts):
            sentence += parts[i + 1]

        # Restore protected abbreviations
        sentence = sentence.replace("<DOT>", ".")
        sentence = sentence.strip()

        if sentence:
            sentences.append(sentence)

    # Handle last part
    if len(parts) % 2 == 1 and parts[-1].strip():
        last = parts[-1].replace("<DOT>", ".").strip()
        if last:
            sentences.append(last)

    return sentences


def detect_headers(text: str) -> List[tuple]:
    """
    Detect section headers in text.

    Returns list of (header_text, start_pos, end_pos) tuples.

    Args:
        text: Input text

    Returns:
        List of header tuples
    """
    headers = []

    # Pattern 1: Markdown-style headers (# Header, ## Header)
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
        headers.append((match.group(2).strip(), match.start(), match.end()))

    # Pattern 2: Numbered headers (1. Header, 1.1 Header)
    for match in re.finditer(r"^(\d+(?:\.\d+)*)\.\s+(.+)$", text, re.MULTILINE):
        headers.append((match.group(2).strip(), match.start(), match.end()))

    # Pattern 3: ALL CAPS headers (minimum 3 words)
    for match in re.finditer(r"^([A-Z][A-Z\s]{10,})$", text, re.MULTILINE):
        header_text = match.group(1).strip()
        # Check if it's really a header (has multiple words)
        if len(header_text.split()) >= 2:
            headers.append((header_text, match.start(), match.end()))

    return headers


def extract_equipment_tags(text: str) -> List[str]:
    """
    Extract equipment tags from text.

    Common patterns: P-101, HX-202, V-303, E-404, T-505, etc.

    Args:
        text: Input text

    Returns:
        List of equipment tags
    """
    # Pattern: Letter(s)-Number(s) with optional suffixes
    pattern = r"\b([A-Z]{1,3})-?(\d{2,4}[A-Z]?)\b"

    matches = re.findall(pattern, text)
    tags = [f"{prefix}-{number}" for prefix, number in matches]

    return list(set(tags))  # Remove duplicates


def chunk_by_tokens(
    text: str, max_tokens: int, overlap_tokens: int = 0, estimator=None
) -> List[str]:
    """
    Chunk text by token count with overlap.

    Args:
        text: Input text
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap size in tokens
        estimator: Function to estimate tokens (default: simple estimate)

    Returns:
        List of text chunks
    """
    if estimator is None:
        estimator = estimate_tokens

    # Split into sentences
    sentences = split_into_sentences(text)

    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    current_chunk = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = estimator(sentence)

        # If single sentence exceeds max, split it
        if sentence_tokens > max_tokens and not current_chunk:
            # Split by characters as last resort
            words = sentence.split()
            temp_chunk = []
            temp_tokens = 0

            for word in words:
                word_tokens = estimator(word)
                if temp_tokens + word_tokens > max_tokens and temp_chunk:
                    chunks.append(" ".join(temp_chunk))
                    # Overlap: keep last few words
                    if overlap_tokens > 0:
                        overlap_words = []
                        overlap_token_count = 0
                        for w in reversed(temp_chunk):
                            w_tokens = estimator(w)
                            if overlap_token_count + w_tokens <= overlap_tokens:
                                overlap_words.insert(0, w)
                                overlap_token_count += w_tokens
                            else:
                                break
                        temp_chunk = overlap_words
                        temp_tokens = overlap_token_count
                    else:
                        temp_chunk = []
                        temp_tokens = 0

                temp_chunk.append(word)
                temp_tokens += word_tokens

            if temp_chunk:
                chunks.append(" ".join(temp_chunk))
            continue

        # Check if adding sentence exceeds max
        if current_tokens + sentence_tokens > max_tokens and current_chunk:
            # Save current chunk
            chunks.append(" ".join(current_chunk))

            # Start new chunk with overlap
            if overlap_tokens > 0:
                # Keep last sentences that fit in overlap
                overlap_chunk = []
                overlap_token_count = 0

                for sent in reversed(current_chunk):
                    sent_tokens = estimator(sent)
                    if overlap_token_count + sent_tokens <= overlap_tokens:
                        overlap_chunk.insert(0, sent)
                        overlap_token_count += sent_tokens
                    else:
                        break

                current_chunk = overlap_chunk
                current_tokens = overlap_token_count
            else:
                current_chunk = []
                current_tokens = 0

        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    # Add remaining chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
