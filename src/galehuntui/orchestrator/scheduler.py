"""Task scheduler for async pipeline execution.

This module provides the TaskScheduler class for managing concurrent
task execution with rate limiting and priority queuing.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar
from uuid import uuid4

from galehuntui.core.constants import EngagementMode, RATE_LIMITS


T = TypeVar("T")


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0  # Must run immediately
    HIGH = 1      # Run as soon as possible
    NORMAL = 2    # Standard priority
    LOW = 3       # Run when resources available


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task(Generic[T]):
    """A scheduled task.
    
    Attributes:
        id: Unique task identifier
        name: Human-readable task name
        coro_func: Coroutine function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        priority: Task priority
        status: Current status
        result: Task result (if completed)
        error: Error message (if failed)
        created_at: Creation timestamp
        started_at: Execution start timestamp
        completed_at: Completion timestamp
    """
    id: str
    name: str
    coro_func: Callable[..., Awaitable[T]]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[T] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __lt__(self, other: "Task") -> bool:
        """Compare tasks by priority for queue ordering."""
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority.value < other.priority.value
    
    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()


class RateLimiter:
    """Token bucket rate limiter.
    
    Implements a token bucket algorithm for rate limiting with
    smooth token replenishment.
    """
    
    def __init__(
        self,
        rate: float,
        *,
        burst: Optional[int] = None,
    ) -> None:
        """Initialize rate limiter.
        
        Args:
            rate: Maximum requests per second
            burst: Maximum burst size (defaults to rate)
        """
        self.rate = rate
        self.burst = burst or int(rate)
        self._tokens = float(self.burst)
        self._last_update = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            await self._replenish()
            
            while self._tokens < 1:
                # Calculate wait time for next token
                wait_time = (1 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)
                await self._replenish()
            
            self._tokens -= 1
    
    async def _replenish(self) -> None:
        """Replenish tokens based on elapsed time."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        return self._tokens


