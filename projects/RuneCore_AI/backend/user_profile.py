"""
User Profile Manager for RuneCore Mind

Loads and persists a user profile JSON file. The profile is injected
into every agent's system prompt so all agents share context about who
they're talking to.

Profile schema:
{
  "name":        "...",        # display name
  "role":        "...",        # e.g. "developer", "student"
  "projects":    ["..."],      # active projects
  "preferences": {             # misc preferences the AI should respect
    "language": "en",
    "response_style": "concise"
  },
  "facts":       ["..."],      # auto-extracted facts (written by curator)
  "system_context": "...",     # freeform extra context (user-authored)
  "updated_at":  "..."
}

Error codes follow RuneGuard convention:
  Type: E/W/I   Origin: A (AI)   Component: B (Backend)   Sub: P (Profile)
"""
import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional

_PROFILE_PATH = os.environ.get(
    "USER_PROFILE_PATH",
    os.path.join(os.path.dirname(__file__), "data", "user_profile.json"),
)
_DEFAULT_PROFILE: Dict[str, Any] = {
    "name": "",
    "role": "",
    "projects": [],
    "preferences": {
        "language": "en",
        "response_style": "balanced",
    },
    "facts": [],
    "system_context": "",
    "updated_at": "",
}

_lock = threading.RLock()
_cache: Optional[Dict[str, Any]] = None


def _ensure_data_dir() -> None:
    data_dir = os.path.dirname(_PROFILE_PATH)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)


def load() -> Dict[str, Any]:
    """Return the current user profile (cached in-memory after first load)."""
    global _cache
    with _lock:
        if _cache is not None:
            return dict(_cache)
        _ensure_data_dir()
        if not os.path.exists(_PROFILE_PATH):
            _cache = dict(_DEFAULT_PROFILE)
            return dict(_cache)
        try:
            with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults so new fields are populated on old files
            merged = dict(_DEFAULT_PROFILE)
            merged.update(data)
            _cache = merged
            return dict(_cache)
        except (json.JSONDecodeError, OSError):
            _cache = dict(_DEFAULT_PROFILE)
            return dict(_cache)


def save(profile: Dict[str, Any]) -> None:
    """Persist profile to disk and update the in-memory cache."""
    global _cache
    with _lock:
        profile["updated_at"] = datetime.now().isoformat()
        _ensure_data_dir()
        with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        _cache = dict(profile)


def update(partial: Dict[str, Any]) -> Dict[str, Any]:
    """Merge partial dict into the current profile and save."""
    profile = load()
    for key, value in partial.items():
        if key == "preferences" and isinstance(value, dict):
            profile.setdefault("preferences", {}).update(value)
        elif key == "facts" and isinstance(value, list):
            # Append new facts, dedup
            existing = set(profile.get("facts", []))
            for fact in value:
                if fact and fact not in existing:
                    profile["facts"].append(fact)
                    existing.add(fact)
        else:
            profile[key] = value
    save(profile)
    return profile


def add_facts(new_facts: list) -> None:
    """Append extracted facts without overwriting the rest of the profile."""
    if not new_facts:
        return
    update({"facts": new_facts})


def build_system_context_block(profile: Optional[Dict[str, Any]] = None) -> str:
    """
    Return a formatted string block to prepend to any agent's system prompt.
    Returns an empty string if the profile is effectively empty.
    """
    if profile is None:
        profile = load()

    lines = []
    if profile.get("name"):
        lines.append(f"User name: {profile['name']}")
    if profile.get("role"):
        lines.append(f"Role: {profile['role']}")
    if profile.get("projects"):
        lines.append(f"Active projects: {', '.join(profile['projects'])}")
    prefs = profile.get("preferences", {})
    if prefs.get("response_style"):
        lines.append(f"Preferred response style: {prefs['response_style']}")
    if prefs.get("language") and prefs["language"] != "en":
        lines.append(f"Preferred language: {prefs['language']}")
    if profile.get("system_context"):
        lines.append(profile["system_context"])
    if profile.get("facts"):
        facts_block = "\n".join(f"- {f}" for f in profile["facts"][:20])
        lines.append(f"Known facts about the user:\n{facts_block}")

    if not lines:
        return ""

    block = "=== User Context ===\n" + "\n".join(lines) + "\n===================\n"
    return block


def inject_into_system_prompt(base_prompt: str) -> str:
    """
    Prepend user context block to a system prompt.
    If the profile is empty this is a no-op.
    """
    ctx = build_system_context_block()
    if not ctx:
        return base_prompt
    if base_prompt:
        return ctx + "\n" + base_prompt
    return ctx
