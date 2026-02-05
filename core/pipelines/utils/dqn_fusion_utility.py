"""
DQN-style deterministic utility function for fusion decision-making.

This module implements a deterministic argmax-based utility calculation
that mimics DQN behavior without random sampling. All decisions are
deterministic and reproducible.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple, Any
from enum import Enum

from core.logging import log
from core.models import TradeAction


class FusionUtilityMethod(str, Enum):
    """Fusion utility calculation methods."""
    DQN_ARGMAX = "dqn_argmax"
    WEIGHTED_AVERAGE = "weighted_average"
    MAX_CONFIDENCE = "max_confidence"


def calculate_dqn_utility(
    action: str,
    distribution: Dict[str, float],
    value_estimate: float,
    risk_penalty: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate DQN-style expected utility for a given action.
    
    Formula: U(action) = w_p * P_fusion(action) + w_v * scaled_value(action) + w_r * risk_penalty(action)
    
    Args:
        action: Action to calculate utility for ("BUY", "HOLD", "SELL")
        distribution: Probability distribution over actions from fusion
        value_estimate: Expected return/score (typically -1.0 to 1.0)
        risk_penalty: Risk penalty score (0.0 to 1.0, higher = more risk)
        weights: Optional weights for probability, value, and risk components
        
    Returns:
        Utility score (0.0 to 1.0, higher = better)
    """
    if weights is None:
        weights = {
            "probability": 0.5,  # Weight for distribution probability
            "value": 0.3,        # Weight for value estimate
            "risk": 0.2,         # Weight for risk penalty
        }
    
    # Normalize distribution to ensure it sums to 1.0
    total_prob = sum(distribution.values())
    if total_prob > 0:
        normalized_dist = {k: v / total_prob for k, v in distribution.items()}
    else:
        # Uniform distribution if no probabilities
        normalized_dist = {k: 1.0 / 3.0 for k in ["BUY", "HOLD", "SELL"]}
    
    # P_fusion(action): Probability of this action from fusion distribution
    p_fusion = normalized_dist.get(action.upper(), 0.0)
    
    # scaled_value(action): Value estimate scaled to [0, 1]
    # For BUY: positive value is good, for SELL: negative value is good
    if action.upper() == "BUY":
        scaled_value = max(0.0, min(1.0, (value_estimate + 1.0) / 2.0))  # Map [-1, 1] to [0, 1]
    elif action.upper() == "SELL":
        scaled_value = max(0.0, min(1.0, (1.0 - value_estimate) / 2.0))  # Invert for SELL
    else:  # HOLD
        scaled_value = 0.5  # Neutral value for HOLD
    
    # risk_penalty(action): Risk penalty (higher risk = lower utility)
    # For BUY/SELL: high risk reduces utility, for HOLD: risk is neutral
    if action.upper() == "HOLD":
        risk_component = 0.5  # Neutral risk for HOLD
    else:
        risk_component = max(0.0, min(1.0, 1.0 - risk_penalty))  # Invert: lower risk = higher utility
    
    # Calculate utility
    utility = (
        weights["probability"] * p_fusion +
        weights["value"] * scaled_value +
        weights["risk"] * risk_component
    )
    
    return max(0.0, min(1.0, utility))  # Clamp to [0, 1]


def deterministic_fusion_argmax(
    trend_distribution: Optional[Dict[str, float]] = None,
    fact_distribution: Optional[Dict[str, float]] = None,
    memory_distribution: Optional[Dict[str, float]] = None,
    trend_value: float = 0.0,
    fact_value: float = 0.0,
    memory_value: float = 0.0,
    risk_penalty: float = 0.3,
    strategy_weights: Optional[Dict[str, float]] = None,
) -> Tuple[str, Dict[str, float], Dict[str, float]]:
    """
    Deterministic DQN-style argmax fusion decision.
    
    This function:
    1. Combines agent distributions into a fused distribution
    2. Calculates utility for each action (BUY, HOLD, SELL)
    3. Selects action with maximum utility (argmax)
    4. Returns action, fused distribution, and utility scores
    
    Args:
        trend_distribution: Trend agent's action distribution
        fact_distribution: Fact agent's action distribution
        memory_distribution: Memory agent's action distribution
        trend_value: Trend agent's value estimate
        fact_value: Fact agent's value estimate
        memory_value: Memory agent's value estimate
        risk_penalty: Overall risk penalty (0.0-1.0)
        strategy_weights: Optional weights per agent (default: equal weights)
        
    Returns:
        Tuple of (action, fused_distribution, utility_scores)
        - action: "BUY", "HOLD", or "SELL"
        - fused_distribution: Combined probability distribution
        - utility_scores: Utility score for each action
    """
    if strategy_weights is None:
        strategy_weights = {
            "trend": 0.4,
            "fact": 0.35,
            "memory": 0.25,
        }
    
    # Normalize strategy weights
    total_weight = sum(strategy_weights.values())
    if total_weight > 0:
        strategy_weights = {k: v / total_weight for k, v in strategy_weights.items()}
    else:
        strategy_weights = {"trend": 0.33, "fact": 0.33, "memory": 0.34}
    
    # Initialize fused distribution
    fused_dist = {"BUY": 0.0, "HOLD": 0.0, "SELL": 0.0}
    
    # Combine distributions with weights
    if trend_distribution:
        for action in ["BUY", "HOLD", "SELL"]:
            fused_dist[action] += trend_distribution.get(action, 0.0) * strategy_weights["trend"]
    
    if fact_distribution:
        for action in ["BUY", "HOLD", "SELL"]:
            fused_dist[action] += fact_distribution.get(action, 0.0) * strategy_weights["fact"]
    
    if memory_distribution:
        for action in ["BUY", "HOLD", "SELL"]:
            fused_dist[action] += memory_distribution.get(action, 0.0) * strategy_weights["memory"]
    
    # Normalize fused distribution
    total_prob = sum(fused_dist.values())
    if total_prob > 0:
        fused_dist = {k: v / total_prob for k, v in fused_dist.items()}
    else:
        # Uniform distribution if no probabilities (should not happen, but safety fallback)
        log.warning("[DQN FUSION] No probabilities from any agent, using uniform distribution")
        fused_dist = {"BUY": 0.33, "HOLD": 0.34, "SELL": 0.33}
    
    # Calculate average value estimate
    avg_value = (
        trend_value * strategy_weights["trend"] +
        fact_value * strategy_weights["fact"] +
        memory_value * strategy_weights["memory"]
    )
    
    # Calculate utility for each action
    utility_scores = {}
    for action in ["BUY", "HOLD", "SELL"]:
        utility_scores[action] = calculate_dqn_utility(
            action=action,
            distribution=fused_dist,
            value_estimate=avg_value,
            risk_penalty=risk_penalty,
        )
    
    # Argmax: select action with maximum utility
    best_action = max(utility_scores.items(), key=lambda x: x[1])[0]
    
    log.debug(
        f"[DQN FUSION] Argmax result: {best_action} "
        f"(utilities: BUY={utility_scores['BUY']:.3f}, "
        f"HOLD={utility_scores['HOLD']:.3f}, "
        f"SELL={utility_scores['SELL']:.3f})"
    )
    
    return best_action, fused_dist, utility_scores