class TaskScheduler:
    """Async task scheduler with worker pool and rate limiting.
    
    Manages concurrent execution of tasks with configurable concurrency,
    rate limiting, and priority-based scheduling.
    
    Attributes:
        max_workers: Maximum concurrent workers
        rate_limiter: Optional rate limiter for task execution
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        *,
        rate_limit: Optional[float] = None,
        engagement_mode: Optional[EngagementMode] = None,
    ) -> None:
        """Initialize task scheduler.
        
        Args:
            max_workers: Maximum concurrent task workers
            rate_limit: Optional rate limit (requests per second)
            engagement_mode: Engagement mode for rate limit defaults
        """
        self.max_workers = max_workers
        
        # Set rate limit based on engagement mode if not specified
        if rate_limit is None and engagement_mode is not None:
            mode_limits = RATE_LIMITS.get(engagement_mode, {})
            rate_limit = float(mode_limits.get("global", 30))
        
        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        
        # Task management
        self._tasks: dict[str, Task] = {}
        self._queue: asyncio.PriorityQueue[tuple[int, str]] = asyncio.PriorityQueue()
        self._active_tasks: set[str] = set()
        
        # Worker management
        self._workers: list[asyncio.Task] = []
        self._semaphore = asyncio.Semaphore(max_workers)
        self._shutdown = asyncio.Event()
        self._started = False
        
        # Callbacks
        self._on_task_complete: list[Callable[[Task], None]] = []
        self._on_task_error: list[Callable[[Task, Exception], None]] = []
    
    async def start(self) -> None:
        """Start the scheduler workers."""
        if self._started:
            return
        
        self._started = True
        self._shutdown.clear()
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(
                self._worker(f"worker-{i}"),
                name=f"scheduler-worker-{i}",
            )
            self._workers.append(worker)
    
    async def stop(self, *, wait: bool = True, timeout: float = 30.0) -> None:
        """Stop the scheduler.
        
        Args:
            wait: Whether to wait for running tasks to complete
            timeout: Maximum time to wait for tasks
        """
        self._shutdown.set()
        
        if wait and self._active_tasks:
            try:
                await asyncio.wait_for(
                    self._wait_for_completion(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                pass
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        self._started = False
    
    async def _wait_for_completion(self) -> None:
        """Wait for all active tasks to complete."""
        while self._active_tasks:
            await asyncio.sleep(0.1)
    
    async def submit(
        self,
        name: str,
        coro_func: Callable[..., Awaitable[T]],
        *args: Any,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs: Any,
    ) -> str:
        """Submit a task for execution.
        
        Args:
            name: Task name
            coro_func: Async function to execute
            *args: Positional arguments for function
            priority: Task priority
            **kwargs: Keyword arguments for function
            
        Returns:
            Task ID
        """
        task_id = str(uuid4())
        
        task: Task = Task(
            id=task_id,
            name=name,
            coro_func=coro_func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            status=TaskStatus.QUEUED,
        )
        
        self._tasks[task_id] = task
        
        # Add to priority queue (priority value, task_id)
        await self._queue.put((priority.value, task_id))
        
        return task_id
    
    async def submit_batch(
        self,
        tasks: list[tuple[str, Callable[..., Awaitable[T]], tuple, dict]],
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> list[str]:
        """Submit multiple tasks at once.
        
        Args:
            tasks: List of (name, coro_func, args, kwargs) tuples
            priority: Priority for all tasks
            
        Returns:
            List of task IDs
        """
        task_ids = []
        for name, coro_func, args, kwargs in tasks:
            task_id = await self.submit(
                name,
                coro_func,
                *args,
                priority=priority,
                **kwargs,
            )
            task_ids.append(task_id)
        return task_ids
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task if found, None otherwise
        """
        return self._tasks.get(task_id)
    
    async def wait_for_task(
        self,
        task_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Optional[Task]:
        """Wait for a specific task to complete.
        
        Args:
            task_id: Task ID to wait for
            timeout: Maximum time to wait
            
        Returns:
            Completed task or None if timeout/not found
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None
        
        start_time = asyncio.get_event_loop().time()
        
        while task.status in (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING):
            if timeout is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    return task
            
            await asyncio.sleep(0.05)
        
        return task
    
    async def wait_all(
        self,
        task_ids: list[str],
        *,
        timeout: Optional[float] = None,
    ) -> list[Task]:
        """Wait for multiple tasks to complete.
        
        Args:
            task_ids: List of task IDs
            timeout: Maximum time to wait
            
        Returns:
            List of completed tasks
        """
        tasks = []
        for task_id in task_ids:
            task = await self.wait_for_task(task_id, timeout=timeout)
            if task is not None:
                tasks.append(task)
        return tasks
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or queued task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled, False if already running/completed
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False
        
        if task.status in (TaskStatus.PENDING, TaskStatus.QUEUED):
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            return True
        
        return False
    
    def on_task_complete(self, callback: Callable[[Task], None]) -> None:
        """Register callback for task completion.
        
        Args:
            callback: Function to call when task completes
        """
        self._on_task_complete.append(callback)
    
    def on_task_error(self, callback: Callable[[Task, Exception], None]) -> None:
        """Register callback for task errors.
        
        Args:
            callback: Function to call when task fails
        """
        self._on_task_error.append(callback)
    
    async def _worker(self, worker_name: str) -> None:
        """Worker coroutine that processes tasks from queue.
        
        Args:
            worker_name: Worker identifier for logging
        """
        while not self._shutdown.is_set():
            try:
                # Get next task from queue with timeout
                try:
                    _, task_id = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=0.5,
                    )
                except asyncio.TimeoutError:
                    continue
                
                task = self._tasks.get(task_id)
                if task is None or task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue
                
                # Acquire semaphore for concurrency control
                async with self._semaphore:
                    await self._execute_task(task)
                
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but keep worker running
                continue
    
    async def _execute_task(self, task: Task) -> None:
        """Execute a single task.
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self._active_tasks.add(task.id)
        
        try:
            # Apply rate limiting if configured
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            
            # Execute the task
            result = await task.coro_func(*task.args, **task.kwargs)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Notify callbacks
            for callback in self._on_task_complete:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(task)
                    else:
                        callback(task)
                except Exception:
                    pass
                    
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            
            # Notify error callbacks
            for callback in self._on_task_error:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(task, e)
                    else:
                        callback(task, e)
                except Exception:
                    pass
        
        finally:
            self._active_tasks.discard(task.id)
    
    @property
    def pending_count(self) -> int:
        """Get count of pending/queued tasks."""
        return sum(
            1 for t in self._tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.QUEUED)
        )
    
    @property
    def running_count(self) -> int:
        """Get count of running tasks."""
        return len(self._active_tasks)
    
    @property
    def completed_count(self) -> int:
        """Get count of completed tasks."""
        return sum(
            1 for t in self._tasks.values()
            if t.status == TaskStatus.COMPLETED
        )
    
    @property
    def failed_count(self) -> int:
        """Get count of failed tasks."""
        return sum(
            1 for t in self._tasks.values()
            if t.status == TaskStatus.FAILED
        )
    
    def get_statistics(self) -> dict[str, int]:
        """Get scheduler statistics.
        
        Returns:
            Dictionary with task counts by status
        """
        return {
            "pending": self.pending_count,
            "running": self.running_count,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "total": len(self._tasks),
        }
