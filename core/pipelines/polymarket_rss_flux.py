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
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from camel.tasks import Task
from camel.societies.workforce import Workforce

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
        cache_path: Optional[str] = None,
    ):
        self.scan_interval = scan_interval
        self.batch_size = batch_size
        self.review_threshold = review_threshold
        self.max_cache = max_cache
        self.max_trades_per_day = max_trades_per_day
        self.min_confidence = min_confidence
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
        # Allow api_client to be optional for tests; create default PolymarketClient if not supplied
        if api_client is None:
            try:
                from core.clients.polymarket_client import PolymarketClient
                self.api_client = PolymarketClient()
            except Exception:
                self.api_client = None
        else:
            self.api_client = api_client
        self.scan_interval = self.config.scan_interval
        self.batch_size = self.config.batch_size
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
                # Scan batch of markets
                await self.process_market_batch()

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

    async def process_market_batch(self) -> Dict[str, Any]:
        """Scan and process a batch of Polymarket markets.

        Workflow:
        1. Fetch markets from Polymarket API
        2. Filter by opportunity criteria
        3. For each promising market: analyze → decide → execute or skip
        4. Track results

        Returns:
            Summary of batch processing
        """
        batch_id = f"batch_{int(datetime.now(timezone.utc).timestamp())}"
        log.info(f"[POLYMARKET RSS FLUX] Processing batch {batch_id}")

        try:
            # Step 1: Market Scanning Task (via Workforce)
            markets = await self._execute_market_scanner()

            if not markets:
                log.debug("[POLYMARKET RSS FLUX] No markets found in scan")
                return {"batch_id": batch_id, "markets_found": 0, "analyzed": 0}

            # Step 2: Update cached feed and defer processing until threshold is met
            self._update_feed_cache(markets)
            pending_markets = list(self._feed_cache.values())
            if len(pending_markets) < self.review_threshold:
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
                }

            # Step 3: Filter markets by criteria (from cached feed)
            filtered = self._filter_markets([m["data"] for m in pending_markets])
            log.info(
                f"[POLYMARKET RSS FLUX] Found {len(filtered)} opportunities from {len(markets)} markets"
            )

            # Step 4: Analyze each promising market
            analyzed_results = []
            for market_data in filtered:
                result = await self._analyze_and_decide(market_data)
                analyzed_results.append(result)

                # Give other tasks a chance to run
                await asyncio.sleep(0.1)

            # Step 5: Execute trades for high-confidence opportunities
            executed_trades = []
            for result in analyzed_results:
                if result["decision"] == "BUY" and result["confidence"] > 0.65:
                    trade_result = await self._execute_trade(result)
                    executed_trades.append(trade_result)

            # Mark processed markets as exhausted and persist cache
            for result in analyzed_results:
                market_id = result.get("market_id")
                if market_id and market_id in self._feed_cache:
                    self._feed_cache[market_id]["exhausted"] = True
            self._update_feed_cache([])  # prune exhausted
            self._save_cache()

            # Step 6: Track results
            summary = {
                "batch_id": batch_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "markets_scanned": len(markets),
                "opportunities_filtered": len(filtered),
                "analyzed": len(analyzed_results),
                "high_confidence": sum(1 for r in analyzed_results if r["confidence"] > 0.65),
                "trades_executed": len(executed_trades),
                "positions_active": len(self._active_positions),
                "pending_review": len(self._feed_cache),
            }

            log.info(
                f"[POLYMARKET RSS FLUX] Batch {batch_id} complete: "
                f"{summary['opportunities_filtered']} filtered, "
                f"{summary['high_confidence']} high-confidence, "
                f"{summary['trades_executed']} trades"
            )

            return summary

        except Exception as exc:
            log.error(f"[POLYMARKET RSS FLUX] Batch processing failed: %s", exc, exc_info=True)
            return {
                "batch_id": batch_id,
                "error": str(exc),
                "status": "failed",
            }

    async def _execute_market_scanner(self) -> List[Dict[str, Any]]:
        """Execute market scanning task via Workforce.

        Returns list of markets from Polymarket API.
        """
        scanner_content = (
            f"Scan Polymarket for active markets.\n\n"
            f"**TASK:**\n"
            f"1. Use search_markets() to find markets (no filter = all active)\n"
            f"2. Use get_trending_markets(timeframe='24h', limit={self.batch_size}) for high-activity markets\n"
            f"3. Return market summaries with ID, title, odds, volume, liquidity\n\n"
            f"**OUTPUT:** [Market Scan Result] with {self.batch_size} market records."
        )

        scanner_task = Task(content=scanner_content)

        try:
            # Execute task through workforce
            result = await self._execute_task(scanner_task, "market_scanner")
            return result.get("markets", []) if result else []
        except Exception as exc:
            log.warning("[POLYMARKET RSS FLUX] Market scan failed: %s", exc)
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

    async def _analyze_and_decide(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market and make trade decision via Workforce.

        Performs multi-stage analysis:
        1. Get market details (orderbook, recent trades)
        2. Analyze sentiment (news, social)
        3. Analyze prices and trends (all intervals)
        4. Calculate opportunity score
        5. Return BUY/SELL/SKIP decision

        Returns:
            Decision dict with confidence score
        """
        market_id = market_data.get("id", "unknown")

        analysis_content = (
            f"Analyze Polymarket opportunity: {market_data.get('title', 'Unknown')}\n\n"
            f"**MARKET DETAILS:**\n"
            f"- ID: {market_id}\n"
            f"- Volume 24h: ${market_data.get('volume_24h', 0)}\n"
            f"- Liquidity: {market_data.get('liquidity_score', 0)}%\n"
            f"- Spread: {market_data.get('bid_ask_spread', 0)}%\n\n"
            f"**ANALYSIS STEPS:**\n"
            f"1. Use get_market_details() for full market data\n"
            f"2. Use get_orderbook() to check bid-ask depth and balance\n"
            f"3. Analyze market activity patterns\n"
            f"4. Analyze price trends:\n"
            f"   - Current Yes/No odds\n"
            f"   - Recent price movements\n"
            f"   - Compare to forecasting trends if available\n"
            f"5. Consensus copy risk check:\n"
            f"   - Estimate crowd consensus (if available)\n"
            f"   - Compare to market implied probability\n"
            f"   - Estimate copy_trade_edge and win-rate\n"
            f"6. Score opportunity:\n"
            f"   - If strong signals & low risk: BUY (confidence > 0.65)\n"
            f"   - If mixed signals: HOLD (confidence 0.4-0.65)\n"
            f"   - If weak or risky: SKIP (confidence < 0.4)\n\n"
            f"**OUTPUT:** Decision (BUY/HOLD/SKIP), confidence (0.0-1.0), explanation.\n"
            f"Include consensus_analysis with copy_trade_edge and estimated_win_rate."
        )

        analysis_task = Task(content=analysis_content)

        try:
            result = await self._execute_task(analysis_task, f"market_analysis_{market_id[:8]}")

            return {
                "market_id": market_id,
                "market_title": market_data.get("title"),
                "decision": result.get("decision", "SKIP"),
                "confidence": result.get("confidence", 0.0),
                "sentiment_score": result.get("sentiment_score", 0.0),
                "opportunity_score": result.get("opportunity_score", 0.0),
                "reasoning": result.get("reasoning", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            log.warning(f"[POLYMARKET RSS FLUX] Analysis failed for {market_id}: {exc}")
            return {
                "market_id": market_id,
                "decision": "SKIP",
                "confidence": 0.0,
                "error": str(exc),
            }

    async def _execute_trade(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trade via Workforce if conditions are met.

        Checks daily trade limits and confidence thresholds before execution.

        Returns:
            Trade execution result (success/failure, position details)
        """
        market_id = analysis_result["market_id"]
        confidence = analysis_result["confidence"]

        # Reset daily trade count if date changed
        today = datetime.now(timezone.utc).date()
        if today > self._trade_day:
            self._trades_today = 0
            self._trade_day = today

        # Check daily trading limit
        if self._trades_today >= self.config.max_trades_per_day:
            log.warning(
                "[POLYMARKET RSS FLUX] Daily trading limit reached: %d/%d",
                self._trades_today,
                self.config.max_trades_per_day,
            )
            return {
                "status": "skipped",
                "market_id": market_id,
                "reason": f"Daily trading limit reached ({self._trades_today}/{self.config.max_trades_per_day})",
            }

        # Check confidence threshold
        if confidence < self.config.min_confidence:
            log.debug(
                "[POLYMARKET RSS FLUX] Confidence below threshold: %.2f < %.2f",
                confidence,
                self.config.min_confidence,
            )
            return {
                "status": "skipped",
                "market_id": market_id,
                "reason": f"Confidence below threshold ({confidence:.2f} < {self.config.min_confidence:.2f})",
            }

        trade_content = (
            f"Execute trade for Polymarket opportunity.\n\n"
            f"**MARKET:** {analysis_result['market_title']}\n"
            f"**DECISION:** {analysis_result['decision']}\n"
            f"**CONFIDENCE:** {confidence:.2%}\n"
            f"**REASONING:** {analysis_result['reasoning']}\n\n"
            f"**TASK:**\n"
            f"1. Validate market still meets criteria (get_market_details)\n"
            f"2. Calculate position size based on account balance and confidence\n"
            f"3. Execute trade:\n"
            f"   - For mock trading: Log position to memory\n"
            f"   - For real: Use Polymarket trading endpoints\n"
            f"4. Record position details (entry price, size, timestamp)\n"
            f"5. Set stop-loss and take-profit levels\n\n"
            f"**OUTPUT:** Trade execution result with position ID or error."
        )

        trade_task = Task(content=trade_content)

        try:
            result = await self._execute_task(trade_task, f"trade_executor_{market_id[:8]}")

            position_id = result.get("position_id", f"pos_{market_id}_{int(datetime.now(timezone.utc).timestamp())}")
            self._active_positions[position_id] = {
                "market_id": market_id,
                "market_title": analysis_result["market_title"],
                "entry_price": result.get("entry_price", 0.5),
                "position_size": result.get("position_size", 0.1),
                "confidence": confidence,
                "entry_time": datetime.now(timezone.utc).isoformat(),
                "status": "OPEN",
            }

            self._trades_today += 1
            log.info(
                f"[POLYMARKET RSS FLUX] Trade executed: {position_id} "
                f"({analysis_result['market_title']} @ {confidence:.2%} confidence)"
            )

            return {
                "status": "success",
                "position_id": position_id,
                "market_id": market_id,
                "entry_price": result.get("entry_price"),
                "position_size": result.get("position_size"),
            }

        except Exception as exc:
            log.warning(f"[POLYMARKET RSS FLUX] Trade execution failed for {market_id}: {exc}")
            return {
                "status": "failed",
                "market_id": market_id,
                "error": str(exc),
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
            if hasattr(self.workforce, "process_task"):
                log.debug(f"[POLYMARKET RSS FLUX] Using process_task")
                result = await self.workforce.process_task(task)
            elif hasattr(self.workforce, "execute_task"):
                log.debug(f"[POLYMARKET RSS FLUX] Using execute_task")
                result = await self.workforce.execute_task(task)
            elif hasattr(self.workforce, "run"):
                log.debug(f"[POLYMARKET RSS FLUX] Using run")
                result = await self.workforce.run(task)
            else:
                log.warning(f"[POLYMARKET RSS FLUX] Workforce has no task execution method")
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
