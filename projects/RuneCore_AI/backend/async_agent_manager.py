#!/usr/bin/env python3
"""
Async Multi-Agent Manager for RuneCore AI

Provides true concurrent processing for multiple AI agents, allowing
independent request handling without blocking other agents.

Error codes follow RuneGuard convention:
- Type: E(rror), W(arning), I(nfo)
- Origin: A (AI Service)
- Component: B (Backend)
- Subcomponent: A (Async/Agent Manager)
- Number: 00-99
"""
import os
import uuid
import asyncio
import threading
import time
import json
import requests
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from queue import PriorityQueue
import heapq


class RequestStatus(Enum):
    """Status states for async requests"""
    SUBMITTED = "submitted"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class AgentRequest:
    """Represents an async chat request"""
    request_id: str
    agent_id: str
    user_id: str
    message: str
    priority: int = 0
    timeout: float = 60.0
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: RequestStatus = RequestStatus.SUBMITTED

    def __lt__(self, other):
        """For priority queue ordering (lower priority number = higher priority)"""
        return self.priority < other.priority


@dataclass
class AgentResponse:
    """Represents a completed response"""
    request_id: str
    agent_id: str
    user_id: str
    message: str
    response: Optional[str] = None
    status: RequestStatus = RequestStatus.COMPLETED
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    processing_time: float = 0.0
    model_used: Optional[str] = None
    tokens_used: int = 0
    error_message: Optional[str] = None
    error_code: Optional[str] = None


class AgentWorker:
    """
    Worker that processes requests for a specific agent.
    Each agent gets its own worker to enable true concurrency.
    """

    def __init__(self, agent_id: str, ollama_url: str, agent_config: Dict[str, Any]):
        self.agent_id = agent_id
        self.ollama_url = ollama_url
        self.agent_config = agent_config
        self.request_queue: asyncio.Queue = None
        self.is_running = False
        self.current_request: Optional[AgentRequest] = None
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the worker processing loop"""
        if self.is_running:
            return

        self.request_queue = asyncio.Queue()
        self.is_running = True
        self._worker_task = asyncio.create_task(self._process_loop())

    async def stop(self):
        """Stop the worker gracefully"""
        self.is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def submit(self, request: AgentRequest):
        """Submit a request to this worker's queue"""
        if not self.is_running:
            await self.start()
        await self.request_queue.put(request)

    async def _process_loop(self):
        """Main processing loop for this agent"""
        while self.is_running:
            try:
                # Wait for a request with timeout to allow graceful shutdown
                try:
                    request = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                async with self._lock:
                    self.current_request = request

                try:
                    await self._process_request(request)
                except Exception as e:
                    # Log but don't crash the worker
                    print(f"[EABA01] Agent {self.agent_id} request processing error: {e}")
                finally:
                    async with self._lock:
                        self.current_request = None
                    self.request_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[EABA02] Agent {self.agent_id} worker loop error: {e}")
                await asyncio.sleep(0.1)

    async def _process_request(self, request: AgentRequest):
        """Process a single request through Ollama"""
        start_time = time.time()

        # Update status
        request.status = RequestStatus.PROCESSING

        try:
            # Build the Ollama payload
            model_name = self.agent_config.get("model_name", "llama3.2:1b")
            temperature = self.agent_config.get("temperature", 0.7)
            top_p = self.agent_config.get("top_p", 0.9)
            max_tokens = self.agent_config.get("max_tokens", 2048)
            system_prompt = self.agent_config.get("system_prompt", "")

            # Inject user profile context into system prompt
            try:
                import user_profile as _upm
                system_prompt = _upm.inject_into_system_prompt(system_prompt)
            except Exception:
                pass

            # Build role-based messages array for Ollama /api/chat
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": request.message})

            payload = {
                "messages": messages,
                "agent_id": request.agent_id,
                "model_name": model_name,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            }

            # Call Ollama with timeout
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        f"{self.ollama_url}/api/chat",
                        json=payload,
                        timeout=request.timeout
                    )
                ),
                timeout=request.timeout
            )

            processing_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                # Ollama /api/chat returns {"message": {"role": "assistant", "content": "..."}}
                msg_obj = data.get("message", {})
                ai_response = (
                    msg_obj.get("content") if isinstance(msg_obj, dict)
                    else data.get("response", "No response from AI")
                )
                if not ai_response:
                    ai_response = data.get("response", "No response from AI")

                # Store the response
                result = AgentResponse(
                    request_id=request.request_id,
                    agent_id=request.agent_id,
                    user_id=request.user_id,
                    message=request.message,
                    response=ai_response,
                    status=RequestStatus.COMPLETED,
                    processing_time=processing_time,
                    model_used=model_name,
                    tokens_used=len(ai_response.split()),
                )

                # Store in the manager's response store
                await async_agent_manager._store_response(request.request_id, result)

            else:
                # Non-200 response
                error_text = response.text[:200] if response.text else "Unknown error"
                result = AgentResponse(
                    request_id=request.request_id,
                    agent_id=request.agent_id,
                    user_id=request.user_id,
                    message=request.message,
                    status=RequestStatus.FAILED,
                    processing_time=processing_time,
                    error_message=f"Ollama returned {response.status_code}: {error_text}",
                    error_code="EABA03",
                )
                await async_agent_manager._store_response(request.request_id, result)

        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            result = AgentResponse(
                request_id=request.request_id,
                agent_id=request.agent_id,
                user_id=request.user_id,
                message=request.message,
                status=RequestStatus.TIMEOUT,
                processing_time=processing_time,
                error_message=f"Request timed out after {request.timeout}s",
                error_code="EABA04",
            )
            await async_agent_manager._store_response(request.request_id, result)

        except Exception as e:
            processing_time = time.time() - start_time
            result = AgentResponse(
                request_id=request.request_id,
                agent_id=request.agent_id,
                user_id=request.user_id,
                message=request.message,
                status=RequestStatus.FAILED,
                processing_time=processing_time,
                error_message=str(e),
                error_code="EABA05",
            )
            await async_agent_manager._store_response(request.request_id, result)


