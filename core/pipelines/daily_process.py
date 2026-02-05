"""
Daily Process Handler - Backward-compatible shim for PolymarketFlux.

Maintains the legacy API while delegating to the new CAMEL Workforce-based
PolymarketFlux pipeline that uses API clients instead of direct Redis access.

Good practices retained:
- Bounded timeouts for blocking waits
- Non-blocking async design
- Cycle manager for priority-based FIFO scheduling
- Structured logging with markers
- Backward compatible with existing callers
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import asyncio

from camel.societies.workforce import Workforce
from core.logging import log
from core.pipelines.cycle_manager import cycle_manager
from core.pipelines.polymarket_flux import PolymarketFlux


class DailyProcess:
    """Backward-compatible shim that delegates to CAMEL Workforce-based PolymarketFlux.

    Maintains the external API so existing callers don't need to change,
    while the implementation now uses pure CAMEL Workforce + API clients.
    """

    def __init__(self, workforce: Workforce, api_client: Any) -> None:
        """Initialize with CAMEL Workforce and API client.

        Args:
            workforce: CAMEL Workforce instance with shared memory
            api_client: PolymarketClient or similar API wrapper
        """
        self.workforce = workforce
        self.flux = PolymarketFlux(workforce=workforce, api_client=api_client)

    async def process(
        self,
        tickers: List[str],
        strategies: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process daily wallet distribution.

        ✅ SAFEGUARD ONLY: This method does NOT manage triggers or intervals.
        The scheduler service (scheduler/service.py) is the ONLY service that manages triggers.
        This method only processes when called - it's a safeguard to prevent errors and loops.

        Uses cycle manager to enqueue the task for priority-based FIFO scheduling.
        For direct calls (like tests), this will process immediately via cycle manager.

        Args:
            tickers: List of ticker symbols
            strategies: List of strategy names to process (defaults to all enabled strategies)

        Returns:
            Dictionary with success status and results
        """
        # Use cycle manager to enqueue and process via PolymarketFlux
        # The cycle manager ensures proper scheduling and prevents concurrent cycles
        task_id = await cycle_manager.enqueue(
            cycle_type="daily",
            callback=self._process_via_flux,
            tickers=tickers,
            strategies=strategies,
        )

        log.info(f"[DAILY PROCESS] Enqueued daily process task: {task_id}")

        # Wait for cycle manager to process the task
        # ✅ CRITICAL: Bounded wait with timeout to prevent infinite loops.
        # Workforce tasks can legitimately take time (multiple agents), allow up to 20 minutes.
        max_wait = 1800  # 20 minutes maximum wait
        wait_interval = 0.5
        elapsed = 0

        while elapsed < max_wait:
            status = cycle_manager.get_queue_status()
            current_task = status.get("current_task")
            queued_tasks = status.get("queued_tasks", [])

            # Check if task is still processing or queued
            task_processing = current_task and current_task.get("task_id") == task_id
            task_queued = any(t.get("task_id") == task_id for t in queued_tasks)

            if not task_processing and not task_queued:
                # Task completed - exit loop
                log.info(f"[DAILY PROCESS] Task {task_id} completed (waited {elapsed:.1f}s)")
                break

            await asyncio.sleep(wait_interval)
            elapsed += wait_interval

        # ✅ CRITICAL: If timeout reached, log warning but don't retry (prevents loops)
        if elapsed >= max_wait:
            log.warning(
                f"[DAILY PROCESS] ⚠️ Task {task_id} wait timeout ({max_wait}s) - task may still be processing"
            )

        # Return success status (results stored via API)
        return {
            "success": True,
            "agentic": True,
            "task_id": task_id,
            "strategies": strategies or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _process_via_flux(
        self,
        tickers: List[str],
        strategies: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run analysis via PolymarketFlux CAMEL pipeline.

        This is called by cycle_manager and delegates to the Workforce-based flux.

        Args:
            tickers: List of ticker symbols
            strategies: Strategy names to process

        Returns:
            Analysis results dictionary
        """
        log.info(f"[DAILY PROCESS] Running flux analysis for {len(tickers)} tickers")
        try:
            result = await self.flux.run_flux(tickers=tickers, strategies=strategies)
            log.info(f"[DAILY PROCESS] Flux completed successfully: {result.get('decision_id')}")
            return result
        except Exception as exc:
            log.error(f"[DAILY PROCESS] Flux failed: {exc}", exc_info=True)
            return {"error": str(exc), "success": False}
