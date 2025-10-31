"""
Conversation summarization for token budget management.

Periodically summarizes conversation history to maintain context
while staying within token limits.
"""

from typing import Dict, List, Optional

from loguru import logger


class ConversationSummarizer:
    """
    Summarizes conversation history to reduce token usage.

    Features:
    - Periodic summarization (every N turns)
    - Recency bias (keep recent turns, summarize old ones)
    - Uses light-tier LLM for cost efficiency
    """

    def __init__(self, summarize_every_n_turns: int = 8):
        self.summarize_every_n_turns = summarize_every_n_turns

    def should_summarize(self, turn_count: int, last_summarized_turn: int = 0) -> bool:
        """Check if conversation should be summarized"""
        turns_since_last = turn_count - last_summarized_turn
        return turns_since_last >= self.summarize_every_n_turns

    def summarize_history(
        self,
        history: List[Dict],
        model_tier: str = "light",
        language: str = "vi",
    ) -> Optional[str]:
        """
        Summarize conversation history.

        Args:
            history: List of turns to summarize
            model_tier: LLM tier to use ("light" or "heavy")
            language: Language for summary

        Returns:
            Summary text or None if summarization fails
        """
        if not history or len(history) < 2:
            return None

        try:
            # Import here to avoid circular dependency
            from app.services.llm_client import get_llm_client

            # Build summarization prompt
            if language == "vi":
                prompt = self._build_vietnamese_summary_prompt(history)
            else:
                prompt = self._build_english_summary_prompt(history)

            # Get LLM client
            llm_client = get_llm_client(tier=model_tier)

            # Generate summary
            response = llm_client.generate(
                prompt=prompt, temperature=0.3, max_tokens=300
            )

            if response and response.content:
                summary = response.content.strip()
                logger.info(
                    f"Summarized {len(history)} turns into {len(summary)} chars"
                )
                return summary

            return None

        except Exception as e:
            logger.error(f"Failed to summarize history: {e}")
            return None

    def create_summary_turn(self, summary: str) -> Dict:
        """Create a system turn containing the summary"""
        return {
            "role": "system",
            "content": f"[Conversation Summary] {summary}",
        }

    def _build_vietnamese_summary_prompt(self, history: List[Dict]) -> str:
        """Build Vietnamese summarization prompt"""
        # Format history
        history_text = ""
        for turn in history:
            role = "Người dùng" if turn["role"] == "user" else "Trợ lý"
            history_text += f"{role}: {turn['content']}\n\n"

        prompt = f"""Hãy tóm tắt cuộc hội thoại sau thành một đoạn ngắn gọn, giữ lại các thông tin quan trọng:

Hội thoại:
{history_text}

Yêu cầu:
- Tóm tắt ngắn gọn (2-3 câu)
- Giữ lại thiết bị/tài liệu được nhắc đến
- Giữ lại các con số/giá trị kỹ thuật quan trọng
- Không thêm thông tin mới

Tóm tắt:"""

        return prompt

    def _build_english_summary_prompt(self, history: List[Dict]) -> str:
        """Build English summarization prompt"""
        # Format history
        history_text = ""
        for turn in history:
            role = "User" if turn["role"] == "user" else "Assistant"
            history_text += f"{role}: {turn['content']}\n\n"

        prompt = f"""Summarize the following conversation concisely, keeping important information:

Conversation:
{history_text}

Requirements:
- Brief summary (2-3 sentences)
- Keep equipment/document references
- Keep important technical numbers/values
- Do not add new information

Summary:"""

        return prompt
