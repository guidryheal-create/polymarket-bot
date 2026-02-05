"""
Enhanced Polymarket Toolkit for CAMEL Agents - Pure CAMEL-AI Implementation.

Provides comprehensive tools for accessing Polymarket prediction markets with
full CAMEL framework integration. Designed for seamless multi-agent usage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import asyncio
import concurrent.futures
from datetime import datetime

try:
    from camel.toolkits.base import BaseToolkit
    from camel.toolkits.function_tool import FunctionTool
    from camel.logger import get_logger
    CAMEL_TOOLS_AVAILABLE = True
except ImportError:
    BaseToolkit = object  # type: ignore
    FunctionTool = None
    CAMEL_TOOLS_AVAILABLE = False

if TYPE_CHECKING:
    from camel.toolkits.function_tool import FunctionTool as FunctionToolType
else:
    FunctionToolType = Any

from core.logging import log
from core.clients.polymarket_client import PolymarketClient

logger = get_logger(__name__)


def run_async(coro, timeout: float = 30.0) -> Any:
    """
    Run async coroutine safely in any context.
    
    Handles:
    - Already running event loop (runs in thread)
    - No event loop (creates new one)
    - Error cases
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                
                future = executor.submit(run_in_thread)
                return future.result(timeout=timeout)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            future = executor.submit(run_in_thread)
            return future.result(timeout=timeout)