def extract_agent_distribution(
    agent_output: Optional[Dict[str, Any]],
    agent_name: str,
) -> Tuple[Optional[Dict[str, float]], float]:
    """
    Extract decision distribution and value estimate from agent output.
    
    Args:
        agent_output: Agent's output dictionary (from Trend/Fact/Memory pipeline)
        agent_name: Name of agent ("TrendAgent", "FactAgent", "MemoryAgent")
        
    Returns:
        Tuple of (distribution, value_estimate)
        - distribution: {"BUY": 0.7, "HOLD": 0.2, "SELL": 0.1} or None
        - value_estimate: Expected return score (-1.0 to 1.0)
    """
    if not agent_output:
        return None, 0.0
    
    # ✅ Try to extract distribution from various possible locations
    # Priority: decision_distribution > distribution > build from action/confidence
    distribution = None
    
    # Method 1: Direct decision_distribution field (highest priority - new schema)
    if "decision_distribution" in agent_output:
        dist = agent_output["decision_distribution"]
        if isinstance(dist, dict) and len(dist) > 0:
            distribution = {k.upper(): float(v) for k, v in dist.items() if k.upper() in ["BUY", "HOLD", "SELL"]}
            if distribution and sum(distribution.values()) > 0:
                # Normalize if needed
                total = sum(distribution.values())
                if abs(total - 1.0) > 0.01:
                    distribution = {k: v / total for k, v in distribution.items()}
    
    # Method 2: Try "distribution" or "dist" field
    if not distribution:
        for field_name in ["distribution", "dist"]:
            if field_name in agent_output:
                dist = agent_output[field_name]
                if isinstance(dist, dict) and len(dist) > 0:
                    distribution = {k.upper(): float(v) for k, v in dist.items() if k.upper() in ["BUY", "HOLD", "SELL"]}
                    if distribution:
                        break
    
    # Method 3: Build from recommended_action and confidence (fallback)
    if not distribution:
        action = agent_output.get("recommended_action") or agent_output.get("action")
        confidence = float(agent_output.get("confidence", 0.5))
        
        if action:
            action_upper = str(action).upper()
            if action_upper in ["BUY", "HOLD", "SELL"]:
                # Create distribution with high probability for recommended action
                distribution = {"BUY": 0.0, "HOLD": 0.0, "SELL": 0.0}
                distribution[action_upper] = confidence
                # Distribute remaining probability evenly
                remaining = (1.0 - confidence) / 2.0
                for other_action in ["BUY", "HOLD", "SELL"]:
                    if other_action != action_upper:
                        distribution[other_action] = remaining
    
    # ✅ Extract value estimate (priority: value_estimate > trend_score/sentiment_score)
    value_estimate = 0.0
    if "value_estimate" in agent_output and agent_output["value_estimate"] is not None:
        value_estimate = float(agent_output.get("value_estimate", 0.0))
    elif "trend_score" in agent_output:
        # For trend agent, use trend_score as value estimate
        value_estimate = float(agent_output.get("trend_score", 0.5)) * 2.0 - 1.0  # Map [0, 1] to [-1, 1]
    elif "sentiment_score" in agent_output:
        # For fact agent, use sentiment_score as value estimate
        value_estimate = float(agent_output.get("sentiment_score", 0.0))
    
    return distribution, value_estimate

