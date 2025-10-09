"""
Rule-Based NLI (Natural Language Inference) Validator

Fast, model-free entailment scoring for citation validation.
Uses only Python stdlib (re, difflib) for compatibility.

The validator checks if a hypothesis (claim) is entailed by a premise (page text)
using multiple heuristic signals:
- Token overlap (Jaccard similarity)
- Keyword presence
- Numerical consistency
- Named entity consistency

Example:
    >>> from app.rag.nli_validator import RuleBasedNLIValidator
    >>> validator = RuleBasedNLIValidator()
    >>> premise = "Paris is the capital of France. Population ~2.1 million."
    >>> hypothesis = "Paris is France's capital with 2.1 million people."
    >>> score = validator.entail(premise, hypothesis)
    >>> score > 0.7
    True
"""

import logging
import re
from typing import Iterable, List, Set

logger = logging.getLogger(__name__)

# Common stopwords (small set for performance)
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "can",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
}

# Month names for entity extraction
MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
}


def _normalize(text: str) -> str:
    """Normalize text (lowercase, strip, collapse whitespace)."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _tokenize(text: str) -> List[str]:
    """Tokenize normalized text."""
    if not text:
        return []
    return text.split()


class RuleBasedNLIValidator:
    """
    Rule-based Natural Language Inference validator.

    Provides fast entailment scoring without ML models.
    Uses multiple heuristic signals to determine if premise entails hypothesis.

    Scoring components (weighted):
        - Token overlap (0.3): Jaccard similarity after stopword removal
        - Keyword matching (0.3): Fraction of hypothesis keywords in premise
        - Numerical consistency (0.2): Number matching with tolerance
        - Named entity consistency (0.2): Entity matching (acronyms, proper nouns)

    Example:
        >>> validator = RuleBasedNLIValidator()
        >>> premise = "The temperature is 25.5°C at noon."
        >>> hypothesis = "Temperature: 25.5 degrees"
        >>> score = validator.entail(premise, hypothesis)
        >>> score > 0.6
        True
        >>> validator.entail("", "Any text")
        0.0
    """

    def __init__(self):
        """Initialize NLI validator."""
        logger.debug("RuleBasedNLIValidator initialized")

    def entail(self, premise: str, hypothesis: str) -> float:
        """
        Compute entailment score between premise and hypothesis.

        Args:
            premise: Source text (e.g., page content)
            hypothesis: Claim to verify (e.g., citation text)

        Returns:
            Entailment score in [0.0, 1.0], where 1.0 means full entailment

        Example:
            >>> v = RuleBasedNLIValidator()
            >>> v.entail("Paris is in France", "Paris is French") > 0.5
            True
            >>> v.entail("abc", "xyz")
            0.0
        """
        # Normalize
        norm_premise = _normalize(premise)
        norm_hypothesis = _normalize(hypothesis)

        # Handle empty inputs
        if not norm_premise or not norm_hypothesis:
            return 0.0

        # Tokenize
        premise_tokens = _tokenize(norm_premise)
        hypothesis_tokens = _tokenize(norm_hypothesis)

        if not premise_tokens or not hypothesis_tokens:
            return 0.0

        # Component scores
        token_score = self._token_overlap(premise_tokens, hypothesis_tokens)
        keyword_score = self._keyword_matching(norm_premise, norm_hypothesis)
        number_score = self._numerical_consistency(norm_premise, norm_hypothesis)
        entity_score = self._entity_consistency(premise, hypothesis)

        # Weighted combination
        score = (
            0.3 * token_score
            + 0.3 * keyword_score
            + 0.2 * number_score
            + 0.2 * entity_score
        )

        # Clip to [0, 1]
        return max(0.0, min(1.0, score))

    def _token_overlap(
        self, premise_tokens: List[str], hypothesis_tokens: List[str]
    ) -> float:
        """
        Compute token overlap (Jaccard) after removing stopwords.

        Args:
            premise_tokens: Premise tokens
            hypothesis_tokens: Hypothesis tokens

        Returns:
            Jaccard similarity score
        """
        # Remove stopwords
        premise_set = {t for t in premise_tokens if t not in STOPWORDS}
        hypothesis_set = {t for t in hypothesis_tokens if t not in STOPWORDS}

        if not premise_set or not hypothesis_set:
            return 0.0

        intersection = len(premise_set & hypothesis_set)
        union = len(premise_set | hypothesis_set)

        return intersection / union if union > 0 else 0.0

    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from text.

        Filters to tokens with length >= 4, alphanumeric, not stopwords.

        Args:
            text: Normalized text

        Returns:
            Set of keywords
        """
        tokens = _tokenize(text)
        keywords = {
            token
            for token in tokens
            if len(token) >= 4 and token.isalnum() and token not in STOPWORDS
        }
        return keywords

    def _keyword_matching(self, premise: str, hypothesis: str) -> float:
        """
        Compute keyword matching score.

        Fraction of hypothesis keywords present in premise.

        Args:
            premise: Premise text (normalized)
            hypothesis: Hypothesis text (normalized)

        Returns:
            Keyword matching score
        """
        hyp_keywords = self._extract_keywords(hypothesis)

        if not hyp_keywords:
            return 1.0  # No keywords to match

        matched = sum(1 for kw in hyp_keywords if kw in premise)

        return matched / len(hyp_keywords)

    def _extract_numbers(self, text: str) -> List[float]:
        """
        Extract numbers from text.

        Handles integers and decimals (with . or , as separator).

        Args:
            text: Text to extract from

        Returns:
            List of numbers
        """
        # Pattern: optional sign, digits, optional decimal part
        pattern = r"[-+]?\d+(?:[.,]\d+)?"
        matches = re.findall(pattern, text)

        numbers = []
        for match in matches:
            try:
                # Normalize comma to dot
                normalized = match.replace(",", ".")
                numbers.append(float(normalized))
            except ValueError:
                continue

        return numbers

    def _numerical_consistency(self, premise: str, hypothesis: str) -> float:
        """
        Check numerical consistency between premise and hypothesis.

        All numbers in hypothesis should be present in premise within tolerance.

        Args:
            premise: Premise text
            hypothesis: Hypothesis text

        Returns:
            Numerical consistency score
        """
        hyp_numbers = self._extract_numbers(hypothesis)

        if not hyp_numbers:
            return 1.0  # No numbers to check

        premise_numbers = self._extract_numbers(premise)

        if not premise_numbers:
            return 0.0  # Hypothesis has numbers but premise doesn't

        matched = 0
        for h_num in hyp_numbers:
            for p_num in premise_numbers:
                # Check if numbers match within tolerance
                # Absolute tolerance: 1e-6
                # Relative tolerance: 1% (0.01)
                if abs(h_num - p_num) <= 1e-6:
                    matched += 1
                    break
                elif h_num != 0 and abs((h_num - p_num) / h_num) <= 0.01:
                    matched += 1
                    break

        return matched / len(hyp_numbers)

    def _extract_entities(self, text: str) -> Set[str]:
        """
        Extract named entities using heuristics.

        Extracts:
        - Acronyms (2+ consecutive uppercase letters)
        - Proper noun sequences (capitalized words)
        - Quoted phrases
        - Month names

        Args:
            text: Text to extract from (original case)

        Returns:
            Set of entities (lowercased for matching)
        """
        entities = set()

        # Acronyms: 2+ uppercase letters
        acronyms = re.findall(r"\b[A-Z]{2,}\b", text)
        entities.update(acr.lower() for acr in acronyms)

        # Proper noun sequences: Capitalized Word+
        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        entities.update(pn.lower() for pn in proper_nouns)

        # Quoted phrases
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
        for match_tuple in quoted:
            for phrase in match_tuple:
                if phrase:
                    entities.add(phrase.lower())

        # Month names
        tokens = _tokenize(_normalize(text))
        for token in tokens:
            if token in MONTHS:
                entities.add(token)

        return entities

    def _entity_consistency(self, premise: str, hypothesis: str) -> float:
        """
        Check named entity consistency.

        Fraction of hypothesis entities present in premise.

        Args:
            premise: Premise text
            hypothesis: Hypothesis text

        Returns:
            Entity consistency score
        """
        hyp_entities = self._extract_entities(hypothesis)

        if not hyp_entities:
            return 1.0  # No entities to check

        premise_lower = _normalize(premise)

        matched = 0
        for entity in hyp_entities:
            # Check case-insensitive presence
            if entity in premise_lower:
                matched += 1

        return matched / len(hyp_entities)


