"""Polymarket RSS Flux Pipeline - Event-driven market scanning & trading.

This pipeline only processes the Polymarket market feed (no external RSS sources).
Because Polymarket does not expose a direct RSS endpoint, we maintain a cached JSON
state of market updates and review batches once a threshold is reached.

Architecture:
- MarketScanner: Polls Polymarket for new/updated markets (RSS-like)
- MarketAnalyzer: Deep analysis per market (orderbook, liquidity, activity)
- TradeDecisionMaker: Determines if position is worthwhile
- TradeExecutor: Executes position or records skip decision
- ResultTracker: Monitors outcomes and ROI

Pure CAMEL Workforce + Task decomposition with Polymarket MCP tools.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

from camel.tasks import Task
from camel.societies.workforce import Workforce

from core.clients.polymarket_client import PolymarketClient
from core.logging import log


class MarketFilterCriteria(Enum):
    """Filtering criteria for market selection."""
    HIGH_VOLUME = "high_volume"  # Recent activity
    LIQUID = "liquid"  # Deep orderbook
    CLOSE_ODDS = "close_odds"  # Tight bid-ask
    TRENDING = "trending"  # Rising volume/interest
    NEW_MARKET = "new_market"  # Recently created


class RSSFluxConfig:
    """Configuration for RSS Flux pipeline trigger intervals."""

    def __init__(
        self,
        scan_interval: int = 300,  # 5 minutes default
        batch_size: int = 50,
        review_threshold: int = 25,
        max_cache: int = 500,
        max_trades_per_day: int = 10,
        min_confidence: float = 0.65,
        trigger_type: str = "interval",
        interval_hours: int = 4,
        cache_path: Optional[str] = None,
    ):
        self.scan_interval = scan_interval
        self.batch_size = batch_size
        self.review_threshold = review_threshold
        self.max_cache = max_cache
        self.max_trades_per_day = max_trades_per_day
        self.min_confidence = min_confidence
        self.trigger_type = trigger_type
        self.interval_hours = interval_hours
        self.cache_path = cache_path or "logs/polymarket_feed_cache.json"
        log.info(
            "[RSS FLUX CONFIG] Initialized: scan_interval=%ds, batch_size=%d, "
            "min_confidence=%.2f, max_trades_per_day=%d",
            scan_interval,
            batch_size,
            min_confidence,
            max_trades_per_day,
        )


class PolymarketRSSFlux:
    """Event-driven Polymarket trading orchestrator using CAMEL Workforce.

    Continuously scans Polymarket markets, applies filters, performs analysis,
    and executes trades based on opportunity scoring.

    Public API:
    - `start()` : Begin continuous market scanning
    - `process_market_batch()` : Scan and filter markets
    - `stop()` : Graceful shutdown
    """

    def __init__(
        self,
        workforce: Workforce,
        api_client: Any = None,
        config: Optional[RSSFluxConfig] = None,
    ) -> None:
        """Initialize RSS Flux pipeline.

        Args:
            workforce: CAMEL Workforce instance with shared memory
            api_client: PolymarketClient for market data access
            config: RSSFluxConfig with trigger intervals and trading limits
        """
        self.config = config or RSSFluxConfig()
        self.workforce = workforce
        self.api_client = api_client or PolymarketClient()
        self.polymarket_client = self.api_client
        self.scan_interval = self.config.scan_interval
        self.batch_size = self.config.batch_size
        self.trigger_type = self.config.trigger_type
        self.interval_hours = self.config.interval_hours
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._last_scan_cursor = None
        self._active_positions: Dict[str, Dict[str, Any]] = {}
        self.review_threshold = self.config.review_threshold
        self.max_cache = self.config.max_cache
        self.cache_path = Path(self.config.cache_path)
        self._feed_cache: Dict[str, Dict[str, Any]] = {}
        self._trades_today = 0
        self._trade_day = datetime.now(timezone.utc).date()
        self._scan_lock = asyncio.Lock()
        self._last_trigger_at: Optional[datetime] = None
        self._last_trigger_type: Optional[str] = None
        self._last_interval_trigger_at: Optional[datetime] = None
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached Polymarket feed state from disk."""
        try:
            if self.cache_path.exists():
                data = json.loads(self.cache_path.read_text())
                self._feed_cache = data.get("markets", {}) if isinstance(data, dict) else {}
            else:
                self._feed_cache = {}
        except Exception as exc:
            log.warning(f"[POLYMARKET RSS FLUX] Failed to load cache: {exc}")
            self._feed_cache = {}

    def _save_cache(self) -> None:
        """Persist cached Polymarket feed state to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(self._feed_cache),
                "markets": self._feed_cache,
            }
            self.cache_path.write_text(json.dumps(payload, indent=2))
        except Exception as exc:
            log.warning(f"[POLYMARKET RSS FLUX] Failed to save cache: {exc}")

    def _is_exhausted(self, market: Dict[str, Any]) -> bool:
        """Check if a market is exhausted (closed/expired or already active)."""
        market_id = market.get("id")
        if not market_id:
            return True
        if market_id in self._active_positions:
            return True
        if market.get("closed") is True or market.get("active") is False:
            return True
        close_time = market.get("close_time")
        if isinstance(close_time, str):
            try:
                close_dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                if close_dt <= datetime.now(timezone.utc):
                    return True
            except Exception:
                pass
        return False

    def _update_feed_cache(self, markets: List[Dict[str, Any]]) -> None:
        """Update cached feed with latest markets and prune exhausted."""
        now = datetime.now(timezone.utc).isoformat()
        for market in markets:
            market_id = market.get("id")
            if not market_id:
                continue
            exhausted = self._is_exhausted(market)
            existing = self._feed_cache.get(market_id, {})
            self._feed_cache[market_id] = {
                "id": market_id,
                "title": market.get("title"),
                "first_seen": existing.get("first_seen", now),
                "last_seen": now,
                "exhausted": exhausted,
                "data": market,
            }

        # Remove exhausted entries and cap cache size
        self._feed_cache = {
            k: v for k, v in self._feed_cache.items() if not v.get("exhausted")
        }
        if len(self._feed_cache) > self.max_cache:
            # Drop oldest by last_seen
            ordered = sorted(
                self._feed_cache.values(),
                key=lambda m: m.get("last_seen", ""),
            )
            keep = ordered[-self.max_cache:]
            self._feed_cache = {m["id"]: m for m in keep if m.get("id")}

    async def start(self) -> None:
        """Begin continuous market scanning loop."""
        if self._running:
            log.warning("[POLYMARKET RSS FLUX] Already running, ignoring start request")
            return

        self._running = True
        log.info(
            f"[POLYMARKET RSS FLUX] Starting market scanning (interval={self.scan_interval}s, batch={self.batch_size})"
        )

        # Launch background scanning task
        self._scan_task = asyncio.create_task(self._scanning_loop())

    async def stop(self) -> None:
        """Graceful shutdown of market scanning."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        log.info("[POLYMARKET RSS FLUX] Market scanning stopped")

    async def _scanning_loop(self) -> None:
        """Continuous market scanning loop."""
        while self._running:
            try:
                if self.trigger_type != "interval":
                    await asyncio.sleep(5)
                    continue

                # Scan batch of markets
                await self.process_market_batch(trigger_type="interval", verify_positions=True, enforce_limits=True)

                # Wait before next scan
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error(
                    "[POLYMARKET RSS FLUX] Scanning loop error: %s", exc, exc_info=True
                )
                # Don't crash - continue scanning
                await asyncio.sleep(self.scan_interval)

    async def _refresh_active_positions(self) -> None:
        """Refresh active positions from the Polymarket client when available."""
        if not hasattr(self.polymarket_client, "get_open_positions"):
            return
        try:
            positions = self.polymarket_client.get_open_positions()
            if asyncio.iscoroutine(positions):
                positions = await positions
            positions = positions or {}
            if isinstance(positions, dict):
                for market_id, orders in positions.items():
                    existing = self._active_positions.get(market_id, {})
                    if not isinstance(existing, dict):
                        existing = {}
                    self._active_positions[market_id] = {
                        **existing,
                        "market_id": market_id,
                        "orders": orders,
                    }
                address = (
                    getattr(self.polymarket_client, "polygon_address", None)
                    or getattr(self.polymarket_client, "address", None)
                    or "unknown"
                )
                short_addr = f"{str(address)[:6]}...{str(address)[-4:]}" if address else "unknown"
                log.info(
                    "[POLYMARKET RSS FLUX] Open positions refreshed for wallet %s: %d",
                    short_addr,
                    len(self._active_positions),
                )
        except Exception as exc:
            log.warning(f"[POLYMARKET RSS FLUX] Failed to refresh open positions: {exc}")

    async def process_market_batch(
        self,
        trigger_type: str = "interval",
        verify_positions: bool = True,
        enforce_limits: bool = True,
    ) -> Dict[str, Any]:
        """Scan and process a batch of Polymarket markets.

        Workflow:
        1. Fetch markets from Polymarket API
        2. Filter by opportunity criteria
        3. For each promising market: analyze → decide → execute or skip
        4. Track results

        Returns:
            Summary of batch processing
        """
        if self._scan_lock.locked():
            return {
                "status": "in_progress",
                "triggered": False,
                "reason": "scan_in_progress",
                "trigger_type": trigger_type,
            }

        now = datetime.now(timezone.utc)
        if now.date() > self._trade_day:
            self._trade_day = now.date()
            self._trades_today = 0
        use_cache = trigger_type != "manual"
        check_threshold = trigger_type != "manual"
        if trigger_type == "manual":
            verify_positions = False
            enforce_limits = False
        if (
            trigger_type == "interval"
            and self._last_interval_trigger_at
            and (now - self._last_interval_trigger_at).total_seconds() < self.scan_interval
        ):
            return {
                "status": "skipped",
                "triggered": False,
                "reason": "interval_throttle",
                "trigger_type": trigger_type,
            }

        async with self._scan_lock:
            self._last_trigger_at = now
            self._last_trigger_type = trigger_type
            if trigger_type == "interval":
                self._last_interval_trigger_at = now

            batch_id = f"batch_{int(datetime.now(timezone.utc).timestamp())}"
            log.info(f"[POLYMARKET RSS FLUX] Processing batch {batch_id} ({trigger_type})")

            try:
                # Step 0: Refresh active positions
                await self._refresh_active_positions()

                # Step 1: Fetch markets directly (source of truth)
                markets = await self._fetch_latest_markets()
                if not markets:
                    log.debug("[POLYMARKET RSS FLUX] No markets found in scan")
                    return {"batch_id": batch_id, "markets_found": 0, "analyzed": 0}

                pending_markets: List[Dict[str, Any]] = []
                if use_cache:
                    # Step 2: Update cached feed and defer processing until threshold is met
                    self._update_feed_cache(markets)
                    pending_markets = list(self._feed_cache.values())
                    if check_threshold and len(pending_markets) < self.review_threshold:
                        self._save_cache()
                        log.info(
                            f"[POLYMARKET RSS FLUX] Cached {len(pending_markets)} markets "
                            f"(threshold={self.review_threshold}); waiting to review."
                        )
                        return {
                            "batch_id": batch_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "markets_scanned": len(markets),
                            "pending_review": len(pending_markets),
                            "threshold": self.review_threshold,
                            "trigger_type": trigger_type,
                        }

                # Step 3: Choose batch candidates
                if use_cache:
                    filtered = self._filter_markets([m["data"] for m in pending_markets])
                else:
                    filtered = markets[: self.batch_size]
                if not filtered:
                    return {
                        "batch_id": batch_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "markets_scanned": len(markets),
                        "opportunities_filtered": 0,
                        "trigger_type": trigger_type,
                    }

                # Step 4: Run a single workforce task for the batch
                before_positions = set(self._active_positions.keys())
                workforce_result = await self._run_batch_task(
                    filtered,
                    trigger_type=trigger_type,
                    enforce_limits=enforce_limits,
                )
                await self._refresh_active_positions()
                after_positions = set(self._active_positions.keys())
                new_positions = list(after_positions - before_positions)
                if enforce_limits:
                    self._trades_today += len(new_positions)

                if use_cache:
                    # Mark processed markets as exhausted and persist cache
                    for market in filtered:
                        market_id = market.get("id")
                        if market_id and market_id in self._feed_cache:
                            self._feed_cache[market_id]["exhausted"] = True
                    self._update_feed_cache([])  # prune exhausted
                    self._save_cache()

                summary = {
                    "batch_id": batch_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "markets_scanned": len(markets),
                    "opportunities_filtered": len(filtered),
                    "trades_executed": len(new_positions),
                    "new_positions": new_positions,
                    "positions_active": len(self._active_positions),
                    "pending_review": len(self._feed_cache) if use_cache else 0,
                    "trigger_type": trigger_type,
                    "workforce_result": workforce_result,
                }

                log.info(
                    "[POLYMARKET RSS FLUX] Batch %s complete: %d filtered, %d new positions",
                    batch_id,
                    summary["opportunities_filtered"],
                    summary["trades_executed"],
                )

                return summary

            except Exception as exc:
                log.error(f"[POLYMARKET RSS FLUX] Batch processing failed: %s", exc, exc_info=True)
                return {
                    "batch_id": batch_id,
                    "error": str(exc),
                    "status": "failed",
                    "trigger_type": trigger_type,
                }

    async def _fetch_latest_markets(self) -> List[Dict[str, Any]]:
        """Fetch the latest markets directly from Polymarket API."""
        if not self.polymarket_client:
            return []
        try:
            markets = await self.polymarket_client.search_markets(
                query="",
                limit=self.batch_size,
            )
            return markets or []
        except Exception as exc:
            log.warning("[POLYMARKET RSS FLUX] Latest market fetch failed: %s", exc)
            return []

    def _filter_markets(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter markets by opportunity criteria.

        Filters for:
        - High recent volume
        - Good liquidity (deep orderbook)
        - Tight odds (bid-ask spread)
        - Trending (increasing activity)
        - Sufficient time to expiration

        Returns:
            Filtered list of promising markets
        """
        filtered = []
        now = datetime.now(timezone.utc)

        for market in markets:
            try:
                # Extract market metrics
                volume_24h = market.get("volume_24h", 0)
                liquidity = market.get("liquidity_score", 0)  # 0-100
                bid_ask_spread = market.get("bid_ask_spread", 1.0)  # percentage
                close_time = market.get("close_time")

                # Parse close_time if string
                if isinstance(close_time, str):
                    close_time = datetime.fromisoformat(close_time.replace("Z", "+00:00"))

                # Calculate time to close
                time_to_close = (close_time - now).total_seconds() / 3600 if close_time else 0

                # Apply filters
                if volume_24h < 100:  # Minimum volume threshold
                    continue
                if liquidity < 40:  # Minimum liquidity (orderbook depth)
                    continue
                if bid_ask_spread > 5:  # Too wide spread
                    continue
                if time_to_close < 1 or time_to_close > 240:  # Between 1 hour and 10 days
                    continue

                # Market passed filters
                filtered.append({
                    **market,
                    "filter_score": (volume_24h / 1000) + (liquidity / 10) - (bid_ask_spread / 2),
                })

            except Exception as exc:
                log.debug(f"[POLYMARKET RSS FLUX] Filter error for market: {exc}")
                continue

        # Sort by opportunity score (highest first)
        filtered.sort(key=lambda m: m.get("filter_score", 0), reverse=True)

        return filtered[:20]  # Limit to top 20 opportunities per scan

    async def _run_batch_task(
        self,
        markets: List[Dict[str, Any]],
        trigger_type: str,
        enforce_limits: bool,
    ) -> Dict[str, Any]:
        """Run a single CAMEL workforce task for the batch (analysis + trade)."""
        if not markets:
            return {"status": "skipped", "reason": "no_markets"}

        market_titles = [m.get("title", "Unknown Market") for m in markets]
        market_ids = [m.get("id") for m in markets if m.get("id")]

        allow_execution = True
        if enforce_limits and self._trades_today >= self.config.max_trades_per_day:
            allow_execution = False

        limit_note = "Manual override: bypass limits and confidence thresholds."
        if enforce_limits:
            limit_note = (
                f"Respect limits (max_trades_per_day={self.config.max_trades_per_day}, "
                f"min_confidence={self.config.min_confidence:.2f})."
            )
        if not allow_execution:
            limit_note += " Trading execution is disabled for this batch (daily limit reached)."

        root_task = Task(
            content=(
                "End-to-end analysis and trade decision for Polymarket batch.\n\n"
                f"Trigger: {trigger_type}\n"
                f"Batch size: {len(markets)}\n"
                f"Markets: {market_titles}\n\n"
                "Use the Polymarket toolkit to fetch data and execute trades. "
                "Do not return structured JSON as source of truth. "
                f"{limit_note}"
            ),
            type="orchestration",
            additional_info={
                "trigger_type": trigger_type,
                "market_ids": market_ids,
            },
        )

        fetch_task = Task(
            content=(
                "Fetch full market details and orderbooks for each market in the batch.\n"
                "Use: get_market_details(), get_orderbook()."
            ),
            type="market_fetch",
            parent=root_task,
        )

        analysis_task = Task(
            content=(
                "Analyze each market and estimate confidence (0.0–1.0). "
                "Evaluate liquidity, spread, odds, and crowd consensus risk."
            ),
            type="analysis",
            parent=root_task,
            dependencies=[fetch_task],
        )

        if allow_execution:
            decision_task = Task(
                content=(
                    "For each market, decide BUY / HOLD / SKIP. "
                    "Execute trades only for BUY using the Polymarket toolkit."
                ),
                type="decision",
                parent=root_task,
                dependencies=[analysis_task],
            )
            root_task.subtasks = [fetch_task, analysis_task, decision_task]
        else:
            decision_task = Task(
                content=(
                    "For each market, decide BUY / HOLD / SKIP. "
                    "Execution is disabled for this batch."
                ),
                type="decision",
                parent=root_task,
                dependencies=[analysis_task],
            )
            root_task.subtasks = [fetch_task, analysis_task, decision_task]

        result = await self._execute_task(root_task, "batch_orchestration")

        workforce_snapshot = {}
        if hasattr(self.workforce, "get_workforce_log_tree"):
            workforce_snapshot["task_tree"] = self.workforce.get_workforce_log_tree()
        if hasattr(self.workforce, "get_completed_tasks"):
            workforce_snapshot["completed_tasks"] = self.workforce.get_completed_tasks()
        if hasattr(self.workforce, "get_workforce_kpis"):
            workforce_snapshot["kpis"] = self.workforce.get_workforce_kpis()

        return {
            "status": "completed",
            "result": result,
            "workforce_observability": workforce_snapshot,
            "execution_enabled": allow_execution,
        }

    async def _execute_task(
        self, task: Task, task_type: str
    ) -> Dict[str, Any]:
        """Execute a task through the Workforce.

        Args:
            task: CAMEL Task to execute
            task_type: Task type descriptor for logging

        Returns:
            Task execution result
        """
        try:
            log.debug(
                f"[POLYMARKET RSS FLUX] Executing task ({task_type}) "
                f"via workforce: {self.workforce.__class__.__name__}"
            )

            # Try multiple execution methods in fallback order
            if hasattr(self.workforce, "process_task_async"):
                log.debug("[POLYMARKET RSS FLUX] Using process_task_async")
                result = await self.workforce.process_task_async(task)
            elif hasattr(self.workforce, "process_task"):
                log.debug("[POLYMARKET RSS FLUX] Using process_task")
                result = await self.workforce.process_task(task)
            else:
                log.warning("[POLYMARKET RSS FLUX] Workforce has no task execution method")
                result = {"status": "placeholder"}

            return result if isinstance(result, dict) else {}
        except Exception as exc:
            log.warning(f"[POLYMARKET RSS FLUX] Task execution failed ({task_type}): {exc}")
            return {"status": "failed", "error": str(exc)}

    def get_active_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get currently active trading positions."""
        return self._active_positions.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get current RSS Flux status including trading limits."""
        return {
            "running": self._running,
            "scan_interval": self.scan_interval,
            "batch_size": self.batch_size,
            "review_threshold": self.review_threshold,
            "active_positions": len(self._active_positions),
            "trades_today": self._trades_today,
            "trades_max_per_day": self.config.max_trades_per_day,
            "min_confidence": self.config.min_confidence,
            "cached_markets": len(self._feed_cache),
            "last_trigger_at": self._last_trigger_at.isoformat() if self._last_trigger_at else None,
            "last_trigger_type": self._last_trigger_type,
            "scan_in_progress": self._scan_lock.locked(),
            "trigger_type": self.trigger_type,
            "interval_hours": self.interval_hours,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
