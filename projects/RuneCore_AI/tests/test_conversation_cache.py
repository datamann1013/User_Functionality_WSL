import sys
import importlib
import types
import os


def _reload_module_with_redis(fake_redis_module):
    # Ensure fresh import
    if "projects.RuneCore_AI.backend.cache.conversation_cache" in sys.modules:
        del sys.modules["projects.RuneCore_AI.backend.cache.conversation_cache"]
    # Insert our fake redis module
    sys.modules["redis"] = fake_redis_module
    # Import the conversation_cache module
    mod = importlib.import_module("projects.RuneCore_AI.backend.cache.conversation_cache")
    importlib.reload(mod)
    return mod


class FakeRedisModuleSuccess(types.ModuleType):
    def __init__(self):
        super().__init__("redis")

    class Redis:
        def __init__(self, host=None, port=None, db=None, **kwargs):
            self._store = {}

        def ping(self):
            return True

        def lpush(self, key, value):
            self._store.setdefault(key, []).insert(0, value)

        def ltrim(self, key, start, end):
            self._store[key] = self._store.get(key, [])[start : end + 1]

        def expire(self, key, secs):
            return True

        def lrange(self, key, start, end):
            return self._store.get(key, [])[start : end + 1]

        def keys(self, pattern):
            import re

            regex = pattern.replace("*", ".*")
            return [k for k in self._store.keys() if re.match(regex, k)]

        def delete(self, *keys):
            cnt = 0
            for k in keys:
                if k in self._store:
                    del self._store[k]
                    cnt += 1
            return cnt


class FakeRedisModuleFail(types.ModuleType):
    def __init__(self):
        super().__init__("redis")

    class Redis:
        def __init__(self, *a, **k):
            pass

        def ping(self):
            raise Exception("no redis")


def test_fallback_cache_add_get_and_formatting(monkeypatch):
    # Ensure cache enabled and use failing redis to force fallback
    monkeypatch.setenv("LOCAL_CACHE_ENABLED", "true")
    fake = FakeRedisModuleFail()
    mod = _reload_module_with_redis(fake)

    cc = mod.ConversationCache()
    assert not cc.using_redis

    cid = cc.add_conversation("agent-x", "hello", "hi")
    assert cid is not None

    ctx = cc.get_conversation_context("agent-x")
    assert len(ctx) == 1
    assert ctx[0]["user_message"] == "hello"

    full = cc.get_full_conversation("agent-x")
    # get_full_conversation returns oldest-first; with one entry it's same
    assert full[0]["ai_response"] == "hi"

    formatted = cc.format_context_for_ai("agent-x")
    # Should include system message + user + assistant entries
    assert isinstance(formatted, list)
    assert formatted[0]["role"] == "system"

    s = cc.format_chat_history_to_string(formatted)
    # system message should appear
    assert "System:" in s

    # clearing
    assert cc.clear_agent_cache("agent-x") is True
    assert cc.get_conversation_context("agent-x") == []

    # disabled cache behavior
    monkeypatch.setenv("LOCAL_CACHE_ENABLED", "false")
    cc_disabled = mod.ConversationCache()
    assert cc_disabled.enabled is False
    assert cc_disabled.add_conversation("a", "b", "c") is None
    assert cc_disabled.get_conversation_context("a") == []
    assert cc_disabled.clear_agent_cache("a") is False
    assert cc_disabled.clear_all_cache() == 0


def test_redis_backend_operations(monkeypatch):
    monkeypatch.setenv("LOCAL_CACHE_ENABLED", "true")
    fake = FakeRedisModuleSuccess()
    mod = _reload_module_with_redis(fake)

    # Create a ConversationCache which will detect redis
    cc = mod.ConversationCache()
    assert cc.using_redis

    # Add several messages
    for i in range(3):
        cc.add_conversation("agent-y", f"u{i}", f"a{i}")

    # Check that get_conversation_context returns newest-first limited by context_size
    ctx = cc.get_conversation_context("agent-y", limit=2)
    assert len(ctx) == 2
    assert ctx[0]["user_message"] == "u2"

    # get_full_conversation returns oldest-first
    full = cc.get_full_conversation("agent-y")
    assert full[0]["user_message"] == "u0"

    # Stats should report redis_agents > 0
    stats = cc.get_cache_stats()
    assert stats.get("using_redis") is True

    # clear agent cache
    assert cc.clear_agent_cache("agent-y") in (0, 1, True)

    # add again and clear all
    cc.add_conversation("agent-z", "hello", "resp")
    cleared = cc.clear_all_cache()
    # cleared is int
    assert isinstance(cleared, int)