class AsyncAgentManager:
    """
    Manages multiple agent workers for concurrent request processing.

    Key features:
    - Per-agent request queues for true independence
    - Priority-based request ordering within each agent
    - Async request submission and response polling
    - Automatic worker lifecycle management
    """

    def __init__(self):
        self.ollama_url = os.environ.get("OLLAMA_SERVICE_URL", "http://127.0.0.1:5002")

        # Per-agent workers
        self._workers: Dict[str, AgentWorker] = {}
        self._workers_lock = threading.Lock()

        # Request tracking
        self._requests: Dict[str, AgentRequest] = {}
        self._responses: Dict[str, AgentResponse] = {}
        self._request_lock = asyncio.Lock()

        # Agent configurations (loaded from AGENTS_DATA or passed in)
        self._agent_configs: Dict[str, Dict[str, Any]] = {}

        # Statistics
        self._stats = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "timeout_requests": 0,
            "active_workers": 0,
        }

        # Event loop management
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._started = False

    def _ensure_loop(self):
        """Ensure we have a running event loop"""
        if self._loop is None or not self._loop.is_running():
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
            self._loop_thread.start()
            # Give the loop time to start
            time.sleep(0.1)

    def _run_loop(self):
        """Run the event loop in a separate thread"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def start_workers(self):
        """Initialize the manager (called on first request)"""
        self._started = True

    def update_agent_config(self, agent_id: str, config: Dict[str, Any]):
        """Update configuration for an agent"""
        self._agent_configs[agent_id] = config

        # Update worker if it exists
        with self._workers_lock:
            if agent_id in self._workers:
                self._workers[agent_id].agent_config = config

    def _get_or_create_worker(self, agent_id: str) -> AgentWorker:
        """Get or create a worker for an agent"""
        with self._workers_lock:
            if agent_id not in self._workers:
                config = self._agent_configs.get(agent_id, {})
                worker = AgentWorker(agent_id, self.ollama_url, config)
                self._workers[agent_id] = worker
                self._stats["active_workers"] = len(self._workers)
            return self._workers[agent_id]

    async def submit_request(
        self,
        agent_id: str,
        user_id: str,
        message: str,
        priority: int = 0,
        timeout: Optional[float] = None
    ) -> str:
        """
        Submit an async chat request.

        Returns a request_id that can be used to poll for the response.
        """
        if timeout is None:
            timeout = float(os.environ.get("ASYNC_REQUEST_TIMEOUT", "60"))

        request_id = str(uuid.uuid4())

        request = AgentRequest(
            request_id=request_id,
            agent_id=agent_id,
            user_id=user_id,
            message=message,
            priority=priority,
            timeout=timeout,
        )

        # Store the request
        async with self._request_lock:
            self._requests[request_id] = request
            self._stats["total_requests"] += 1

        # Get or create worker for this agent
        worker = self._get_or_create_worker(agent_id)

        # Submit to the worker
        await worker.submit(request)

        return request_id

    async def get_response(self, request_id: str) -> Optional[AgentResponse]:
        """Get the response for a completed request"""
        async with self._request_lock:
            return self._responses.get(request_id)

    async def get_request_status(self, request_id: str) -> Optional[RequestStatus]:
        """Get the current status of a request"""
        async with self._request_lock:
            # Check if completed
            if request_id in self._responses:
                return self._responses[request_id].status

            # Check if still pending
            if request_id in self._requests:
                return self._requests[request_id].status

            return None

    async def _store_response(self, request_id: str, response: AgentResponse):
        """Store a completed response (called by workers)"""
        async with self._request_lock:
            self._responses[request_id] = response

            # Update stats
            if response.status == RequestStatus.COMPLETED:
                self._stats["completed_requests"] += 1
            elif response.status == RequestStatus.FAILED:
                self._stats["failed_requests"] += 1
            elif response.status == RequestStatus.TIMEOUT:
                self._stats["timeout_requests"] += 1

            # Clean up the request entry
            if request_id in self._requests:
                del self._requests[request_id]

    async def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending request"""
        async with self._request_lock:
            if request_id in self._requests:
                request = self._requests[request_id]
                request.status = RequestStatus.CANCELLED

                # Create a cancelled response
                response = AgentResponse(
                    request_id=request_id,
                    agent_id=request.agent_id,
                    user_id=request.user_id,
                    message=request.message,
                    status=RequestStatus.CANCELLED,
                    error_message="Request cancelled by user",
                    error_code="IABA01",
                )
                self._responses[request_id] = response
                del self._requests[request_id]
                return True

        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        with self._workers_lock:
            worker_stats = {}
            for agent_id, worker in self._workers.items():
                queue_size = worker.request_queue.qsize() if worker.request_queue else 0
                worker_stats[agent_id] = {
                    "is_running": worker.is_running,
                    "queue_size": queue_size,
                    "processing": worker.current_request is not None,
                }

        return {
            **self._stats,
            "active_workers": len(self._workers),
            "pending_requests": len(self._requests),
            "completed_responses": len(self._responses),
            "workers": worker_stats,
            "mock": False,
        }

    def get_agent_queue_status(self, agent_id: str) -> Dict[str, Any]:
        """Get queue status for a specific agent"""
        with self._workers_lock:
            if agent_id not in self._workers:
                return {"exists": False, "queue_size": 0, "processing": False}

            worker = self._workers[agent_id]
            return {
                "exists": True,
                "is_running": worker.is_running,
                "queue_size": worker.request_queue.qsize() if worker.request_queue else 0,
                "processing": worker.current_request is not None,
                "current_request_id": worker.current_request.request_id if worker.current_request else None,
            }

    async def cleanup_old_responses(self, max_age_seconds: int = 3600):
        """Clean up responses older than max_age_seconds"""
        now = datetime.now()
        to_remove = []

        async with self._request_lock:
            for request_id, response in self._responses.items():
                try:
                    response_time = datetime.fromisoformat(response.timestamp)
                    age = (now - response_time).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(request_id)
                except Exception:
                    pass

            for request_id in to_remove:
                del self._responses[request_id]

        return len(to_remove)


# Global singleton instance
async_agent_manager = AsyncAgentManager()
