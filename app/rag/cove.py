"""
Chain-of-Verification (CoVe) implementation for Phase 2.
Light-weight verification to reduce hallucinations in RAG answers.
"""
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings
from app.rag.query_transform import QueryIntent, QueryTransformer
from app.rag.schemas import CoVeCheckpoint
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


@dataclass
class VerificationClaim:
    """A claim extracted from the answer that needs verification."""

    claim: str
    importance: float  # 0.0 to 1.0
    check_queries: List[str]


class ChainOfVerification:
    """
    Chain-of-Verification (CoVe) for answer validation.
    Extracts key claims from answers and verifies them against retrieved chunks.
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        settings: Optional[Settings] = None,
    ):
        """Initialize CoVe with LLM service."""
        self.settings = settings or Settings()
        self.llm_service = llm_service or LLMService(settings=self.settings)

    async def extract_claims(
        self, answer: str, max_claims: int = 5
    ) -> List[VerificationClaim]:
        """
        Extract key factual claims from the answer.

        Args:
            answer: Generated answer text
            max_claims: Maximum number of claims to extract

        Returns:
            List of verification claims
        """
        # Simple regex-based extraction for key facts
        # Look for sentences with specific patterns
        claims = []

        # Pattern 1: Statements with numbers/values
        number_pattern = r"[^.!?]*\d+(?:\.\d+)?[^.!?]*[.!?]"
        number_matches = re.findall(number_pattern, answer)

        # Pattern 2: Statements with "là", "is", "are", "được", "có"
        fact_pattern = (
            r"[^.!?]*(?:là|is|are|được|có|bao gồm|includes?|contains?)[^.!?]*[.!?]"
        )
        fact_matches = re.findall(fact_pattern, answer, re.IGNORECASE)

        # Combine and deduplicate
        all_statements = list(set(number_matches + fact_matches))

        # Score by importance (length, keywords, position)
        scored_statements = []
        for stmt in all_statements[: max_claims * 2]:  # Get extra for filtering
            stmt = stmt.strip()
            if len(stmt) < 20:  # Skip very short statements
                continue

            # Calculate importance score
            importance = 0.5
            if any(
                keyword in stmt.lower()
                for keyword in [
                    "tối đa",
                    "maximum",
                    "minimum",
                    "critical",
                    "quan trọng",
                ]
            ):
                importance += 0.3
            if re.search(r"\d+", stmt):  # Contains numbers
                importance += 0.2

            # Generate check queries for this claim
            check_queries = self._generate_check_queries(stmt)

            scored_statements.append(
                VerificationClaim(
                    claim=stmt,
                    importance=min(importance, 1.0),
                    check_queries=check_queries,
                )
            )

        # Sort by importance and take top claims
        scored_statements.sort(key=lambda x: x.importance, reverse=True)
        claims = scored_statements[:max_claims]

        logger.info(f"Extracted {len(claims)} claims for verification")
        return claims

    def _generate_check_queries(self, claim: str) -> List[str]:
        """
        Generate search queries to verify a claim.

        Args:
            claim: The claim to verify

        Returns:
            List of check queries
        """
        queries = []

        # Extract key entities/numbers from claim
        entities = re.findall(r"\b[A-Z][A-Z0-9]{3,}\b", claim)  # e.g., KT06101
        numbers = re.findall(r"\d+(?:\.\d+)?", claim)

        # Query 1: Use main entities
        if entities:
            queries.append(" ".join(entities))

        # Query 2: Entities + key numbers
        if entities and numbers:
            queries.append(f"{entities[0]} {numbers[0]}")

        # Query 3: Key terms from claim (simplified)
        # Remove common words and create a focused query
        key_words = []
        for word in claim.split():
            word = word.strip(".,!?")
            if len(word) > 3 and word.lower() not in [
                "this",
                "that",
                "with",
                "from",
                "trong",
                "được",
                "của",
            ]:
                key_words.append(word)
        if len(key_words) > 2:
            queries.append(" ".join(key_words[:4]))

        # Fallback: use a truncated version of the claim
        if not queries:
            queries.append(claim[:50])

        return queries[:3]  # Max 3 queries per claim

    async def verify_claims(
        self,
        claims: List[VerificationClaim],
        retriever: Any,  # HybridRetriever instance
        confidence_threshold: float = 0.4,  # Lowered from 0.5 to reduce false warnings
    ) -> List[CoVeCheckpoint]:
        """
        Verify claims against the retrieval index.

        Args:
            claims: List of claims to verify
            retriever: Retriever instance to search for evidence
            confidence_threshold: Minimum confidence to consider evidence valid

        Returns:
            List of verification checkpoints
        """
        checkpoints = []

        # Use a lightweight transformer without HyDE for verification queries
        query_transformer = QueryTransformer(enable_hyde=False)

        for claim in claims:
            # Try each check query
            best_evidence = None
            best_score = 0.0
            supporting_chunks = []

            for check_query in claim.check_queries:
                try:
                    # Transform check query and force ASK intent
                    transformed_query = query_transformer.transform(
                        query=check_query, filters=None
                    )
                    transformed_query.intent = QueryIntent.ASK

                    # Perform search using current retriever interface
                    results = retriever.search(transformed_query)

                    if results:
                        # Check if any result contains evidence
                        for res in results[:5]:  # limit for speed
                            score = float(res.score)
                            if score > best_score:
                                best_score = score
                                best_evidence = res

                            if score > confidence_threshold:
                                supporting_chunks.append(
                                    getattr(res, "chunk_id", "unknown")
                                )

                except Exception as e:
                    logger.warning(f"Verification query failed: {e}")
                    continue

            # Create checkpoint
            checkpoint = CoVeCheckpoint(
                claim=claim.claim,
                check_query=claim.check_queries[0] if claim.check_queries else "",
                evidence_found=best_score > confidence_threshold,
                confidence=best_score,
                supporting_chunks=supporting_chunks[:3],  # Top 3 supporting chunks
            )
            checkpoints.append(checkpoint)

            logger.debug(
                f"Verified claim: evidence_found={checkpoint.evidence_found}, confidence={checkpoint.confidence:.2f}"
            )

        return checkpoints

    async def adjust_answer(
        self,
        original_answer: str,
        checkpoints: List[CoVeCheckpoint],
        confidence_threshold: float = 0.4,  # Lowered from 0.5 to reduce false warnings
        global_confidence: float = 1.0,  # Overall answer confidence from generation
    ) -> Tuple[str, List[str]]:
        """
        Adjust answer based on verification results.

        Args:
            original_answer: Original generated answer
            checkpoints: Verification checkpoints
            confidence_threshold: Minimum confidence for claims
            global_confidence: Overall answer confidence from generation (0.0-1.0)

        Returns:
            Tuple of (adjusted_answer, warnings)
        """
        adjusted_answer = original_answer
        warnings = []

        # Check for unverified claims
        unverified_claims = [
            cp
            for cp in checkpoints
            if not cp.evidence_found or cp.confidence < confidence_threshold
        ]

        # Smart warning logic: Only warn if BOTH verification AND global confidence suggest issues
        # This prevents false warnings when answer is generated from vision/high-quality sources
        if (
            unverified_claims and global_confidence < 0.85
        ):  # Only warn if global confidence is not high
            # Build detailed warning with confidence scores
            low_conf_count = len(
                [cp for cp in unverified_claims if cp.confidence < 0.2]
            )
            med_conf_count = len(
                [
                    cp
                    for cp in unverified_claims
                    if 0.2 <= cp.confidence < confidence_threshold
                ]
            )

            # Severity-based warnings
            if low_conf_count > 0 and global_confidence < 0.7:
                # High severity: Low verification + Low global confidence
                warning_msg = f"⚠️ Verification: {len(unverified_claims)}/{len(checkpoints)} claims have lower confidence (verification < {confidence_threshold:.1f}, answer confidence: {global_confidence:.0%})"
                warnings.append(warning_msg)

                # Add specific details for very low confidence claims (only top 2 to avoid spam)
                shown = 0
                for cp in unverified_claims:
                    if cp.confidence < 0.2 and shown < 2:  # Very low confidence
                        warnings.append(
                            f"   • Low verification ({cp.confidence:.2f}): '{cp.claim[:60]}...'"
                        )
                        shown += 1
            elif (
                med_conf_count > 0 and len(checkpoints) > 2 and global_confidence < 0.75
            ):
                # Medium severity: Moderate verification + Medium global confidence
                avg_verif_conf = sum(cp.confidence for cp in unverified_claims) / len(
                    unverified_claims
                )
                warning_msg = f"ℹ️ Note: Some claims need additional verification (avg verification: {avg_verif_conf:.2f}, answer confidence: {global_confidence:.0%})"
                warnings.append(warning_msg)

        # Check overall verification rate
        verification_rate = (
            len([cp for cp in checkpoints if cp.evidence_found]) / len(checkpoints)
            if checkpoints
            else 1.0
        )

        # Only warn if verification rate is critically low AND global confidence is not high
        # This prevents false alarms when answer comes from high-quality sources (e.g., vision)
        if verification_rate < 0.2 and global_confidence < 0.8:
            # Calculate average confidence for context
            avg_confidence = (
                sum(cp.confidence for cp in checkpoints) / len(checkpoints)
                if checkpoints
                else 0.0
            )

            # Add detailed warning with metrics (only if global confidence suggests real issues)
            disclaimer = (
                f"\n\n⚠️ **Verification Notice**: "
                f"This answer has limited verification coverage ({verification_rate:.0%} verified, avg: {avg_confidence:.2f}, confidence: {global_confidence:.0%}). "
                f"Please cross-reference with source documents for critical information."
            )
            adjusted_answer += disclaimer
            warnings.append(
                f"Low verification rate ({verification_rate:.0%}, global confidence: {global_confidence:.0%}) - "
                f"{len(checkpoints)} claims checked, {len([cp for cp in checkpoints if cp.evidence_found])} verified"
            )

        return adjusted_answer, warnings

    async def run_verification(
        self,
        answer: str,
        retriever: Any,
        max_claims: int = 5,
        confidence_threshold: float = 0.4,  # Lowered from 0.5
        global_confidence: float = 1.0,  # Overall answer confidence from generation
    ) -> Dict[str, Any]:
        """
        Run full CoVe pipeline on an answer.

        Args:
            answer: Generated answer to verify
            retriever: Retriever instance for evidence search
            max_claims: Maximum claims to extract and verify
            confidence_threshold: Minimum confidence threshold
            global_confidence: Overall answer confidence from generation (0.0-1.0)

        Returns:
            Verification results with adjusted answer and metadata
        """
        try:
            # Extract claims
            claims = await self.extract_claims(answer, max_claims=max_claims)

            if not claims:
                logger.info("No verifiable claims found in answer")
                return {
                    "adjusted_answer": answer,
                    "warnings": [],
                    "verification_rate": 1.0,
                    "checkpoints": [],
                }

            # Verify claims
            checkpoints = await self.verify_claims(
                claims, retriever, confidence_threshold=confidence_threshold
            )

            # Adjust answer based on verification (pass global_confidence for smart warning logic)
            adjusted_answer, warnings = await self.adjust_answer(
                answer,
                checkpoints,
                confidence_threshold=confidence_threshold,
                global_confidence=global_confidence,
            )

            # Calculate metrics
            verified_count = len([cp for cp in checkpoints if cp.evidence_found])
            verification_rate = (
                verified_count / len(checkpoints) if checkpoints else 1.0
            )

            return {
                "adjusted_answer": adjusted_answer,
                "warnings": warnings,
                "verification_rate": verification_rate,
                "checkpoints": checkpoints,
                "claims_extracted": len(claims),
                "claims_verified": verified_count,
            }

        except Exception as e:
            logger.error(f"CoVe verification failed: {e}")
            # Return original answer on failure
            return {
                "adjusted_answer": answer,
                "warnings": [f"Xác thực không thành công: {str(e)}"],
                "verification_rate": 0.0,
                "checkpoints": [],
            }
