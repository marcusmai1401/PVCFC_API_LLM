"""
Token budget management for conversation context.

Ensures conversation history + context stays within model token limits.
"""

from typing import Dict, List, Optional

from loguru import logger


class TokenBudgetManager:
    """
    Manages token budget for conversation context.

    Features:
    - Estimate tokens using tiktoken
    - Trim history to fit within budget
    - Prioritize recent turns over old ones
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        # Try to import tiktoken
        try:
            import tiktoken

            self.encoding = tiktoken.get_encoding("cl100k_base")
            self.use_tiktoken = True
        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            self.use_tiktoken = False

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        if self.use_tiktoken:
            return len(self.encoding.encode(text))
        else:
            # Fallback: rough estimation (4 chars ≈ 1 token)
            return len(text) // 4

    def estimate_turns_tokens(self, turns: List[Dict]) -> int:
        """Estimate total tokens for list of turns"""
        total = 0
        for turn in turns:
            # Add role tokens
            total += 4  # role overhead
            # Add content tokens
            total += self.estimate_tokens(turn.get("content", ""))
        return total

    def trim_to_budget(
        self,
        history: List[Dict],
        context_text: str,
        reserved_for_response: int = 1000,
    ) -> List[Dict]:
        """
        Trim history to fit within token budget.

        Args:
            history: Conversation history
            context_text: Retrieved context text
            reserved_for_response: Tokens to reserve for model response

        Returns:
            Trimmed history that fits within budget
        """
        # Calculate tokens used by context and response
        context_tokens = self.estimate_tokens(context_text)
        used_tokens = context_tokens + reserved_for_response

        # Calculate available tokens for history
        available = self.max_tokens - used_tokens

        if available <= 0:
            logger.warning("No tokens available for history after context + response")
            return []

        # Trim history from oldest first
        trimmed = []
        current_tokens = 0

        # Iterate from newest to oldest
        for turn in reversed(history):
            turn_tokens = self.estimate_tokens(turn.get("content", "")) + 4
            if current_tokens + turn_tokens <= available:
                trimmed.insert(0, turn)
                current_tokens += turn_tokens
            else:
                break

        logger.debug(
            f"Trimmed history to {len(trimmed)}/{len(history)} turns "
            f"({current_tokens}/{available} tokens)"
        )

        return trimmed

    def should_summarize(
        self,
        history: List[Dict],
        context_text: str,
        reserved_for_response: int = 1000,
    ) -> bool:
        """
        Check if history should be summarized to fit budget.

        Returns True if current history + context exceeds budget.
        """
        history_tokens = self.estimate_turns_tokens(history)
        context_tokens = self.estimate_tokens(context_text)
        total = history_tokens + context_tokens + reserved_for_response

        return total > self.max_tokens

    def validate_total_budget(
        self,
        trimmed_history: List[Dict],
        context_text: str,
        current_query: str,
        reserved_for_response: int = 1000,
        model_max_tokens: Optional[int] = None,
    ) -> bool:
        """
        BUG-031 FIX: Validate that total tokens fit within model limits.

        Previously, trim_to_budget() only trimmed history but didn't validate
        that the total (history + context + query + response) fits model max.
        This could cause generation failures due to token overflow.

        Args:
            trimmed_history: History after trimming
            context_text: Retrieved context text
            current_query: Current user query
            reserved_for_response: Tokens reserved for model response
            model_max_tokens: Model's max token limit (defaults to self.max_tokens)

        Returns:
            True if total fits within budget, False otherwise
        """
        model_max = model_max_tokens or self.max_tokens

        # Calculate total tokens
        history_tokens = self.estimate_turns_tokens(trimmed_history)
        context_tokens = self.estimate_tokens(context_text)
        query_tokens = self.estimate_tokens(current_query)
        total_tokens = (
            history_tokens + context_tokens + query_tokens + reserved_for_response
        )

        if total_tokens > model_max:
            logger.warning(
                f"Token budget overflow detected: {total_tokens} > {model_max} "
                f"(history={history_tokens}, context={context_tokens}, "
                f"query={query_tokens}, response={reserved_for_response})"
            )
            return False

        logger.debug(
            f"Token budget OK: {total_tokens}/{model_max} tokens "
            f"({(total_tokens/model_max)*100:.1f}% used)"
        )
        return True
