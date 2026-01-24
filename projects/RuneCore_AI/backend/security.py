#!/usr/bin/env python3
"""
Security utilities for RuneCore AI

Provides:
- Rate limiting per agent and globally
- Input sanitization for chat messages
- Request validation

Error codes follow RuneGuard convention:
- Type: E(rror), W(arning), I(nfo)
- Origin: A (AI Service)
- Component: B (Backend)
- Subcomponent: S (Security)
- Number: 00-99
"""
import os
import re
import html
import time
import threading
from typing import Dict, Optional, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from flask import request, jsonify


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    # Per-agent limits
    requests_per_minute: int = 20
    requests_per_hour: int = 200

    # Global limits
    global_requests_per_minute: int = 100
    global_requests_per_hour: int = 1000

    # Burst allowance (allows temporary spikes)
    burst_allowance: int = 5


@dataclass
class RateLimitEntry:
    """Tracks request timestamps for rate limiting"""
    timestamps: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    """
    Thread-safe rate limiter with per-agent and global limits.

    Implements a sliding window rate limiting algorithm.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig(
            requests_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20")),
            requests_per_hour=int(os.environ.get("RATE_LIMIT_PER_HOUR", "200")),
            global_requests_per_minute=int(os.environ.get("RATE_LIMIT_GLOBAL_PER_MINUTE", "100")),
            global_requests_per_hour=int(os.environ.get("RATE_LIMIT_GLOBAL_PER_HOUR", "1000")),
            burst_allowance=int(os.environ.get("RATE_LIMIT_BURST", "5")),
        )

        # Per-agent tracking
        self._agent_limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

        # Global tracking
        self._global_limit = RateLimitEntry()

        # Lock for creating new entries
        self._entries_lock = threading.Lock()

    def _clean_old_timestamps(self, entry: RateLimitEntry, window_seconds: int):
        """Remove timestamps older than the window"""
        now = time.time()
        cutoff = now - window_seconds
        entry.timestamps = [ts for ts in entry.timestamps if ts > cutoff]

    def check_rate_limit(self, agent_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a request should be allowed.

        Returns (allowed, error_message)
        """
        now = time.time()

        # Check per-agent limits
        with self._entries_lock:
            if agent_id not in self._agent_limits:
                self._agent_limits[agent_id] = RateLimitEntry()

        entry = self._agent_limits[agent_id]
        with entry.lock:
            # Clean old timestamps
            self._clean_old_timestamps(entry, 3600)  # Keep last hour

            # Count recent requests
            minute_ago = now - 60
            hour_ago = now - 3600

            minute_count = sum(1 for ts in entry.timestamps if ts > minute_ago)
            hour_count = len(entry.timestamps)

            # Check minute limit (with burst)
            if minute_count >= self.config.requests_per_minute + self.config.burst_allowance:
                return False, f"Rate limit exceeded: {minute_count} requests in the last minute (limit: {self.config.requests_per_minute})"

            # Check hour limit
            if hour_count >= self.config.requests_per_hour:
                return False, f"Rate limit exceeded: {hour_count} requests in the last hour (limit: {self.config.requests_per_hour})"

            # Record this request
            entry.timestamps.append(now)

        # Check global limits
        with self._global_limit.lock:
            self._clean_old_timestamps(self._global_limit, 3600)

            minute_ago = now - 60
            minute_count = sum(1 for ts in self._global_limit.timestamps if ts > minute_ago)
            hour_count = len(self._global_limit.timestamps)

            if minute_count >= self.config.global_requests_per_minute:
                return False, "Global rate limit exceeded. Please try again later."

            if hour_count >= self.config.global_requests_per_hour:
                return False, "Global rate limit exceeded. Please try again later."

            self._global_limit.timestamps.append(now)

        return True, None

    def get_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limiting statistics"""
        now = time.time()
        stats = {}

        if agent_id:
            with self._entries_lock:
                if agent_id in self._agent_limits:
                    entry = self._agent_limits[agent_id]
                    with entry.lock:
                        minute_ago = now - 60
                        stats["agent"] = {
                            "requests_last_minute": sum(1 for ts in entry.timestamps if ts > minute_ago),
                            "requests_last_hour": len([ts for ts in entry.timestamps if ts > now - 3600]),
                            "limit_per_minute": self.config.requests_per_minute,
                            "limit_per_hour": self.config.requests_per_hour,
                        }

        with self._global_limit.lock:
            minute_ago = now - 60
            stats["global"] = {
                "requests_last_minute": sum(1 for ts in self._global_limit.timestamps if ts > minute_ago),
                "requests_last_hour": len([ts for ts in self._global_limit.timestamps if ts > now - 3600]),
                "limit_per_minute": self.config.global_requests_per_minute,
                "limit_per_hour": self.config.global_requests_per_hour,
            }

        return stats


class InputSanitizer:
    """
    Sanitizes user input to prevent injection attacks and ensure safe processing.

    Handles:
    - XSS prevention (HTML encoding)
    - Prompt injection mitigation
    - Length limits
    - Character filtering
    """

    def __init__(self):
        # Maximum message length (characters)
        self.max_message_length = int(os.environ.get("MAX_MESSAGE_LENGTH", "10000"))

        # Maximum system prompt length
        self.max_system_prompt_length = int(os.environ.get("MAX_SYSTEM_PROMPT_LENGTH", "2000"))

        # Patterns that might indicate prompt injection attempts
        self._suspicious_patterns = [
            # Attempting to override system behavior
            r"ignore\s+(all\s+)?(previous\s+)?instructions?",
            r"disregard\s+(all\s+)?(previous\s+)?instructions?",
            r"forget\s+(all\s+)?(previous\s+)?instructions?",
            # Attempting to extract system prompt
            r"(print|show|display|reveal)\s+(your\s+)?(system\s+)?prompt",
            r"what\s+(is|are)\s+your\s+(system\s+)?instructions?",
            # Attempting role play as system
            r"^system:\s*",
            r"^\[system\]",
        ]

        # Compile patterns for efficiency
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self._suspicious_patterns
        ]

    def sanitize_message(self, message: str) -> Tuple[str, list]:
        """
        Sanitize a user message.

        Returns (sanitized_message, warnings)
        """
        warnings = []

        if not message:
            return "", warnings

        # Truncate if too long
        if len(message) > self.max_message_length:
            message = message[:self.max_message_length]
            warnings.append(f"Message truncated to {self.max_message_length} characters")

        # Strip control characters (except newlines and tabs)
        message = ''.join(
            char for char in message
            if char in '\n\t' or (ord(char) >= 32 and ord(char) != 127)
        )

        # Check for suspicious patterns
        for pattern in self._compiled_patterns:
            if pattern.search(message):
                warnings.append("WABS01: Potentially suspicious input pattern detected")
                break

        # Don't modify the message content beyond basic cleanup
        # Let the AI handle natural language - just ensure it's safe to process
        return message.strip(), warnings

    def sanitize_agent_name(self, name: str) -> str:
        """Sanitize an agent name"""
        if not name:
            return ""

        # Limit length
        name = name[:50]

        # Remove HTML
        name = html.escape(name)

        # Allow only alphanumeric, spaces, hyphens, underscores
        name = re.sub(r'[^\w\s\-]', '', name)

        return name.strip()

    def sanitize_system_prompt(self, prompt: str) -> Tuple[str, list]:
        """Sanitize a system prompt"""
        warnings = []

        if not prompt:
            return "", warnings

        # Truncate if too long
        if len(prompt) > self.max_system_prompt_length:
            prompt = prompt[:self.max_system_prompt_length]
            warnings.append(f"System prompt truncated to {self.max_system_prompt_length} characters")

        # Strip control characters
        prompt = ''.join(
            char for char in prompt
            if char in '\n\t' or (ord(char) >= 32 and ord(char) != 127)
        )

        return prompt.strip(), warnings

    def validate_model_name(self, model_name: str) -> Tuple[bool, Optional[str]]:
        """Validate a model name"""
        if not model_name:
            return False, "Model name is required"

        # Limit length
        if len(model_name) > 100:
            return False, "Model name too long"

        # Allow only safe characters
        if not re.match(r'^[\w\.\:\-]+$', model_name):
            return False, "Invalid characters in model name"

        return True, None

    def validate_agent_id(self, agent_id: str) -> Tuple[bool, Optional[str]]:
        """Validate an agent ID (UUID format)"""
        if not agent_id:
            return False, "Agent ID is required"

        # UUID format validation
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, agent_id.lower()):
            return False, "Invalid agent ID format"

        return True, None

    def sanitize_for_log(self, text: str, max_length: int = 200) -> str:
        """Sanitize text for logging (prevent log injection)"""
        if not text:
            return ""

        # Remove newlines and control characters
        text = re.sub(r'[\r\n\x00-\x1f]', ' ', text)

        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text


# Global instances
rate_limiter = RateLimiter()
input_sanitizer = InputSanitizer()


def rate_limit_decorator(get_agent_id=None):
    """
    Decorator to apply rate limiting to Flask routes.

    Args:
        get_agent_id: Optional function to extract agent_id from request.
                     If None, uses request.json.get("agent_id", "anonymous")
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract agent_id
            if get_agent_id:
                agent_id = get_agent_id()
            else:
                try:
                    data = request.get_json() or {}
                    agent_id = data.get("agent_id", "anonymous")
                except Exception:
                    agent_id = "anonymous"

            # Check rate limit
            allowed, error_msg = rate_limiter.check_rate_limit(agent_id)

            if not allowed:
                return jsonify({
                    "error": "Rate limit exceeded",
                    "error_code": "EABS01",
                    "message": error_msg,
                }), 429

            return f(*args, **kwargs)

        return decorated_function
    return decorator
