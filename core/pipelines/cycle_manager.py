"""
Cycle Manager - Prevents concurrent cycles and implements priority-based FIFO scheduling.

Priority order: daily > hourly > minute (higher interval = higher priority)
FIFO: First in, first out within same priority level.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any
from enum import IntEnum
from datetime import datetime, timezone
from dataclasses import dataclass, field

from core.logging import log


class CyclePriority(IntEnum):
    """Cycle priority levels - higher number = higher priority."""
    MINUTE = 1
    HOURLY = 2
    DAILY = 3


@dataclass
class CycleTask:
    """Represents a cycle task in the queue."""
    cycle_type: str  # 'daily', 'hourly', 'minute'
    priority: CyclePriority
    task_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    callback: Optional[Any] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)


class CycleManager:
    """
    Manages cycle execution with priority-based FIFO scheduling.
    
    Prevents concurrent cycles and ensures:
    - Higher interval cycles have higher priority (daily > hourly > minute)
    - FIFO processing within same priority level
    - Only one cycle runs at a time
    """
    
    _instance: Optional['CycleManager'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._queue: list[CycleTask] = []
        self._current_task: Optional[CycleTask] = None
        self._processing = False
        self._worker_task: Optional[asyncio.Task] = None
        self._initialized = True
        
        log.info("[CYCLE MANAGER] Initialized with priority-based FIFO scheduling")
    
    async def enqueue(
        self,
        cycle_type: str,
        callback: Any,
        *args,
        **kwargs
    ) -> str:
        """
        Enqueue a cycle task.
        
        Args:
            cycle_type: 'daily', 'hourly', or 'minute'
            callback: Async function to execute
            *args: Positional arguments for callback
            **kwargs: Keyword arguments for callback
            
        Returns:
            Task ID for tracking
        """
        # Determine priority
        priority_map = {
            'daily': CyclePriority.DAILY,
            'hourly': CyclePriority.HOURLY,
            'minute': CyclePriority.MINUTE,
        }
        priority = priority_map.get(cycle_type, CyclePriority.MINUTE)
        
        # Create task
        task_id = f"{cycle_type}_{int(datetime.now(timezone.utc).timestamp())}"
        task = CycleTask(
            cycle_type=cycle_type,
            priority=priority,
            task_id=task_id,
            callback=callback,
            args=args,
            kwargs=kwargs,
        )
        
        async with self._lock:
            # Insert task in priority order (higher priority first, then FIFO)
            inserted = False
            for i, existing_task in enumerate(self._queue):
                if task.priority > existing_task.priority:
                    self._queue.insert(i, task)
                    inserted = True
                    break
            if not inserted:
                self._queue.append(task)
            
            log.info(
                f"[CYCLE MANAGER] 📥 Enqueued {cycle_type} task {task_id} "
                f"(priority: {priority.name}, queue size: {len(self._queue)})"
            )
            
            # Start worker if not running
            if not self._processing and self._worker_task is None:
                self._worker_task = asyncio.create_task(self._worker())
        
        return task_id
    
    async def _worker(self):
        """Worker coroutine that processes tasks from the queue."""
        self._processing = True
        log.info("[CYCLE MANAGER] 🚀 Worker started")
        
        try:
            while True:
                # Get next task
                async with self._lock:
                    if not self._queue:
                        # No more tasks, stop worker
                        self._processing = False
                        self._worker_task = None
                        log.info("[CYCLE MANAGER] ⏹️ Worker stopped (queue empty)")
                        break
                    
                    # Get highest priority task (first in queue)
                    task = self._queue.pop(0)
                    self._current_task = task
                
                # Execute task
                log.info(
                    f"[CYCLE MANAGER] ▶️ Executing {task.cycle_type} task {task.task_id} "
                    f"(priority: {task.priority.name})"
                )
                
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(*task.args, **task.kwargs)
                    else:
                        task.callback(*task.args, **task.kwargs)
                    
                    log.info(
                        f"[CYCLE MANAGER] ✅ Completed {task.cycle_type} task {task.task_id}"
                    )
                except Exception as e:
                    log.error(
                        f"[CYCLE MANAGER] ❌ Failed {task.cycle_type} task {task.task_id}: {e}",
                        exc_info=True
                    )
                finally:
                    async with self._lock:
                        self._current_task = None
                
                # Small delay between tasks to allow state cleanup
                await asyncio.sleep(0.5)
        
        except Exception as e:
            log.error(f"[CYCLE MANAGER] ❌ Worker error: {e}", exc_info=True)
            async with self._lock:
                self._processing = False
                self._worker_task = None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        async def _get_status():
            async with self._lock:
                return {
                    "queue_size": len(self._queue),
                    "processing": self._processing,
                    "current_task": {
                        "cycle_type": self._current_task.cycle_type if self._current_task else None,
                        "task_id": self._current_task.task_id if self._current_task else None,
                    } if self._current_task else None,
                    "queued_tasks": [
                        {
                            "cycle_type": task.cycle_type,
                            "task_id": task.task_id,
                            "priority": task.priority.name,
                        }
                        for task in self._queue[:10]  # First 10
                    ],
                }
        
        # Run in event loop if available
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task to get status
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_status())
                    return future.result(timeout=1.0)
            else:
                return asyncio.run(_get_status())
        except Exception:
            return {"error": "Could not get status"}


# Global instance
cycle_manager = CycleManager()

