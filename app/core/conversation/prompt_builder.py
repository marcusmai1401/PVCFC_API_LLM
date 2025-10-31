"""
Build conversation-aware prompts with history context.
"""

from typing import Dict, List, Optional

from loguru import logger


def build_conversation_aware_prompt(
    current_query: str,
    history: List[Dict],
    retrieved_docs: List,
    language: str = "vi",
    summary: Optional[str] = None,
) -> str:
    """
    Build prompt with conversation context.

    Args:
        current_query: Current user query
        history: Recent conversation turns
        retrieved_docs: Retrieved context documents
        language: Language for instructions
        summary: Optional conversation summary

    Returns:
        Complete prompt with conversation context
    """
    # Build context from retrieved documents
    context_parts = []
    for i, doc in enumerate(retrieved_docs[:8], 1):
        page_info = f" (Page {doc.page})" if hasattr(doc, "page") and doc.page else ""
        text = doc.text if hasattr(doc, "text") else str(doc)
        context_parts.append(f"[Doc {i}]{page_info}\n{text}")

    context = "\n---\n".join(context_parts)

    # Build conversation history section
    history_section = ""
    if summary:
        # If we have a summary, use it first
        history_section = f"\n## Conversation Summary:\n{summary}\n"

    if history and len(history) > 0:
        history_section += "\n## Recent Conversation:\n"
        # Show last 6 turns (3 exchanges)
        for turn in history[-6:]:
            role_label = "User" if turn["role"] == "user" else "Assistant"
            history_section += f"{role_label}: {turn['content']}\n\n"

    # Instruction based on language
    if language == "vi":
        instruction = """Dựa trên tài liệu và lịch sử hội thoại, trả lời câu hỏi hiện tại.

**Hướng dẫn:**
- Nếu câu hỏi đề cập đến "nó", "cái đó", "thiết bị trên", "tài liệu vừa rồi" → suy luận từ ngữ cảnh trước
- Trích dẫn nguồn dạng [Doc N, p.X]
- Chỉ sử dụng thông tin từ tài liệu được cung cấp
- Trả lời ngắn gọn, chính xác"""
    else:
        instruction = """Based on the documents and conversation history, answer the current question.

**Instructions:**
- If question refers to "it", "that", "the equipment", "the document" → infer from previous context
- Include citations as [Doc N, p.X]
- Only use information from provided documents
- Answer concisely and accurately"""

    # Assemble final prompt
    prompt = f"""{instruction}

## Context Documents:
{context}
{history_section}

## Current Question:
{current_query}

## Answer:"""

    logger.debug(
        f"Built conversation-aware prompt: "
        f"{len(context)} chars context, "
        f"{len(history) if history else 0} history turns, "
        f"summary={'yes' if summary else 'no'}"
    )

    return prompt
