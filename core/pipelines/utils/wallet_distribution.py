"""Wallet distribution calculator based on strategy outputs."""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict

from core.models.strategy import StrategyMode, STRATEGY_CONFIGS, get_strategy_config
from core.logging import log


def calculate_wallet_distribution(
    strategy_recommendations: Dict[str, Dict[str, Any]],
    reserve_percentage: float = 0.1,  # 10% reserve
) -> Dict[str, Any]:
    """
    Calculate stochastic wallet distribution per token across all strategies.
    
    Args:
        strategy_recommendations: Dict mapping ticker -> strategy -> recommendation
            Example: {
                "BTC": {
                    "wallet_balancing": {"action": "BUY", "percent_allocation": 0.15, "confidence": 0.8},
                    "trading": {"action": "BUY", "percent_allocation": 0.20, "confidence": 0.7},
                    ...
                }
            }
        reserve_percentage: Percentage of wallet to keep in reserve (default 10%)
    
    Returns:
        Dict with wallet distribution per token:
        {
            "ticker": {
                "total_allocation": 0.35,  # Sum across all strategies
                "reserve_allocation": 0.10,  # Reserve percentage
                "strategies": {
                    "wallet_balancing": {"allocation": 0.15, "weight": 0.43, "action": "BUY"},
                    "trading": {"allocation": 0.20, "weight": 0.57, "action": "BUY"},
                    ...
                },
                "weighted_action": "BUY",  # Most common action weighted by allocation
                "weighted_confidence": 0.75,  # Weighted average confidence
                "distribution": [0.15, 0.20, ...]  # Allocation per strategy
            }
        }
    """
    wallet_dist = {}
    available_allocation = 1.0 - reserve_percentage
    
    for ticker, strategies in strategy_recommendations.items():
        ticker_dist = {
            "total_allocation": 0.0,
            "reserve_allocation": reserve_percentage,
            "strategies": {},
            "weighted_action": "HOLD",
            "weighted_confidence": 0.0,
            "distribution": [],
            "actions": defaultdict(float),  # action -> weighted sum
            "confidence_sum": 0.0,
            "allocation_sum": 0.0,
        }
        
        # Process each strategy's recommendation
        for strategy_name, recommendation in strategies.items():
            if not recommendation:
                continue
            
            action = recommendation.get("action", "HOLD")
            allocation = recommendation.get("percent_allocation", 0.0)
            confidence = recommendation.get("confidence", 0.0)
            
            # Skip HOLD actions with zero allocation
            if action == "HOLD" and allocation == 0.0:
                continue
            
            # Weight by strategy focus and interval
            strategy_config = get_strategy_config(strategy_name)
            strategy_weight = 1.0
            
            # Adjust weight based on strategy focus
            if strategy_config.focus == "minimize_loss":
                strategy_weight *= 1.2  # Slightly higher weight for loss minimization
            elif strategy_config.focus == "maximize_gain":
                strategy_weight *= 1.0
            
            # Adjust weight based on interval (longer intervals = more weight)
            if strategy_config.interval == "days":
                strategy_weight *= 1.5
            elif strategy_config.interval == "hours":
                strategy_weight *= 1.2
            elif strategy_config.interval == "minutes":
                strategy_weight *= 1.0
            
            # Weighted allocation (allocation * strategy_weight * confidence)
            weighted_allocation = allocation * strategy_weight * confidence
            
            ticker_dist["strategies"][strategy_name] = {
                "allocation": allocation,
                "weight": strategy_weight,
                "weighted_allocation": weighted_allocation,
                "action": action,
                "confidence": confidence,
            }
            
            # Accumulate for weighted averages
            ticker_dist["actions"][action] += weighted_allocation
            ticker_dist["confidence_sum"] += confidence * weighted_allocation
            ticker_dist["allocation_sum"] += weighted_allocation
            ticker_dist["distribution"].append(weighted_allocation)
        
        # Calculate weighted action (most common action weighted by allocation)
        if ticker_dist["actions"]:
            ticker_dist["weighted_action"] = max(
                ticker_dist["actions"].items(),
                key=lambda x: x[1]
            )[0]
        
        # Calculate weighted confidence
        if ticker_dist["allocation_sum"] > 0:
            ticker_dist["weighted_confidence"] = ticker_dist["confidence_sum"] / ticker_dist["allocation_sum"]
        
        # Store raw weighted allocation for later normalization
        total_weighted = sum(ticker_dist["distribution"])
        ticker_dist["raw_total_allocation"] = total_weighted
        wallet_dist[ticker] = ticker_dist
    
    # ✅ Normalize across ALL tickers to ensure 100% total (stochastic min-max normalization)
    if wallet_dist:
        # Step 1: Collect all raw allocations
        raw_allocations = [ticker_data["raw_total_allocation"] for ticker_data in wallet_dist.values()]
        
        # Step 2: Min-max normalization (stochastic distribution)
        min_allocation = min(raw_allocations) if raw_allocations else 0.0
        max_allocation = max(raw_allocations) if raw_allocations else 0.0
        range_allocation = max_allocation - min_allocation if max_allocation > min_allocation else 1.0
        
        # Step 3: Normalize each ticker using min-max formula: (x - min) / (max - min) * 100
        normalized_allocations = []
        for ticker, ticker_data in wallet_dist.items():
            raw = ticker_data["raw_total_allocation"]
            if range_allocation > 0:
                # Min-max normalization: (x - min) / (max - min)
                normalized = (raw - min_allocation) / range_allocation
            else:
                # If all values are the same (including all zeros), distribute equally
                normalized = 1.0 / len(wallet_dist) if wallet_dist else 0.0
            
            normalized_allocations.append((ticker, normalized))
        
        # Step 4: Scale to available allocation (1.0 - reserve) to ensure 100% total
        total_normalized = sum(norm for _, norm in normalized_allocations)
        if total_normalized > 0:
            scale_factor = available_allocation / total_normalized
        else:
            # ✅ Pure agentic: if all raw allocations are zero, do NOT invent allocations.
            # Leave all tickers at 0 so upstream can detect "no valid allocation" and decide what to do.
            log.info(
                "[WALLET DIST] All raw allocations are zero; keeping total_allocation=0 for all tickers "
                "(no heuristic equal-split fallback applied)."
            )
            for ticker, ticker_data in wallet_dist.items():
                ticker_data["total_allocation"] = 0.0
                for strategy_name in ticker_data["strategies"]:
                    ticker_data["strategies"][strategy_name]["normalized_allocation"] = 0.0
                ticker_data.pop("raw_total_allocation", None)
            return wallet_dist
        
        # Step 5: Apply final allocation to each ticker
        for ticker, normalized in normalized_allocations:
            ticker_data = wallet_dist[ticker]
            final_allocation = normalized * scale_factor
            
            # Ensure we don't exceed available allocation
            ticker_data["total_allocation"] = min(final_allocation, available_allocation)
            
            # Normalize individual strategy allocations proportionally
            if ticker_data["raw_total_allocation"] > 0:
                strategy_scale = ticker_data["total_allocation"] / ticker_data["raw_total_allocation"]
                for strategy_name in ticker_data["strategies"]:
                    ticker_data["strategies"][strategy_name]["normalized_allocation"] = (
                        ticker_data["strategies"][strategy_name]["weighted_allocation"] * strategy_scale
                    )
            else:
                # ✅ If raw allocation is 0 but we have a normalized allocation, distribute it equally among strategies
                if ticker_data["total_allocation"] > 0:
                    equal_strategy_allocation = ticker_data["total_allocation"] / len(ticker_data["strategies"]) if ticker_data["strategies"] else 0.0
                    for strategy_name in ticker_data["strategies"]:
                        ticker_data["strategies"][strategy_name]["normalized_allocation"] = equal_strategy_allocation
                else:
                    for strategy_name in ticker_data["strategies"]:
                        ticker_data["strategies"][strategy_name]["normalized_allocation"] = 0.0
            
            # Remove raw_total_allocation from final output (internal use only)
            ticker_data.pop("raw_total_allocation", None)
    else:
        # No tickers with allocations
        for ticker_data in wallet_dist.values():
            ticker_data["total_allocation"] = 0.0
            ticker_data.pop("raw_total_allocation", None)
    
    # Verify total allocation sums to available_allocation (within rounding)
    total_allocated = sum(ticker_data.get("total_allocation", 0.0) for ticker_data in wallet_dist.values())
    log.info(
        f"[WALLET DIST] Calculated distribution for {len(wallet_dist)} tickers "
        f"(reserve: {reserve_percentage*100:.1f}%, available: {available_allocation*100:.1f}%, "
        f"total allocated: {total_allocated*100:.2f}%)"
    )
    
    # Warn if total doesn't match expected (should be within 0.1% due to rounding)
    if abs(total_allocated - available_allocation) > 0.001:
        log.warning(
            f"[WALLET DIST] ⚠️  Total allocation ({total_allocated*100:.2f}%) doesn't match available "
            f"({available_allocation*100:.2f}%) - difference: {(total_allocated - available_allocation)*100:.2f}%"
        )
    
    return wallet_dist


