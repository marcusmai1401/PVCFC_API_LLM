"""
Production-grade conversation manager with Redis persistence.

Features:
- Redis persistence (survive restarts)
- Horizontal scaling (shared state)
- TTL management (auto cleanup)
- Vendor-agnostic (works with any LLM)
- Analytics-ready (export conversations)
- Smart history truncation (context window management)
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import redis
from loguru import logger

from app.core.redis_client import get_redis


@dataclass
class ConversationTurn:
    """Single turn in conversation"""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str
    metadata: Optional[Dict] = None  # citations, model, latency, etc.


@dataclass
class ConversationMetadata:
    """Conversation-level metadata"""

    conversation_id: str
    created_at: str
    last_updated: str
    user_id: Optional[str] = None
    language: str = "vi"
    total_turns: int = 0
    last_summarized_turn: int = 0


class ConversationManager:
    """
    Production-grade conversation manager.

    Features:
    - Redis persistence (survive restarts)
    - Horizontal scaling (shared state)
    - TTL management (auto cleanup)
    - Vendor-agnostic (works with any LLM)
    - Analytics-ready (export conversations)
    - Smart history truncation (context window management)
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",  # Deprecated, kept for backward compatibility
        redis_password: Optional[
            str
        ] = None,  # Deprecated, kept for backward compatibility
        ttl_hours: int = 24,
        max_turns_per_conversation: int = 50,
        max_context_tokens: int = 8000,
    ):
        self.ttl = ttl_hours * 3600  # Convert to seconds
        self.max_turns = max_turns_per_conversation
        self.max_context_tokens = max_context_tokens

        # Use Redis client factory for HA support
        # Legacy redis_url and redis_password parameters are ignored
        # Configuration now comes from app.core.config settings
        try:
            self.redis = get_redis(read_only=False)
            # Test connection
            self.redis.ping()
            logger.info(
                f"ConversationManager initialized with Redis factory: "
                f"TTL={ttl_hours}h, max_turns={max_turns_per_conversation}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis via factory: {e}")
            raise

        # Register Lua script for atomic add_turn operation
        # This prevents race conditions when multiple requests add turns simultaneously
        self.add_turn_script = self.redis.register_script(
            """
            local history_key = KEYS[1]
            local meta_key = KEYS[2]
            local turn_data = ARGV[1]
            local ttl = tonumber(ARGV[2])
            local max_turns = tonumber(ARGV[3])
            local timestamp = ARGV[4]

            -- Add turn to history
            redis.call('RPUSH', history_key, turn_data)
            redis.call('EXPIRE', history_key, ttl)

            -- Get current length
            local length = redis.call('LLEN', history_key)

            -- Trim if exceeds max_turns
            if length > max_turns then
                local excess = length - max_turns
                redis.call('LTRIM', history_key, excess, -1)
                length = max_turns
            end

            -- Update metadata atomically
            local meta = redis.call('GET', meta_key)
            if meta then
                local meta_obj = cjson.decode(meta)
                meta_obj['last_updated'] = timestamp
                meta_obj['total_turns'] = length
                redis.call('SET', meta_key, cjson.encode(meta_obj), 'EX', ttl)
            end

            return length
        """
        )

    def create_conversation(
        self, user_id: Optional[str] = None, language: str = "vi"
    ) -> str:
        """Create new conversation and return ID"""
        conv_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        metadata = ConversationMetadata(
            conversation_id=conv_id,
            created_at=now,
            last_updated=now,
            user_id=user_id,
            language=language,
            total_turns=0,
            last_summarized_turn=0,
        )

        # Store metadata
        try:
            self.redis.set(
                f"conv:meta:{conv_id}", json.dumps(asdict(metadata)), ex=self.ttl
            )
            logger.info(f"Created conversation {conv_id}")
            return conv_id
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise

    def add_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Add turn to conversation using atomic Lua script.

        RACE CONDITION FIX:
        Previously used 4 separate Redis operations (rpush, expire, update_meta, trim),
        which could interleave with concurrent requests causing:
        - Incorrect turn counts
        - Lost turns
        - TTL race conditions

        Now uses single atomic Lua script for all operations.
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            turn = ConversationTurn(
                role=role,
                content=content,
                timestamp=timestamp,
                metadata=metadata or {},
            )

            history_key = f"conv:history:{conversation_id}"
            meta_key = f"conv:meta:{conversation_id}"

            # Execute atomic Lua script
            # All operations (rpush, expire, trim, update_meta) happen atomically
            result_length = self.add_turn_script(
                keys=[history_key, meta_key],
                args=[
                    json.dumps(asdict(turn)),  # turn_data
                    self.ttl,  # ttl
                    self.max_turns,  # max_turns
                    timestamp,  # timestamp for metadata
                ],
            )

            logger.debug(
                f"Added {role} turn to {conversation_id}, "
                f"total turns: {result_length}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to add turn to {conversation_id}: {e}")
            return False

    def get_history(
        self,
        conversation_id: str,
        max_turns: Optional[int] = None,
        include_metadata: bool = False,
    ) -> List[Dict]:
        """
        Get conversation history.

        Args:
            conversation_id: Conversation ID
            max_turns: Limit to N most recent turns (default: all)
            include_metadata: Include turn-level metadata

        Returns:
            List of turns (newest last)
        """
        try:
            history_key = f"conv:history:{conversation_id}"

            # Get all or limited turns
            if max_turns:
                raw_turns = self.redis.lrange(history_key, -max_turns, -1)
            else:
                raw_turns = self.redis.lrange(history_key, 0, -1)

            turns = [json.loads(t) for t in raw_turns]

            # Strip metadata if not requested
            if not include_metadata:
                turns = [{"role": t["role"], "content": t["content"]} for t in turns]

            return turns

        except Exception as e:
            logger.error(f"Failed to get history for {conversation_id}: {e}")
            return []

    def get_metadata(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation metadata"""
        try:
            meta_key = f"conv:meta:{conversation_id}"
            raw_meta = self.redis.get(meta_key)
            if raw_meta:
                return json.loads(raw_meta)
            return None
        except Exception as e:
            logger.error(f"Failed to get metadata for {conversation_id}: {e}")
            return None

    def update_summarization_marker(
        self, conversation_id: str, turn_count: int
    ) -> bool:
        """Update last_summarized_turn marker"""
        try:
            meta_key = f"conv:meta:{conversation_id}"
            raw_meta = self.redis.get(meta_key)
            if raw_meta:
                meta = json.loads(raw_meta)
                meta["last_summarized_turn"] = turn_count
                meta["last_updated"] = datetime.utcnow().isoformat()
                self.redis.set(meta_key, json.dumps(meta), ex=self.ttl)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update summarization marker: {e}")
            return False

    def clear_conversation(self, conversation_id: str) -> bool:
        """Delete conversation"""
        try:
            self.redis.delete(f"conv:history:{conversation_id}")
            self.redis.delete(f"conv:meta:{conversation_id}")
            logger.info(f"Cleared conversation {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear {conversation_id}: {e}")
            return False

    def list_user_conversations(self, user_id: str) -> List[Dict]:
        """List all conversations for a user"""
        try:
            # Scan all metadata keys
            conversations = []
            for key in self.redis.scan_iter("conv:meta:*"):
                meta = json.loads(self.redis.get(key))
                if meta.get("user_id") == user_id:
                    conversations.append(meta)

            # Sort by last_updated (newest first)
            conversations.sort(key=lambda x: x["last_updated"], reverse=True)
            return conversations

        except Exception as e:
            logger.error(f"Failed to list conversations for {user_id}: {e}")
            return []

    def build_llm_history(
        self, conversation_id: str, max_turns: int = 10, format: str = "openai"
    ) -> List[Dict]:
        """
        Build LLM-compatible history format.
        Vendor-agnostic with format conversion.
        """
        turns = self.get_history(conversation_id, max_turns=max_turns)

        if format == "openai":
            # OpenAI format: {"role": "user|assistant", "content": "..."}
            return [
                {
                    "role": t["role"] if t["role"] != "assistant" else "assistant",
                    "content": t["content"],
                }
                for t in turns
            ]

        elif format == "gemini":
            # Gemini format: {"role": "user|model", "parts": ["..."]}
            return [
                {
                    "role": "user" if t["role"] == "user" else "model",
                    "parts": [t["content"]],
                }
                for t in turns
            ]

        elif format == "anthropic":
            # Anthropic format: {"role": "user|assistant", "content": "..."}
            return [{"role": t["role"], "content": t["content"]} for t in turns]

        else:
            # Generic format
            return turns

    def health_check(self) -> Dict:
        """Check Redis connection and stats"""
        try:
            self.redis.ping()

            # Count total conversations
            total_convs = len(list(self.redis.scan_iter("conv:meta:*")))

            return {
                "status": "healthy",
                "redis_connected": True,
                "total_conversations": total_convs,
                "ttl_hours": self.ttl / 3600,
            }
        except Exception as e:
            return {"status": "unhealthy", "redis_connected": False, "error": str(e)}

    # NOTE: _update_conversation_metadata and _trim_if_needed have been removed
    # These operations are now handled atomically by the Lua script in add_turn()
    # to prevent race conditions in concurrent requests