class EnhancedPolymarketToolkit(BaseToolkit):
    """Enhanced Polymarket toolkit for CAMEL agents.
    
    Provides market discovery, analysis, portfolio management, and trading tools.
    """

    def __init__(self, timeout: Optional[float] = None):
        """Initialize toolkit.
        
        Args:
            timeout: Request timeout in seconds (default: 30.0)
        """
        super().__init__(timeout=timeout or 30.0)
        self.client = PolymarketClient(timeout=self.timeout)
        self._initialized = False

    async def _async_initialize(self) -> None:
        """Initialize toolkit (async)."""
        try:
            self._initialized = True
        except Exception as e:
            log.warning(f"Toolkit initialization: {e}")
            self._initialized = False

    def initialize(self) -> None:
        """Initialize toolkit (sync wrapper)."""
        run_async(self._async_initialize(), timeout=self.timeout)

    # ========================================================================
    # MARKET DISCOVERY
    # ========================================================================

    def search_markets(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search for markets by keyword."""
        def _normalize_market(market: Dict[str, Any]) -> Dict[str, Any]:
            title = market.get("title") or market.get("question") or market.get("name") or ""
            volume = market.get("volume_24h")
            if volume is None and isinstance(market.get("volume"), dict):
                volume = market.get("volume", {}).get("sum")
            return {
                **market,
                "market_id": market.get("market_id") or market.get("id") or market.get("condition_id"),
                "title": title,
                "volume_24h": volume,
            }

        async def _search():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                if not query or len(query) < 1:
                    return {"success": False, "error": "Query required (min 1 char)"}
                
                results = await self.client.search_markets(
                    query=query,
                    limit=max(1, min(limit, 100))
                )
                normalized = [_normalize_market(m) for m in results]
                
                return {
                    "success": True,
                    "markets": normalized,
                    "count": len(normalized),
                    "query": query
                }
            except Exception as e:
                log.error(f"Search error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_search(), timeout=self.timeout)

    def get_trending_markets(
        self,
        timeframe: str = "24h",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get trending markets by volume."""
        async def _trending():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                valid = ["24h", "7d", "30d"]
                tf = timeframe if timeframe in valid else "24h"
                
                results = await self.client.get_trending_markets(
                    timeframe=tf,
                    limit=max(1, min(limit, 100))
                )
                
                return {
                    "success": True,
                    "markets": results,
                    "count": len(results),
                    "timeframe": tf
                }
            except Exception as e:
                log.error(f"Trending error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_trending(), timeout=self.timeout)

    def get_markets_by_category(
        self,
        category: str,
        active_only: bool = True,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Filter markets by category."""
        async def _by_category():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                results = await self.client.filter_markets_by_category(
                    category=category,
                    active_only=active_only,
                    limit=max(1, min(limit, 100))
                )
                
                return {
                    "success": True,
                    "markets": results,
                    "count": len(results),
                    "category": category
                }
            except Exception as e:
                log.error(f"Category error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_by_category(), timeout=self.timeout)

    def get_markets_closing_soon(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get markets closing within specified hours."""
        async def _closing_soon():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                results = await self.client.get_closing_soon_markets(
                    hours=max(1, min(hours, 8760)),
                    limit=max(1, min(limit, 100))
                )
                
                return {
                    "success": True,
                    "markets": results,
                    "count": len(results),
                    "closing_within_hours": hours
                }
            except Exception as e:
                log.error(f"Closing soon error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_closing_soon(), timeout=self.timeout)

    # ========================================================================
    # MARKET ANALYSIS
    # ========================================================================

    def get_market_details(self, market_id: str) -> Dict[str, Any]:
        """Get market details."""
        async def _details():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                if not market_id:
                    return {"success": False, "error": "market_id required"}
                
                result = await self.client.get_market_details(market_id=market_id)
                return {"success": True, "market": result, "market_id": market_id}
            except Exception as e:
                log.error(f"Details error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_details(), timeout=self.timeout)

    def get_market_data(self, market_id: str) -> Dict[str, Any]:
        """Get current market price, orderbook, and other data."""
        async def _get_data():
            try:
                market_details = await self.client.get_market_details(market_id=market_id)
                if not market_details:
                    return {"status": "error", "message": "Market not found"}

                token_ids = await self.client.get_outcome_token_ids(market_id)
                token_id = token_ids.get("YES")
                if not token_id:
                    return {"status": "error", "message": "YES token ID not found in market details"}

                orderbook = await self.client.get_orderbook(token_id=token_id)

                bid = orderbook["bids"][0]["price"] if orderbook["bids"] else None
                ask = orderbook["asks"][0]["price"] if orderbook["asks"] else None
                mid_price = (bid + ask) / 2 if bid and ask else None
                spread = (ask - bid) if bid and ask else None
                
                created_at_str = market_details.get("created_at")
                market_age_hours = None
                if created_at_str:
                    try:
                        # Assuming format like '2024-01-03T10:00:00Z'
                        created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        market_age_hours = (datetime.now(created_at_dt.tzinfo) - created_at_dt).total_seconds() / 3600
                    except ValueError:
                        log.warning(f"Could not parse market creation date: {created_at_str}")


                return {
                    "status": "success",
                    "market_id": market_id,
                    "title": market_details.get("title")
                    or market_details.get("question")
                    or market_details.get("name")
                    or "",
                    "mid_price": mid_price,
                    "bid": bid,
                    "ask": ask,
                    "spread": spread,
                    "liquidity": market_details.get("liquidity"),
                    "volume_24h": market_details.get("volume", {}).get('sum'),
                    "market_age_hours": market_age_hours,
                    "orderbook": {
                        "bids": orderbook["bids"][:5],
                        "asks": orderbook["asks"][:5],
                    }
                }
            except Exception as e:
                log.error(f"Error getting market data for {market_id}: {e}")
                return {"status": "error", "message": str(e), "market_id": market_id}

        return run_async(_get_data(), timeout=self.timeout)

    def get_orderbook(
        self,
        market_id: str,
        depth: int = 10
    ) -> Dict[str, Any]:
        """Get orderbook for market."""
        async def _orderbook():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                if not market_id:
                    return {"success": False, "error": "market_id required"}
                
                market_details = await self.client.get_market_details(market_id=market_id)
                if not market_details:
                    return {"status": "error", "message": "Market not found"}
                
                token_ids = await self.client.get_outcome_token_ids(market_id)
                token_id = token_ids.get("YES")
                if not token_id:
                    return {"success": False, "error": "YES token ID not found in market details"}
                
                result = await self.client.get_orderbook(
                    token_id=token_id,
                    depth=max(1, min(depth, 50))
                )
                return {"success": True, "orderbook": result, "market_id": market_id}
            except Exception as e:
                log.error(f"Orderbook error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_orderbook(), timeout=self.timeout)

    def calculate_market_opportunity(
        self,
        market_id: str,
        confidence_threshold: float = 0.55
    ) -> Dict[str, Any]:
        """Calculate opportunity score for market."""
        async def _opportunity():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                if not market_id:
                    return {"success": False, "error": "market_id required"}
                
                market = await self.client.get_market_details(market_id=market_id)
                
                token_ids = await self.client.get_outcome_token_ids(market_id)
                token_id = token_ids.get("YES")
                if not token_id:
                    return {"success": False, "error": "YES token ID not found in market details"}

                orderbook = await self.client.get_orderbook(token_id=token_id)
                
                yes_price = market.get("yes_price", 0.5)
                no_price = 1 - yes_price
                volume = market.get("volume",{}).get('sum', 0)
                liquidity = orderbook.get("liquidity_score", 0) if orderbook else 0
                
                spread = abs(yes_price - no_price)
                opportunity_score = min(1.0, (volume / 10000.0) * (liquidity / 100.0))
                
                if yes_price > confidence_threshold:
                    signal = "BUY_YES"
                    confidence = yes_price
                elif no_price > confidence_threshold:
                    signal = "BUY_NO"
                    confidence = no_price
                else:
                    signal = "HOLD"
                    confidence = max(yes_price, no_price)
                
                return {
                    "success": True,
                    "market_id": market_id,
                    "opportunity_score": opportunity_score,
                    "signal": signal,
                    "confidence": confidence,
                    "spread": spread,
                    "volume_24h": volume
                }
            except Exception as e:
                log.error(f"Opportunity error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_opportunity(), timeout=self.timeout)

    # ========================================================================
    # PORTFOLIO
    # ========================================================================

    def monitor_positions(self) -> Dict[str, Any]:
        """
        Monitor current open positions.
        NOTE: Not supported in native py-clob-client path yet.
        """
        async def _monitor():
            return {
                "status": "not_supported",
                "message": "Position monitoring is not available via native client yet.",
                "open_positions": [],
            }
        
        return run_async(_monitor(), timeout=self.timeout)

    def get_position_history(self, limit: int = 50, asset_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get closed/historical positions.
        NOTE: Not supported in native py-clob-client path yet.
        """
        async def _get_history():
            return {
                "status": "not_supported",
                "message": "Position history is not available via native client yet.",
                "history": [],
                "limit": limit,
                "asset_filter": asset_filter,
            }
        return run_async(_get_history(), timeout=self.timeout)

    def get_user_positions(self, user_address: str) -> Dict[str, Any]:
        """Get positions for user."""
        async def _positions():
            return {
                "status": "not_supported",
                "message": "User positions are not available via native client yet.",
                "positions": [],
                "count": 0,
                "user_address": user_address,
            }
        
        return run_async(_positions(), timeout=self.timeout)

    def calculate_portfolio_pnl(self, user_address: str) -> Dict[str, Any]:
        """Calculate portfolio P&L."""
        async def _pnl():
            return {
                "status": "not_supported",
                "message": "Portfolio P&L is not available via native client yet.",
                "pnl": {},
                "user_address": user_address,
            }
        
        return run_async(_pnl(), timeout=self.timeout)

    def get_portfolio_value(self, user_address: str) -> Dict[str, Any]:
        """Get portfolio total value."""
        async def _value():
            return {
                "status": "not_supported",
                "message": "Portfolio value is not available via native client yet.",
                "portfolio": {},
                "user_address": user_address,
            }
        
        return run_async(_value(), timeout=self.timeout)

    # ========================================================================
    # TRADING
    # ========================================================================

    def suggest_trade_size(
        self,
        market_id: str,
        portfolio_value: float,
        confidence: float,
        max_exposure_pct: float = 5.0
    ) -> Dict[str, Any]:
        """Calculate optimal trade size."""
        async def _size():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                if not market_id or portfolio_value <= 0:
                    return {"success": False, "error": "Invalid inputs"}
                
                confidence = max(0.0, min(1.0, confidence))
                max_exposure = (portfolio_value * max_exposure_pct) / 100.0
                
                if confidence < 0.55:
                    position_size = 0
                elif confidence < 0.65:
                    position_size = max_exposure * 0.25
                elif confidence < 0.75:
                    position_size = max_exposure * 0.50
                else:
                    position_size = max_exposure * 0.75
                
                return {
                    "success": True,
                    "suggested_size": position_size,
                    "max_allowed": max_exposure,
                    "confidence": confidence,
                    "sizing_strategy": "kelly_variant"
                }
            except Exception as e:
                log.error(f"Sizing error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_size(), timeout=self.timeout)

    def take_position(
        self,
        market_id: str,
        side: str,
        size: float,
        user_address: str
    ) -> Dict[str, Any]:
        """Execute trade to open position.
        
        Args:
            market_id: ID of market to trade
            side: "YES" or "NO" (buy Yes or No shares)
            size: Number of shares to buy
            user_address: User wallet address
        
        Returns:
            Trade execution result with position details
        """
        async def _take_position():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                # Validate inputs
                if not market_id or not user_address:
                    log.warning(f"[POLYMARKET] Missing required: market_id={market_id}, user={user_address}")
                    return {"success": False, "error": "market_id and user_address required"}
                
                if side not in ["YES", "NO"]:
                    log.warning(f"[POLYMARKET] Invalid side: {side}")
                    return {"success": False, "error": "side must be YES or NO"}
                
                if size <= 0:
                    log.warning(f"[POLYMARKET] Invalid size: {size}")
                    return {"success": False, "error": "size must be > 0"}
                
                # Execute trade via client
                log.info(f"[POLYMARKET] Taking position: market={market_id[:8]}..., side={side}, size={size}, user={user_address[:8]}...")
                
                token_ids = await self.client.get_outcome_token_ids(market_id)
                token_id = token_ids.get(side)
                if not token_id:
                    return {"success": False, "error": f"{side} token ID not found"}

                trade_result = await self.client.place_order(
                    token_id=token_id,
                    side="BUY",
                    quantity=size,
                    price=0.5,  # TODO: use derived price
                )
                
                log.info(f"[POLYMARKET] Position opened: {trade_result.get('id', 'unknown')}")
                
                return {
                    "success": True,
                    "transaction_id": trade_result.get("id"),
                    "market_id": market_id,
                    "side": side,
                    "size": size,
                    "entry_price": trade_result.get("price", 0),
                    "total_cost": trade_result.get("price", 0) * size,
                    "user_address": user_address
                }
            except Exception as e:
                log.error(f"[POLYMARKET] Position error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_take_position(), timeout=self.timeout)

    def close_position(
        self,
        market_id: str,
        side: str,
        size: float,
        user_address: str
    ) -> Dict[str, Any]:
        """Close existing position.
        
        Args:
            market_id: ID of market
            side: "YES" or "NO" (shares to sell)
            size: Number of shares to sell
            user_address: User wallet address
        
        Returns:
            Trade execution result with exit details
        """
        async def _close_position():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                if not market_id or not user_address:
                    log.warning(f"[POLYMARKET] Missing required: market_id={market_id}, user={user_address}")
                    return {"success": False, "error": "market_id and user_address required"}
                
                if side not in ["YES", "NO"]:
                    log.warning(f"[POLYMARKET] Invalid side: {side}")
                    return {"success": False, "error": "side must be YES or NO"}
                
                if size <= 0:
                    log.warning(f"[POLYMARKET] Invalid size: {size}")
                    return {"success": False, "error": "size must be > 0"}
                
                log.info(f"[POLYMARKET] Closing position: market={market_id[:8]}..., side={side}, size={size}")
                
                token_ids = await self.client.get_outcome_token_ids(market_id)
                token_id = token_ids.get(side)
                if not token_id:
                    return {"success": False, "error": f"{side} token ID not found"}

                trade_result = await self.client.place_order(
                    token_id=token_id,
                    side="SELL",
                    quantity=size,
                    price=0.5,  # TODO: use derived price
                )
                
                log.info(f"[POLYMARKET] Position closed: {trade_result.get('id', 'unknown')}")
                
                return {
                    "success": True,
                    "transaction_id": trade_result.get("id"),
                    "market_id": market_id,
                    "side": side,
                    "size": size,
                    "exit_price": trade_result.get("price", 0),
                    "proceeds": trade_result.get("price", 0) * size,
                    "user_address": user_address
                }
            except Exception as e:
                log.error(f"[POLYMARKET] Close error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_close_position(), timeout=self.timeout)

    def get_position_details(
        self,
        market_id: str,
        user_address: str
    ) -> Dict[str, Any]:
        """Get detailed position info for specific market.
        
        Args:
            market_id: ID of market
            user_address: User wallet address
        
        Returns:
            Position details including entry, current value, P&L
        """
        async def _position_details():
            return {
                "status": "not_supported",
                "message": "Position details are not available via native client yet.",
                "market_id": market_id,
                "user_address": user_address,
            }
        
        return run_async(_position_details(), timeout=self.timeout)

    # ========================================================================
    # UTILITIES
    # ========================================================================

    def get_market_categories(self) -> Dict[str, Any]:
        """Get available categories."""
        return {
            "success": True,
            "categories": [
                "Politics", "Sports", "Crypto", "Markets",
                "Technology", "Entertainment", "Society", "Science"
            ],
            "count": 8
        }

    def format_market_summary(self, market_id: str) -> Dict[str, Any]:
        """Format market summary for display."""
        async def _summary():
            try:
                if not self._initialized:
                    await self._async_initialize()
                
                market = await self.client.get_market_details(market_id=market_id)
                
                return {
                    "success": True,
                    "market_id": market_id,
                    "title": market.get("title")
                    or market.get("question")
                    or market.get("name")
                    or "",
                    "description": market.get("description", ""),
                    "yes_price": market.get("yes_price", 0.5),
                    "no_price": 1-market.get("yes_price", 0.5),
                    "volume_24h": market.get("volume", {}).get('sum',0),
                    "liquidity": market.get("liquidity", 0),
                    "closing_date": market.get("end_date_time", ""),
                    "categories": market.get("category", [])
                }
            except Exception as e:
                log.error(f"Summary error: {e}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        return run_async(_summary(), timeout=self.timeout)

    # ========================================================================
    # CAMEL REGISTRATION
    # ========================================================================

    def get_tools(self) -> List["FunctionToolType"]:
        """Return FunctionTool objects for CAMEL agents."""
        if not CAMEL_TOOLS_AVAILABLE or FunctionTool is None:
            logger.warning("CAMEL tools not available")
            return []
        
        toolkit = self
        
        try:
            from core.camel_tools.async_wrapper import create_function_tool
        except ImportError:
            logger.warning("async_wrapper not found, using basic tools")
            create_function_tool = FunctionTool
        
        tools = []
        
        # Search tool
        def search_tool(query: str, limit: int = 20) -> Dict[str, Any]:
            """Search markets by keyword"""
            return toolkit.search_markets(query=query, limit=limit)
        
        search_tool.__doc__ = "Search Polymarket for trading opportunities"
        tools.append(create_function_tool(search_tool))
        
        # Trending tool
        def trending_tool(timeframe: str = "24h", limit: int = 10) -> Dict[str, Any]:
            """Get trending markets"""
            return toolkit.get_trending_markets(timeframe=timeframe, limit=limit)
        
        trending_tool.__doc__ = "Get trending markets by volume"
        tools.append(create_function_tool(trending_tool))

        # Market Data tool
        def market_data_tool(market_id: str) -> Dict[str, Any]:
            """Get detailed data for a specific market, including orderbook."""
            return toolkit.get_market_data(market_id=market_id)
        
        market_data_tool.__doc__ = "Get detailed data for a specific market, including orderbook."
        tools.append(create_function_tool(market_data_tool))
        
        # Details tool
        def details_tool(market_id: str) -> Dict[str, Any]:
            """Get market details"""
            return toolkit.get_market_details(market_id=market_id)
        
        details_tool.__doc__ = "Get market details including prices"
        tools.append(create_function_tool(details_tool))
        
        # Opportunity tool
        def opportunity_tool(market_id: str, confidence_threshold: float = 0.55) -> Dict[str, Any]:
            """Calculate opportunity"""
            return toolkit.calculate_market_opportunity(
                market_id=market_id,
                confidence_threshold=confidence_threshold
            )
        
        opportunity_tool.__doc__ = "Calculate market opportunity score"
        tools.append(create_function_tool(opportunity_tool))
        
        # Sizing tool
        def sizing_tool(
            market_id: str,
            portfolio_value: float,
            confidence: float
        ) -> Dict[str, Any]:
            """Calculate position size"""
            return toolkit.suggest_trade_size(
                market_id=market_id,
                portfolio_value=portfolio_value,
                confidence=confidence
            )
        
        sizing_tool.__doc__ = "Calculate optimal position size"
        tools.append(create_function_tool(sizing_tool))
        
        logger.info(f"✅ Loaded {len(tools)} Polymarket tools for CAMEL (including trading)")
        return tools


# Backward compatibility alias
PolymarketToolkit = EnhancedPolymarketToolkit

__all__ = ["EnhancedPolymarketToolkit", "PolymarketToolkit"]