def format_wallet_distribution_response(
    wallet_dist: Dict[str, Any],
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Format wallet distribution for response format.
    
    Returns:
        {
            "wallet_distribution": {
                "ticker": {
                    "total_allocation": 0.35,
                    "reserve_allocation": 0.10,
                    "weighted_action": "BUY",
                    "weighted_confidence": 0.75,
                    "strategies": {...}
                }
            },
            "reserve_percentage": 0.1,
            "total_allocated": 0.65,
            "timestamp": "2025-11-19T..."
        }
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    total_allocated = sum(
        ticker_data.get("total_allocation", 0.0)
        for ticker_data in wallet_dist.values()
    )
    
    reserve_percentage = next(
        (ticker_data.get("reserve_allocation", 0.1) for ticker_data in wallet_dist.values()),
        0.1
    ) if wallet_dist else 0.1

    # Derive lightweight signals for frontend if not provided upstream.
    buy_signals: List[Dict[str, Any]] = []
    sell_signals: List[Dict[str, Any]] = []
    for ticker, ticker_data in wallet_dist.items():
        alloc = ticker_data.get("total_allocation", 0.0)
        action = ticker_data.get("weighted_action", "HOLD")
        confidence = ticker_data.get("weighted_confidence", 0.0)
        if alloc > 0:
            if action.upper() == "BUY":
                buy_signals.append({"ticker": ticker, "allocation": alloc, "confidence": confidence})
            elif action.upper() == "SELL":
                sell_signals.append({"ticker": ticker, "allocation": alloc, "confidence": confidence})

    ai_explanation = (
        "Deterministic fallback: no agentic explanation available (all allocations are zero)."
        if total_allocated == 0
        else "Aggregated wallet distribution using available strategy signals; see weighted_action per ticker."
    )

    return {
        "wallet_distribution": wallet_dist,
        "reserve_percentage": reserve_percentage,
        "total_allocated": total_allocated,
        "available_reserve": 1.0 - total_allocated - reserve_percentage,
        "timestamp": timestamp.isoformat(),
        "ai_explanation": ai_explanation,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
    }


def log_signals_to_redis(redis_client, strategy: str, buy_signals: List[Dict[str, Any]], sell_signals: List[Dict[str, Any]]):
    """
    Best-effort logging of signals for frontend/history.
    Does nothing if redis_client is None or not connected.
    """
    if not redis_client or not getattr(redis_client, "redis", None):
        return
    try:
        payload = {
            "strategy": strategy,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Store latest signals per strategy
        key = f"signals:{strategy}:latest"
        # Limit log length to avoid growth
        history_key = f"signals:{strategy}:history"
        # set_json is async; we assume redis_client methods are async
        # Callers should await these coroutines
        return key, history_key, payload
    except Exception:
        log.debug("Signal logging skipped (redis/logging optional).")
        return None

