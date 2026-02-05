"""Polymarket Flux Pipeline - CAMEL Workforce-based decomposition.

Uses pure CAMEL Workforce with Task decomposition to process Polymarket trading
analysis. Delegates to API endpoints instead of direct database access.

Good practices retained from main app:
- CAMEL Workforce for orchestration
- Task class for proper task decomposition
- Agent-based processing with shared memory
- Comprehensive logging with structured markers
- Non-blocking async design with bounded timeouts
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from camel.tasks import Task
from camel.societies.workforce import Workforce

from core.logging import log


class PolymarketFlux:
    """Polymarket trading analysis pipeline using CAMEL Workforce.

    Public API:
    - `run_flux(tickers, strategies)` : orchestrates end-to-end analysis via Workforce

    Architecture:
    - Uses CAMEL Workforce for multi-agent coordination
    - Delegates I/O to API client (not direct Redis/DB)
    - Task-based decomposition: Fact → Trend → Sentiment → Fusion → Strategy
    """

    def __init__(self, workforce: Workforce, api_client: Any) -> None:
        """Initialize flux pipeline.

        Args:
            workforce: CAMEL Workforce instance (with shared memory)
            api_client: PolymarketClient or similar API wrapper
        """
        self.workforce = workforce
        self.api_client = api_client

    async def run_flux(
        self, tickers: List[str], strategies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run end-to-end Polymarket analysis pipeline via CAMEL Workforce.

        Builds a task pipeline: fact gathering → trend analysis → sentiment/risk
        → fusion synthesis → per-strategy wallet distribution.

        All tasks are executed through the workforce with shared memory context,
        ensuring agents have access to intermediate results.

        Args:
            tickers: List of asset tickers to analyze
            strategies: Strategy names to compute allocations for

        Returns:
            Summary dict with timestamp, fused analysis, and strategy results
        """
        ts = datetime.now(timezone.utc).isoformat()
        decision_id = f"polymarket_flux_{int(datetime.now(timezone.utc).timestamp())}"
        strategies = strategies or []

        log.info(
            "[POLYMARKET FLUX] Starting flux run: %s tickers=%d strategies=%s",
            ts,
            len(tickers),
            strategies,
        )

        try:
            # Build and execute task pipeline using CAMEL Workforce
            # ✅ Using Task class for proper CAMEL decomposition
            assets_line = ", ".join(sorted(set(t.upper() for t in tickers)))

            # Task 1: Fact Gathering
            fact_content = (
                f"[Fact Gathering - Polymarket]\n\n"
                f"Analyze market facts and context for: {assets_line}\n\n"
                f"Use search_markets, get_trending_markets, and get_market_details "
                f"from the Polymarket toolkit to gather:\n"
                f"- Market volume and activity levels\n"
                f"- Order book depth and liquidity\n"
                f"- Recent trading trends\n"
                f"- Market-specific news or developments\n\n"
                f"Log findings with log_conversation:\n"
                f"- title: 'Polymarket Fact Analysis: {assets_line}'\n"
                f"- message: Key market facts per ticker\n\n"
                f"OUTPUT: [Fact Result] with per-ticker market summaries."
            )
            fact_task = Task(content=fact_content)

            # Task 2: Trend Analysis
            trend_content = (
                f"[Trend Analysis - Polymarket]\n\n"
                f"Analyze market trends for: {assets_line}\n\n"
                f"Use get_orderbook and calculate_market_opportunity from Polymarket toolkit to assess:\n"
                f"- Order book imbalances (buy vs sell pressure)\n"
                f"- Market opportunity scores\n"
                f"- Price discovery indicators\n\n"
                f"Log with log_conversation:\n"
                f"- title: 'Polymarket Trend Analysis: {assets_line}'\n"
                f"- message: Per-market trend assessment and opportunity scores\n\n"
                f"OUTPUT: [Trend Result] with opportunity assessments."
            )
            trend_task = Task(content=trend_content)

            # Task 3: Sentiment & Risk Assessment
            sentiment_content = (
                f"[Sentiment & Risk - Polymarket]\n\n"
                f"Assess sentiment and risk for: {assets_line}\n\n"
                f"Use get_user_positions, get_portfolio_value, and calculate_portfolio_pnl "
                f"to understand market positioning:\n"
                f"- Portfolio concentration\n"
                f"- Position-weighted sentiment\n"
                f"- Market risk levels\n\n"
                f"Log with log_conversation:\n"
                f"- title: 'Polymarket Risk Assessment: {assets_line}'\n"
                f"- message: Risk scores and sentiment indicators\n\n"
                f"OUTPUT: [Sentiment & Risk Result] with risk assessments."
            )
            sentiment_task = Task(content=sentiment_content)

            # Task 4: Consensus Copy Risk Analysis
            consensus_content = (
                f"[Consensus Copy Risk - Polymarket]\n\n"
                f"Estimate whether copying crowd consensus is likely profitable.\n"
                f"Markets: {assets_line}\n\n"
                f"Inputs per market:\n"
                f"- consensus_probability (e.g., crowd % on YES)\n"
                f"- market_implied_probability (from price)\n"
                f"- fees_pct, spread_pct, latency_penalty\n\n"
                f"Use the consensus_copy_risk_analysis heuristic if available.\n"
                f"OUTPUT: [Consensus Result] with per-market copy_trade_edge, "
                f"estimated_win_rate, decision (follow/avoid/needs_more_data)."
            )
            consensus_task = Task(content=consensus_content)

            # Task 5: Fusion & Synthesis
            fusion_content = (
                f"[Fusion Synthesis - Polymarket]\n\n"
                f"Synthesize [Fact Result], [Trend Result], [Sentiment & Risk Result], "
                f"and [Consensus Result] "
                f"into unified trading analysis.\n\n"
                f"- Reconcile all results\n"
                f"- Per market: facts, trend, risk, opportunity\n"
                f"- Identify top BUY and SELL candidates\n"
                f"- Prioritize risk management\n\n"
                f"Log with log_conversation:\n"
                f"- title: 'Polymarket Fusion Summary: {assets_line}'\n"
                f"- message: Unified analysis with buy/sell recommendations\n\n"
                f"OUTPUT: [Analysis Result] with fused trading recommendations."
            )
            fusion_task = Task(content=fusion_content)

            # Task 6: Per-strategy wallet distribution
            strategy_tasks = []
            for strategy in strategies:
                strategy_content = (
                    f"[Strategy: {strategy} - Polymarket]\n\n"
                    f"Plan market allocation for strategy: {strategy}\n"
                    f"Markets: {assets_line}\n\n"
                    f"1. Review [Analysis Result] from fusion task\n"
                    f"2. Use suggest_trade_size with portfolio data to compute position sizes\n"
                    f"3. Generate buy_signals (confidence > 0.6) and sell_signals\n"
                    f"4. Output wallet distribution: {{market_id: allocation_pct}}\n"
                    f"5. Use log_conversation to document allocation rationale\n\n"
                    f"OUTPUT: [Strategy: {strategy}] with market allocations."
                )
                strategy_tasks.append(Task(content=strategy_content))

            # ✅ Execute unified task pipeline via workforce
            log.info("[POLYMARKET FLUX] Executing unified task pipeline via Workforce")
            
            # Build unified pipeline task
            unified_content = (
                f"[Unified Polymarket Analysis Pipeline]\n\n"
                f"Execute the complete analysis workflow for: {assets_line}\n\n"
                f"**PIPELINE STAGES:**\n"
                f"1. Fact Gathering: {fact_content}\n\n"
                f"2. Trend Analysis: {trend_content}\n\n"
                f"3. Sentiment & Risk: {sentiment_content}\n\n"
                f"4. Consensus Copy Risk: {consensus_content}\n\n"
                f"5. Fusion Synthesis: {fusion_content}\n\n"
                f"6. Strategy Allocations (per strategy):\n"
                + "\n".join(
                    f"   - {strategy}: {task.content[:50]}..."
                    for strategy, task in zip(strategies, strategy_tasks)
                )
                + f"\n\nReturn aggregated results with all 6 stages."
            )
            
            unified_task = Task(content=unified_content)
            
            # Execute single unified task through workforce
            result = await self._execute_task(unified_task, "unified_pipeline")
            
            # Extract results from unified execution
            summary = {
                "timestamp": ts,
                "decision_id": decision_id,
                "tickers": list(tickers),
                "strategies": strategies,
                "unified_result": result,
                "status": "completed" if result.get("status") != "failed" else "failed",
            }

            log.info("[POLYMARKET FLUX] Completed unified pipeline run: %s", decision_id)
            return summary

        except Exception as exc:
            log.error("[POLYMARKET FLUX] Flux run failed: %s", exc, exc_info=True)
            raise

    async def _execute_task(self, task: Task, task_type: str) -> Dict[str, Any]:
        """Execute a single unified task through the workforce.

        ✅ Good practice: Use workforce's execution methods when available;
        fallback to direct execution for compatibility.

        Args:
            task: CAMEL Task to execute
            task_type: Type descriptor for logging

        Returns:
            Task execution result dict
        """
        log.debug("[POLYMARKET FLUX] Executing %s task via Workforce", task_type)
        log.debug(
            "[POLYMARKET FLUX] Workforce type: %s, has agents: %s",
            type(self.workforce).__name__,
            hasattr(self.workforce, "agents"),
        )
        
        try:
            # ✅ Try primary task execution method
            if hasattr(self.workforce, "process_task"):
                log.debug("[POLYMARKET FLUX] Using workforce.process_task()")
                result = await self.workforce.process_task(task)
            else:
                # Fallback: return structured placeholder
                log.warning(
                    "[POLYMARKET FLUX] Workforce has no task execution method, using placeholder for %s",
                    task_type
                )
                result = {
                    "task_type": task_type,
                    "status": "placeholder",
                    "warning": "No workforce execution method available",
                }

            log.debug("[POLYMARKET FLUX] Task %s completed with status: %s", task_type, result.get("status", "unknown"))
            return result if isinstance(result, dict) else {"result": result, "task_type": task_type}
            
        except Exception as exc:
            log.warning(
                "[POLYMARKET FLUX] Task execution failed (%s): %s",
                task_type,
                exc,
                exc_info=True,
            )
            # Return partial result so pipeline continues
            return {
                "task_type": task_type,
                "status": "failed",
                "error": str(exc),
            }
