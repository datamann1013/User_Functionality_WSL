#!/usr/bin/env python3
"""
Model Manager for RuneCore AI

Provides model management functionality including:
- Listing available models from Ollama
- Model download/pull operations
- Model deletion
- Model status monitoring

Error codes follow RuneGuard convention:
- Type: E(rror), W(arning), I(nfo)
- Origin: A (AI Service)
- Component: B (Backend)
- Subcomponent: M (Model)
- Number: 00-99
"""
import os
import requests
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """Information about an available model"""
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None
    digest: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class PullStatus:
    """Status of a model pull operation"""
    model: str
    status: str  # "started", "pulling", "completed", "failed", "cancelled"
    progress: int = 0  # 0-100
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None
    output: str = ""


class ModelManager:
    """
    Manages AI models through the Ollama service.

    Provides a clean interface for model operations that can be used
    by the backend API endpoints.
    """

    def __init__(self, ollama_service_url: Optional[str] = None):
        self.ollama_url = ollama_service_url or os.environ.get(
            "OLLAMA_SERVICE_URL", "http://127.0.0.1:5002"
        )

        # Cache for model list
        self._model_cache: List[ModelInfo] = []
        self._cache_time: float = 0
        self._cache_ttl: float = 30.0  # seconds

        # Track active pulls
        self._active_pulls: Dict[str, PullStatus] = {}
        self._pulls_lock = threading.Lock()

    def list_models(self, force_refresh: bool = False) -> List[ModelInfo]:
        """
        List available models from Ollama.

        Returns cached results unless force_refresh is True or cache is expired.
        """
        now = time.time()

        if not force_refresh and self._model_cache and (now - self._cache_time) < self._cache_ttl:
            return self._model_cache

        try:
            response = requests.get(
                f"{self.ollama_url}/api/models",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                models_data = data.get("models", [])

                self._model_cache = []
                for m in models_data:
                    if isinstance(m, dict):
                        self._model_cache.append(ModelInfo(
                            name=m.get("name", "unknown"),
                            size=m.get("size"),
                            modified_at=m.get("modified_at"),
                            digest=m.get("digest"),
                            details=m.get("details"),
                        ))
                    elif isinstance(m, str):
                        self._model_cache.append(ModelInfo(name=m))

                self._cache_time = now
                return self._model_cache
            else:
                # Return cached data if available, otherwise empty list
                return self._model_cache if self._model_cache else []

        except Exception as e:
            print(f"[WABM01] Failed to fetch models: {e}")
            return self._model_cache if self._model_cache else []

    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a specific model"""
        models = self.list_models()
        for model in models:
            if model.name == model_name:
                return model
        return None

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available locally"""
        models = self.list_models(force_refresh=True)
        return any(m.name == model_name for m in models)

    def pull_model(self, model_name: str) -> PullStatus:
        """
        Initiate a model pull/download.

        Returns immediately with a PullStatus that can be polled.
        """
        with self._pulls_lock:
            # Check if already pulling
            if model_name in self._active_pulls:
                existing = self._active_pulls[model_name]
                if existing.status in ("started", "pulling"):
                    return existing

        # Start the pull
        status = PullStatus(
            model=model_name,
            status="started",
        )

        with self._pulls_lock:
            self._active_pulls[model_name] = status

        # Initiate pull through ollama service
        try:
            response = requests.post(
                f"{self.ollama_url}/api/pull",
                json={"name": model_name},
                timeout=10
            )

            if response.status_code in (200, 202):
                status.status = "pulling"
                status.last_update = datetime.now().isoformat()

                # Start background monitoring
                self._start_pull_monitor(model_name)
            else:
                status.status = "failed"
                status.error = f"Failed to initiate pull: HTTP {response.status_code}"
                status.last_update = datetime.now().isoformat()

        except Exception as e:
            status.status = "failed"
            status.error = str(e)
            status.last_update = datetime.now().isoformat()

        return status

    def _start_pull_monitor(self, model_name: str):
        """Start a background thread to monitor pull progress"""
        def monitor():
            while True:
                with self._pulls_lock:
                    if model_name not in self._active_pulls:
                        return
                    status = self._active_pulls[model_name]
                    if status.status in ("completed", "failed", "cancelled"):
                        return

                # Check if model is now available
                if self.is_model_available(model_name):
                    with self._pulls_lock:
                        if model_name in self._active_pulls:
                            self._active_pulls[model_name].status = "completed"
                            self._active_pulls[model_name].progress = 100
                            self._active_pulls[model_name].last_update = datetime.now().isoformat()
                    return

                # Try to get progress from ollama service
                try:
                    response = requests.get(
                        f"{self.ollama_url}/api/pulls/{model_name}",
                        timeout=5
                    )
                    if response.status_code == 200:
                        data = response.json()
                        with self._pulls_lock:
                            if model_name in self._active_pulls:
                                self._active_pulls[model_name].progress = data.get("progress", 0)
                                self._active_pulls[model_name].last_update = datetime.now().isoformat()
                                if data.get("status") == "completed":
                                    self._active_pulls[model_name].status = "completed"
                                    return
                                elif data.get("status") == "failed":
                                    self._active_pulls[model_name].status = "failed"
                                    self._active_pulls[model_name].error = data.get("error")
                                    return
                except Exception:
                    pass

                time.sleep(2.0)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def get_pull_status(self, model_name: str) -> Optional[PullStatus]:
        """Get the status of a model pull operation"""
        with self._pulls_lock:
            return self._active_pulls.get(model_name)

    def list_active_pulls(self) -> Dict[str, PullStatus]:
        """List all active pull operations"""
        with self._pulls_lock:
            return dict(self._active_pulls)

    def cancel_pull(self, model_name: str) -> bool:
        """Cancel an active pull operation"""
        with self._pulls_lock:
            if model_name in self._active_pulls:
                self._active_pulls[model_name].status = "cancelled"
                self._active_pulls[model_name].last_update = datetime.now().isoformat()
                return True
        return False

    def delete_model(self, model_name: str) -> bool:
        """
        Delete a model from Ollama.

        Returns True if deletion was successful.
        """
        try:
            # Try the delete endpoint
            response = requests.delete(
                f"{self.ollama_url}/api/models/{model_name}",
                timeout=30
            )

            if response.status_code in (200, 204):
                # Invalidate cache
                self._cache_time = 0
                return True

            # Try alternative endpoint
            response = requests.post(
                f"{self.ollama_url}/api/delete",
                json={"name": model_name},
                timeout=30
            )

            if response.status_code in (200, 204):
                self._cache_time = 0
                return True

            return False

        except Exception as e:
            print(f"[EABM02] Failed to delete model {model_name}: {e}")
            return False

    def get_model_details(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a model"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/show",
                json={"name": model_name},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception:
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get model manager statistics"""
        models = self.list_models()

        with self._pulls_lock:
            active_pulls = len([
                p for p in self._active_pulls.values()
                if p.status in ("started", "pulling")
            ])

        return {
            "total_models": len(models),
            "active_pulls": active_pulls,
            "cache_age_seconds": time.time() - self._cache_time if self._cache_time else None,
            "ollama_url": self.ollama_url,
        }


# Global singleton instance
model_manager = ModelManager()