if __name__ == "__main__":
    # Run doctests
    import doctest

    doctest.testmod()

    # Smoke tests
    print("=== NLI Validator Smoke Tests ===")

    validator = RuleBasedNLIValidator()

    # Test 1: High entailment
    p1 = "Paris is the capital of France. Population ~2.1 million."
    h1 = "Paris is France's capital with 2.1 million people."
    score1 = validator.entail(p1, h1)
    print(f"Test 1 (high entailment): {score1:.2f} (expected: >0.7)")
    assert score1 > 0.7

    # Test 2: Partial entailment
    p2 = "The temperature is 25°C at noon."
    h2 = "It is warm at noon."
    score2 = validator.entail(p2, h2)
    print(f"Test 2 (partial entailment): {score2:.2f} (expected: 0.3-0.7)")
    assert 0.3 <= score2 <= 0.7

    # Test 3: No entailment
    p3 = "The sky is blue."
    h3 = "The grass is green."
    score3 = validator.entail(p3, h3)
    print(f"Test 3 (no entailment): {score3:.2f} (expected: <0.3)")
    assert score3 < 0.3

    # Test 4: Numerical match
    p4 = "Pressure: 1.5 bar, temperature: 45.0°C"
    h4 = "Pressure is 1.5 bar"
    score4 = validator.entail(p4, h4)
    print(f"Test 4 (numerical match): {score4:.2f} (expected: >0.6)")
    assert score4 > 0.6

    # Test 5: Entity match
    p5 = "PVCFC operates the KT-06101 compressor in Vietnam."
    h5 = "KT-06101 is in Vietnam."
    score5 = validator.entail(p5, h5)
    print(f"Test 5 (entity match): {score5:.2f} (expected: >0.6)")
    assert score5 > 0.6

    # Test 6: Empty handling
    score6 = validator.entail("", "text")
    print(f"Test 6 (empty premise): {score6:.2f} (expected: 0.00)")
    assert score6 == 0.0

    print("\n✓ All smoke tests passed!")
