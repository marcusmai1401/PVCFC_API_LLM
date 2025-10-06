"""
Claims Extraction Module

Extracts factual claims from generated answers to enable per-claim attribution
and improve citation accuracy.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from loguru import logger


class ClaimType(str, Enum):
    """Types of factual claims"""

    NUMERICAL = "numerical"  # Contains numbers, measurements, values
    CATEGORICAL = "categorical"  # Describes categories, types, properties
    PROCEDURAL = "procedural"  # Describes processes, steps, methods
    TEMPORAL = "temporal"  # Time-based claims
    RELATIONAL = "relational"  # Relationships between entities


@dataclass
class Claim:
    """A single factual claim extracted from an answer"""

    id: str
    text: str
    type: ClaimType
    keywords: List[str]
    confidence: float = 1.0
    requires_citation: bool = True

    # For mapping back to answer
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None


class ClaimsExtractor:
    """Extract factual claims from text"""

    def __init__(self):
        # Patterns for identifying different claim types
        self.numerical_pattern = re.compile(
            r"\b\d+(?:[.,]\d+)*\s*(?:mm|cm|m|km|kg|g|ton|bar|psi|°C|°F|kW|MW|Hz|V|A|%|Nm|rpm)\b",
            re.IGNORECASE,
        )
        self.technical_terms = re.compile(
            r"\b[A-Z]{2,}[-]?\d{2,}[A-Z]?\b"  # Equipment tags like KT-06101
        )

    def extract_factual_claims(
        self, answer: str, min_claim_length: int = 10
    ) -> List[Claim]:
        """
        Extract factual claims from answer text.

        Args:
            answer: Generated answer text
            min_claim_length: Minimum length for a claim to be extracted

        Returns:
            List of extracted claims
        """
        if not answer or len(answer.strip()) < min_claim_length:
            return []

        claims = []

        # Split by sentences
        sentences = self._split_sentences(answer)

        for idx, sentence in enumerate(sentences):
            if len(sentence.strip()) < min_claim_length:
                continue

            claim_type = self._classify_claim(sentence)
            keywords = self._extract_keywords(sentence)

            # Only extract claims that need citations
            requires_citation = self._requires_citation(sentence, claim_type)

            if requires_citation:
                claim = Claim(
                    id=f"claim_{idx}",
                    text=sentence.strip(),
                    type=claim_type,
                    keywords=keywords,
                    requires_citation=requires_citation,
                )
                claims.append(claim)

        logger.debug(f"Extracted {len(claims)} claims from answer")
        return claims

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting (can be improved with spaCy/NLTK)
        # Handle common abbreviations
        text = text.replace("e.g.", "eg").replace("i.e.", "ie")

        # Split on sentence boundaries
        sentences = re.split(r"[.!?]\s+", text)
        return [s for s in sentences if s.strip()]

    def _classify_claim(self, sentence: str) -> ClaimType:
        """Classify the type of claim"""
        sentence_lower = sentence.lower()

        # Check for numerical claims
        if self.numerical_pattern.search(sentence):
            return ClaimType.NUMERICAL

        # Check for procedural claims
        procedural_markers = [
            "step",
            "first",
            "then",
            "next",
            "finally",
            "procedure",
            "method",
            "process",
            "install",
            "operate",
            "maintain",
        ]
        if any(marker in sentence_lower for marker in procedural_markers):
            return ClaimType.PROCEDURAL

        # Check for temporal claims
        temporal_markers = [
            "when",
            "during",
            "after",
            "before",
            "while",
            "year",
            "month",
            "day",
            "hour",
            "time",
        ]
        if any(marker in sentence_lower for marker in temporal_markers):
            return ClaimType.TEMPORAL

        # Check for relational claims
        relational_markers = [
            "connect",
            "link",
            "relate",
            "between",
            "among",
            "with",
            "associated",
            "part of",
            "belongs to",
        ]
        if any(marker in sentence_lower for marker in relational_markers):
            return ClaimType.RELATIONAL

        # Default to categorical
        return ClaimType.CATEGORICAL

    def _extract_keywords(self, sentence: str) -> List[str]:
        """Extract important keywords from claim"""
        keywords = []

        # Extract numerical values with units
        numerical_matches = self.numerical_pattern.findall(sentence)
        keywords.extend(numerical_matches)

        # Extract equipment tags
        technical_matches = self.technical_terms.findall(sentence)
        keywords.extend(technical_matches)

        # Extract capitalized terms (likely technical terms)
        capitalized = re.findall(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\b", sentence)
        keywords.extend([c for c in capitalized if len(c) > 3])

        return list(set(keywords))  # Remove duplicates

    def _requires_citation(self, sentence: str, claim_type: ClaimType) -> bool:
        """Determine if a claim requires citation"""
        sentence_lower = sentence.lower()

        # Generic statements don't need citations
        generic_phrases = [
            "in general",
            "typically",
            "usually",
            "generally",
            "commonly",
            "often",
            "sometimes",
            "it is known that",
        ]
        if any(phrase in sentence_lower for phrase in generic_phrases):
            return False

        # Questions don't need citations
        if sentence.strip().endswith("?"):
            return False

        # Very short sentences likely don't need citations
        if len(sentence.split()) < 5:
            return False

        # Numerical and procedural claims always need citations
        if claim_type in [ClaimType.NUMERICAL, ClaimType.PROCEDURAL]:
            return True

        # Check for factual indicators
        factual_indicators = [
            "according to",
            "as stated",
            "documented",
            "specified",
            "required",
            "must",
            "shall",
            "defined as",
        ]
        if any(indicator in sentence_lower for indicator in factual_indicators):
            return True

        return True  # Default: require citation


def extract_factual_claims(answer: str, min_claim_length: int = 10) -> List[Claim]:
    """
    Convenience function to extract claims.

    Args:
        answer: Generated answer text
        min_claim_length: Minimum length for a claim

    Returns:
        List of extracted claims
    """
    extractor = ClaimsExtractor()
    return extractor.extract_factual_claims(answer, min_claim_length)


if __name__ == "__main__":
    # Test the claims extractor
    test_answer = """
    Áp suất vận hành tối đa của KT-06101 là 10 bar theo datasheet.
    Thiết bị này được lắp đặt tại vị trí P-123 trong nhà máy.
    Quy trình bảo trì yêu cầu kiểm tra định kỳ 6 tháng/lần.
    Nhiệt độ hoạt động nằm trong khoảng 5-40°C.
    """

    claims = extract_factual_claims(test_answer)

    print(f"\nExtracted {len(claims)} claims:")
    for claim in claims:
        print(f"\n- Type: {claim.type}")
        print(f"  Text: {claim.text}")
        print(f"  Keywords: {claim.keywords}")
        print(f"  Requires citation: {claim.requires_citation}")
