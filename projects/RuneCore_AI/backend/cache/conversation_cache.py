#!/usr/bin/env python3
"""
Conversation Cache Module
Redis-based conversation caching with Python dict fallback for AI service
"""
import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
import redis


class ConversationCache:
    """
    Per-agent conversation cache with Redis backend and Python dict fallback

    Features:
    - Per-agent message storage with configurable limits
    - Automatic message rotation (FIFO)
    - Redis backend with graceful fallback to in-memory dict
    - Configurable context window for AI model
    """

    def __init__(self):
        """Initialize conversation cache with Redis backend"""
        self.message_limit = int(os.environ.get("LOCAL_CACHE_MESSAGE_LIMIT", "10"))
        self.context_size = int(os.environ.get("LOCAL_CACHE_CONTEXT_SIZE", "5"))
        self.enabled = os.environ.get("LOCAL_CACHE_ENABLED", "true").lower() == "true"

        # Redis configuration
        self.redis_host = os.environ.get("REDIS_HOST", "localhost")
        self.redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        self.redis_db = int(os.environ.get("REDIS_DB", "0"))

        # Initialize Redis connection
        self.redis_client = None
        self.using_redis = False

        # Fallback to Python dict
        self.fallback_cache = defaultdict(lambda: deque(maxlen=self.message_limit))

        if self.enabled:
            self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection with error handling"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                health_check_interval=30,
            )

            # Test connection
            self.redis_client.ping()
            self.using_redis = True

            print(
                f"✅ Redis cache initialized: {self.redis_host}:{self.redis_port}/{self.redis_db}"
            )

        except Exception as e:
            print(f"⚠️ Redis unavailable, using fallback cache: {e}")
            self.using_redis = False
            self.redis_client = None

    def _get_key(self, agent_id: str) -> str:
        """Generate Redis key for agent conversations"""
        return f"runecore:agent:{agent_id}:messages"

    def add_conversation(
        self, agent_id: str, user_message: str, ai_response: str, model_used: str = "unknown"
    ) -> str:
        """
        Add conversation to cache with automatic rotation

        Args:
            agent_id: ID of the agent
            user_message: User's message
            ai_response: AI's response

        Returns:
            str: Conversation ID
        """
        if not self.enabled:
            try:
                print(f"[ConversationCache] add_conversation skipped (disabled) for {agent_id}")
            except Exception:
                pass
            return None

        conversation_id = str(uuid.uuid4())

        message_obj = {
            "id": conversation_id,
            "user_message": user_message,
            "ai_response": ai_response,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "model_used": model_used,
        }

        if self.using_redis and self.redis_client:
            try:
                cid = self._add_to_redis(agent_id, message_obj)
                try:
                    print(f"[ConversationCache] added to redis {agent_id} id={cid}")
                except Exception:
                    pass
                return cid
            except Exception as e:
                print(f"⚠️ Redis error, falling back to dict: {e}")
                self.using_redis = False
                cid = self._add_to_fallback(agent_id, message_obj)
                try:
                    print(f"[ConversationCache] redis add failed, added to fallback {agent_id} id={cid}")
                except Exception:
                    pass
                return cid
        else:
            cid = self._add_to_fallback(agent_id, message_obj)
            try:
                print(f"[ConversationCache] added to fallback {agent_id} id={cid}")
            except Exception:
                pass
            return cid

    def _add_to_redis(self, agent_id: str, message_obj: Dict) -> str:
        """Add message to Redis with rotation"""
        key = self._get_key(agent_id)

        # Add to the beginning of the list (newest first)
        self.redis_client.lpush(key, json.dumps(message_obj))

        # Trim list to maintain size limit
        self.redis_client.ltrim(key, 0, self.message_limit - 1)

        # Set expiration (optional - for memory management)
        self.redis_client.expire(key, 3600 * 24)  # 24 hours

        return message_obj["id"]

    def _add_to_fallback(self, agent_id: str, message_obj: Dict) -> str:
        """Add message to fallback Python dict"""
        # Deque automatically handles rotation with maxlen
        self.fallback_cache[agent_id].appendleft(message_obj)
        return message_obj["id"]

    def get_conversation_context(
        self, agent_id: str, limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get conversation context for AI model

        Args:
            agent_id: ID of the agent
            limit: Optional message limit (defaults to context_size)

        Returns:
            List[Dict]: Recent messages (newest first)
        """
        if not self.enabled:
            return []

        if limit is None:
            limit = self.context_size

        if self.using_redis and self.redis_client:
            try:
                return self._get_from_redis(agent_id, limit)
            except Exception as e:
                print(f"⚠️ Redis error, using fallback: {e}")
                self.using_redis = False
                return self._get_from_fallback(agent_id, limit)
        else:
            return self._get_from_fallback(agent_id, limit)

    def _get_from_redis(self, agent_id: str, limit: int) -> List[Dict]:
        """Get messages from Redis"""
        key = self._get_key(agent_id)
        raw_messages = self.redis_client.lrange(key, 0, limit - 1)
        parsed = []
        for i, msg in enumerate(raw_messages):
            try:
                parsed.append(json.loads(msg))
            except Exception as e:
                # Skip malformed entries but surface a short diagnostic to stdout
                try:
                    print(f"⚠️ Skipping malformed cached message for agent {agent_id} at index {i}: {e}")
                except Exception:
                    pass
                continue
        return parsed

    def _get_from_fallback(self, agent_id: str, limit: int) -> List[Dict]:
        """Get messages from fallback cache"""
        if agent_id not in self.fallback_cache:
            return []

        messages = list(self.fallback_cache[agent_id])
        return messages[:limit]

    def get_full_conversation(self, agent_id: str) -> List[Dict]:
        """Get all cached messages for an agent in chronological order (oldest first)"""
        if self.using_redis and self.redis_client:
            try:
                key = self._get_key(agent_id)
                raw = self.redis_client.lrange(key, 0, self.message_limit - 1)
                parsed = []
                for i, m in enumerate(raw):
                    try:
                        parsed.append(json.loads(m))
                    except Exception as e:
                        try:
                            print(f"⚠️ Skipping malformed cached message for agent {agent_id} at index {i}: {e}")
                        except Exception:
                            pass
                        continue
                return list(reversed(parsed))
            except Exception as e:
                print(f"⚠️ Redis error in get_full_conversation: {e}")
                self.using_redis = False
        # fallback
        messages = list(self.fallback_cache[agent_id]) if agent_id in self.fallback_cache else []
        return list(reversed(messages))

    def clear_agent_cache(self, agent_id: str) -> bool:
        """Clear conversation cache for specific agent"""
        if not self.enabled:
            return False

        if self.using_redis and self.redis_client:
            try:
                key = self._get_key(agent_id)
                return self.redis_client.delete(key) > 0
            except Exception:
                pass

        # Clear from fallback cache
        if agent_id in self.fallback_cache:
            self.fallback_cache[agent_id].clear()
            return True

        return False

    def clear_all_cache(self) -> int:
        """Clear all conversation caches"""
        if not self.enabled:
            return 0

        cleared_count = 0

        if self.using_redis and self.redis_client:
            try:
                # Find all agent keys
                pattern = "runecore:agent:*:messages"
                keys = self.redis_client.keys(pattern)
                if keys:
                    cleared_count = self.redis_client.delete(*keys)
            except Exception:
                pass

        # Clear fallback cache
        fallback_count = len(self.fallback_cache)
        self.fallback_cache.clear()

        return cleared_count + fallback_count

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and status"""
        stats = {
            "enabled": self.enabled,
            "using_redis": self.using_redis,
            "message_limit": self.message_limit,
            "context_size": self.context_size,
            "fallback_agents": len(self.fallback_cache),
        }

        if self.using_redis and self.redis_client:
            try:
                # Count Redis keys
                pattern = "runecore:agent:*:messages"
                redis_keys = len(self.redis_client.keys(pattern))
                stats["redis_agents"] = redis_keys
                stats["redis_info"] = {
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "db": self.redis_db,
                }
            except Exception as e:
                stats["redis_error"] = str(e)

        return stats

    def format_context_for_ai(self, agent_id: str) -> List[Dict]:
        """
        Format conversation context as structured list for AI model

        Returns conversation history in proper chat format using role-based structure
        """
        messages = self.get_conversation_context(agent_id)

        if not messages:
            return []

        # Convert to proper chat format with role-based structure
        chat_history = []

        # Add system message first
        chat_history.append(
            {
                "role": "system",
                "content": "You are a helpful AI assistant. Provide clear, conversational responses.",
            }
        )

        # Add conversation history in chronological order (oldest first)
        for msg in reversed(messages):  # Reverse because Redis stores newest-first
            chat_history.append({"role": "user", "content": msg["user_message"]})
            chat_history.append({"role": "assistant", "content": msg["ai_response"]})

        return chat_history

    def format_chat_history_to_string(self, chat_history: List[Dict]) -> str:
        """
        Convert structured chat history to string format for Ollama
        Using a simple, clean format that won't trigger content filters
        """
        if not chat_history:
            return ""

        formatted_lines = []

        for message in chat_history:
            role = message["role"]
            content = message["content"]

            if role == "system":
                formatted_lines.append(f"System: {content}")
            elif role == "user":
                formatted_lines.append(f"User: {content}")
            elif role == "assistant":
                formatted_lines.append(f"Assistant: {content}")

        return "\n\n".join(formatted_lines)


# Global cache instance - initialized when imported
conversation_cache = ConversationCache()
