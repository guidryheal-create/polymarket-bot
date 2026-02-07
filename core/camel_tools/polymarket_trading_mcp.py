"""
Polymarket Trading Toolkit for CAMEL and MCP.

Provides tools for:
- Market discovery (crypto/stock focus)
- Price data retrieval  
- Trade execution (buy/sell positions)
- Position monitoring
- Trade result tracking

OpenAI-compatible tool schemas with simple types (no Pydantic).
"""

from typing import Dict, Any, List, Optional, Annotated
from datetime import datetime
import asyncio
import logging

from pydantic import Field
from core.logging import log
from core.clients.polymarket_client import PolymarketClient
from core.config import settings

try:
    from camel.toolkits import FunctionTool
    CAMEL_TOOLS_AVAILABLE = True
except ImportError:
    FunctionTool = None
    CAMEL_TOOLS_AVAILABLE = False

logger = logging.getLogger(__name__)


class PolymarketTradingResult:
    """Track and store polymarket trading results."""
    
    def __init__(self):
        """Initialize result tracker."""
        self.results: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
    
    def add_result(self, operation: str, success: bool, data: Dict[str, Any]) -> None:
        """Add operation result to tracker."""
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "success": success,
            "data": data
        }
        self.results.append(result)
        if operation == "trade":
            self.trades.append(result)
    
    def get_latest(self, operation: Optional[str] = None, count: int = 10) -> List[Dict[str, Any]]:
        """Get latest results, optionally filtered by operation."""
        if operation:
            filtered = [r for r in self.results if r["operation"] == operation]
        else:
            filtered = self.results
        return filtered[-count:]
    
    def get_trades(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get latest trades."""
        return self.trades[-count:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get results summary."""
        successful = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - successful
        
        return {
            "total_operations": len(self.results),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self.results) if self.results else 0,
            "total_trades": len(self.trades),
            "latest_operations": self.get_latest(count=5)
        }


class PolymarketTradingToolkit:
    """Polymarket trading toolkit with MCP and OpenAI-compatible schemas."""
    
    def __init__(self, polymarket_client: Optional[PolymarketClient] = None):
        """Initialize toolkit with Polymarket client."""
        self.client = polymarket_client or PolymarketClient()
        self.result_tracker = PolymarketTradingResult()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the toolkit."""
        try:
            self._initialized = True
            log.info("PolymarketTradingToolkit initialized")
        except Exception as e:
            log.error(f"Toolkit initialization error: {e}")
            self._initialized = False
    
    # ========================================================================
    # MARKET DISCOVERY & DATA RETRIEVAL
    # ========================================================================
    
    async def search_crypto_markets(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for cryptocurrency prediction markets.
        
        Focus: Bitcoin, Ethereum, Solana, and other major crypto assets.
        
        Args:
            query: Search query (e.g., "bitcoin price", "ethereum above 3000")
            limit: Max markets to return (default: 10, max: 50)
            
        Returns:
            Dict with search results or error message
        """
        try:
            if not isinstance(query, str) or not query.strip():
                result_data = {"error": "Query must be non-empty string"}
                self.result_tracker.add_result("search_crypto_markets", False, result_data)
                return {"success": False, **result_data}
            
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                result_data = {"error": "Limit must be between 1 and 50"}
                self.result_tracker.add_result("search_crypto_markets", False, result_data)
                return {"success": False, **result_data}
            
            # Search with crypto focus
            crypto_queries = [query, f"crypto {query}", f"price {query}"]
            all_markets = []
            
            for q in crypto_queries:
                markets = await self.client.search_markets(q, limit=limit)
                all_markets.extend(markets)
            
            # Deduplicate and filter to crypto
            unique_markets = {}
            for m in all_markets:
                market_id = m.get("id")
                if market_id not in unique_markets:
                    unique_markets[market_id] = m
            def _is_crypto(m: Dict[str, Any]) -> bool:
                cat = str(m.get("category", "")).lower()
                if "crypto" in cat:
                    return True
                tags = m.get("tags") or []
                if isinstance(tags, str):
                    tags = [tags]
                for t in tags:
                    if "crypto" in str(t).lower():
                        return True
                return False

            markets = [m for m in unique_markets.values() if _is_crypto(m)]
            if not markets:
                markets = list(unique_markets.values())
            markets = markets[:limit]
            
            result_data = {
                "query": query,
                "found": len(markets),
                "markets": [{
                    "id": m.get("id"),
                    "title": m.get("title"),
                    "liquidity": m.get("liquidity", 0),
                    "volume_24h": m.get("volume_24h", 0),
                    "mid_price": m.get("mid_price", 0)
                } for m in markets]
            }
            
            self.result_tracker.add_result("search_crypto_markets", True, result_data)
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {"error": str(e), "query": query}
            self.result_tracker.add_result("search_crypto_markets", False, error_data)
            log.error(f"Crypto market search error: {e}")
            return {"success": False, **error_data}
    
    async def search_stock_markets(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for stock/commodities prediction markets.
        
        Focus: S&P 500, Tech stocks, indices.
        
        Args:
            query: Search query (e.g., "S&P 500", "Apple stock price")
            limit: Max markets to return (default: 10, max: 50)
            
        Returns:
            Dict with search results or error message
        """
        try:
            if not isinstance(query, str) or not query.strip():
                result_data = {"error": "Query must be non-empty string"}
                self.result_tracker.add_result("search_stock_markets", False, result_data)
                return {"success": False, **result_data}
            
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                result_data = {"error": "Limit must be between 1 and 50"}
                self.result_tracker.add_result("search_stock_markets", False, result_data)
                return {"success": False, **result_data}
            
            # Search with stock focus
            stock_queries = [query, f"stock {query}", f"{query} price"]
            all_markets = []
            
            for q in stock_queries:
                markets = await self.client.search_markets(q, limit=limit)
                all_markets.extend(markets)
            
            unique_markets = {}
            for m in all_markets:
                market_id = m.get("id")
                if market_id not in unique_markets:
                    unique_markets[market_id] = m
            
            markets = list(unique_markets.values())[:limit]
            
            result_data = {
                "query": query,
                "found": len(markets),
                "markets": [{
                    "id": m.get("id"),
                    "title": m.get("title"),
                    "liquidity": m.get("liquidity", 0),
                    "volume_24h": m.get("volume_24h", 0),
                    "mid_price": m.get("mid_price", 0)
                } for m in markets]
            }
            
            self.result_tracker.add_result("search_stock_markets", True, result_data)
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {"error": str(e), "query": query}
            self.result_tracker.add_result("search_stock_markets", False, error_data)
            log.error(f"Stock market search error: {e}")
            return {"success": False, **error_data}
    
    async def get_market_price(
        self,
        market_id: str
    ) -> Dict[str, Any]:
        """Get current price and orderbook for a market.
        
        Args:
            market_id: Polymarket market ID (unique identifier)
            
        Returns:
            Current price, bid/ask spread, and liquidity
        """
        try:
            if not isinstance(market_id, str) or not market_id.strip():
                result_data = {"error": "Market ID must be non-empty string"}
                self.result_tracker.add_result("get_market_price", False, result_data)
                return {"success": False, **result_data}
            
            market_details = await self.client.get_market_details(market_id)
            orderbook = await self.client.get_orderbook(market_id, depth=5)
            
            result_data = {
                "market_id": market_id,
                "title": market_details.get("title"),
                "mid_price": market_details.get("mid_price", 0),
                "liquidity": market_details.get("liquidity", 0),
                "volume_24h": market_details.get("volume_24h", 0),
                "bid": orderbook.get("bids", [{}])[0].get("price") if orderbook.get("bids") else None,
                "ask": orderbook.get("asks", [{}])[0].get("price") if orderbook.get("asks") else None,
                "spread": abs((orderbook.get("asks", [{}])[0].get("price", 0) or 0) - 
                           (orderbook.get("bids", [{}])[0].get("price", 0) or 0))
            }
            
            self.result_tracker.add_result("get_market_price", True, result_data)
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {"error": str(e), "market_id": market_id}
            self.result_tracker.add_result("get_market_price", False, error_data)
            log.error(f"Get market price error: {e}")
            return {"success": False, **error_data}
    
    # ========================================================================
    # TRADE EXECUTION
    # ========================================================================
    
    async def place_buy_order(
        self,
        market_id: str,
        quantity: int,
        price: float
    ) -> Dict[str, Any]:
        """Place a buy order for the YES token on a market.
        
        Args:
            market_id: Polymarket market ID
            quantity: Number of shares/contracts to buy (integer > 0)
            price: Limit price per share (0.01 to 0.99)
            
        Returns:
            Order execution result with order ID and status
        """
        try:
            # Validate inputs
            if not isinstance(market_id, str) or not market_id.strip():
                result_data = {"error": "Market ID must be non-empty string"}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            if not isinstance(quantity, int) or quantity <= 0:
                result_data = {"error": "Quantity must be positive integer"}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            if not isinstance(price, (int, float)) or price <= 0 or price >= 1:
                result_data = {"error": "Price must be between 0.01 and 0.99"}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            # Check authentication
            if not self.client.is_authenticated:
                result_data = {"error": "Not authenticated. Set POLYGON_PRIVATE_KEY to enable trading."}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            token_ids = await self.client.get_outcome_token_ids(market_id)
            token_id = token_ids.get("YES")
            if not token_id:
                result_data = {"error": "YES token ID not found for market", "market_id": market_id}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}

            # Place order (BUY YES)
            order = await self.client.place_order(
                token_id=token_id,
                side="BUY",
                quantity=quantity,
                price=price,
            )
            
            result_data = {
                "order_id": order.get("order_id"),
                "market_id": market_id,
                "outcome": "YES",
                "token_label": "yes token",
                "quantity": quantity,
                "price": price,
                "total_value": quantity * price,
                "status": order.get("status", "pending") if isinstance(order, dict) else "pending",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.result_tracker.add_result("trade", True, result_data)
            log.info(f"Buy order placed: {result_data}")
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "market_id": market_id,
                "quantity": quantity,
                "price": price
            }
            self.result_tracker.add_result("trade", False, error_data)
            log.error(f"Place buy order error: {e}")
            return {"success": False, **error_data}
    
    async def place_sell_order(
        self,
        market_id: str,
        quantity: int,
        price: float
    ) -> Dict[str, Any]:
        """Place a buy order for the NO token (Polymarket yes/no outcomes).
        
        Args:
            market_id: Polymarket market ID
            quantity: Number of shares/contracts to sell (integer > 0)
            price: Limit price per share (0.01 to 0.99)
            
        Returns:
            Order execution result with order ID and status
        """
        try:
            # Validate inputs
            if not isinstance(market_id, str) or not market_id.strip():
                result_data = {"error": "Market ID must be non-empty string"}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            if not isinstance(quantity, int) or quantity <= 0:
                result_data = {"error": "Quantity must be positive integer"}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            if not isinstance(price, (int, float)) or price <= 0 or price >= 1:
                result_data = {"error": "Price must be between 0.01 and 0.99"}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            # Check authentication
            if not self.client.is_authenticated:
                result_data = {"error": "Not authenticated. Set POLYGON_PRIVATE_KEY to enable trading."}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}
            
            token_ids = await self.client.get_outcome_token_ids(market_id)
            token_id = token_ids.get("NO")
            if not token_id:
                result_data = {"error": "NO token ID not found for market", "market_id": market_id}
                self.result_tracker.add_result("trade", False, result_data)
                return {"success": False, **result_data}

            # Place order (BUY NO)
            order = await self.client.place_order(
                token_id=token_id,
                side="BUY",
                quantity=quantity,
                price=price,
            )
            
            result_data = {
                "order_id": order.get("order_id"),
                "market_id": market_id,
                "outcome": "NO",
                "token_label": "no token",
                "quantity": quantity,
                "price": price,
                "total_value": quantity * price,
                "status": order.get("status", "pending") if isinstance(order, dict) else "pending",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.result_tracker.add_result("trade", True, result_data)
            log.info(f"Sell order placed: {result_data}")
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "market_id": market_id,
                "quantity": quantity,
                "price": price
            }
            self.result_tracker.add_result("trade", False, error_data)
            log.error(f"Place sell order error: {e}")
            return {"success": False, **error_data}
    
    # ========================================================================
    # POSITION & ORDER MONITORING
    # ========================================================================
    
    async def get_open_orders(self) -> Dict[str, Any]:
        """Get all open orders for authenticated account.
        
        Returns:
            List of open orders with details
        """
        try:
            if not self.client.is_authenticated:
                result_data = {"error": "Not authenticated"}
                self.result_tracker.add_result("get_open_orders", False, result_data)
                return {"success": False, **result_data}
            
            orders = await self.client.get_orders()
            
            result_data = {
                "order_count": len(orders),
                "orders": [{
                    "order_id": o.get("order_id"),
                    "market_id": o.get("market_id"),
                    "side": o.get("side"),
                    "quantity": o.get("quantity"),
                    "price": o.get("price"),
                    "status": o.get("status"),
                    "created_at": o.get("created_at")
                } for o in orders]
            }
            
            self.result_tracker.add_result("get_open_orders", True, result_data)
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {"error": str(e)}
            self.result_tracker.add_result("get_open_orders", False, error_data)
            log.error(f"Get open orders error: {e}")
            return {"success": False, **error_data}
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Cancellation result
        """
        try:
            if not isinstance(order_id, str) or not order_id.strip():
                result_data = {"error": "Order ID must be non-empty string"}
                self.result_tracker.add_result("cancel_order", False, result_data)
                return {"success": False, **result_data}
            
            if not self.client.is_authenticated:
                result_data = {"error": "Not authenticated"}
                self.result_tracker.add_result("cancel_order", False, result_data)
                return {"success": False, **result_data}
            
            result = await self.client.cancel_order(order_id)
            
            result_data = {
                "order_id": order_id,
                "status": result.get("status", "cancelled"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.result_tracker.add_result("cancel_order", True, result_data)
            log.info(f"Order cancelled: {order_id}")
            return {"success": True, **result_data}
            
        except Exception as e:
            error_data = {"error": str(e), "order_id": order_id}
            self.result_tracker.add_result("cancel_order", False, error_data)
            log.error(f"Cancel order error: {e}")
            return {"success": False, **error_data}
    
    # ========================================================================
    # RESULT TRACKING
    # ========================================================================
    
    def get_trade_results(self, limit: int = 10) -> Dict[str, Any]:
        """Get latest trade results.
        
        Args:
            limit: Number of latest trades to return
            
        Returns:
            List of recent trades with details
        """
        trades = self.result_tracker.get_trades(limit)
        return {
            "count": len(trades),
            "trades": trades
        }
    
    def get_operation_results(self, limit: int = 20) -> Dict[str, Any]:
        """Get all operation results (not just trades).
        
        Args:
            limit: Number of latest operations to return
            
        Returns:
            List of recent operations
        """
        results = self.result_tracker.get_latest(count=limit)
        return {
            "count": len(results),
            "results": results
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get toolkit operations summary."""
        return self.result_tracker.get_summary()
    
    # ========================================================================
    # CAMEL TOOL GENERATION
    # ========================================================================
    
    def get_tools(self) -> List[Any]:
        """Get list of CAMEL-compatible tools with OpenAI schemas.
        
        Returns:
            List of FunctionTool objects ready for CAMEL/GPT integration
        """
        if not CAMEL_TOOLS_AVAILABLE:
            return []
        
        toolkit = self
        
        tools = []
        
        # Search crypto markets tool
        async def search_crypto_markets_tool(
            query: Annotated[str, Field(description="Search query for crypto markets (e.g., 'bitcoin price', 'ethereum')")] = "bitcoin",
            limit: Annotated[int, Field(description="Max markets to return (1-50)")] = 10
        ) -> str:
            result = await toolkit.search_crypto_markets(query, limit)
            return str(result)
        
        tools.append(FunctionTool(
            func=search_crypto_markets_tool,
            description="Search for cryptocurrency prediction markets on Polymarket (Bitcoin, Ethereum, Solana, etc.). Perfect for finding markets related to crypto price predictions."
        ))
        
        # Search stock markets tool
        async def search_stock_markets_tool(
            query: Annotated[str, Field(description="Search query for stock markets (e.g., 'S&P 500', 'apple stock')")] = "S&P 500",
            limit: Annotated[int, Field(description="Max markets to return (1-50)")] = 10
        ) -> str:
            result = await toolkit.search_stock_markets(query, limit)
            return str(result)
        
        tools.append(FunctionTool(
            func=search_stock_markets_tool,
            description="Search for stock and commodities prediction markets on Polymarket (S&P 500, individual stocks, indices, etc.)."
        ))
        
        # Get market price tool
        async def get_market_price_tool(
            market_id: Annotated[str, Field(description="Polymarket market ID")]
        ) -> str:
            result = await toolkit.get_market_price(market_id)
            return str(result)
        
        tools.append(FunctionTool(
            func=get_market_price_tool,
            description="Get current price, bid/ask spread, and liquidity for a specific Polymarket market."
        ))
        
        # Place buy order tool
        async def place_buy_order_tool(
            market_id: Annotated[str, Field(description="Polymarket market ID")],
            quantity: Annotated[int, Field(description="Number of shares/contracts (must be > 0)")],
            price: Annotated[float, Field(description="Limit price (0.01 to 0.99)")]
        ) -> str:
            result = await toolkit.place_buy_order(market_id, quantity, price)
            return str(result)
        
        tools.append(FunctionTool(
            func=place_buy_order_tool,
            description="Place a buy order for a crypto or stock prediction market. Requires authentication (POLYGON_PRIVATE_KEY)."
        ))
        
        # Place sell order tool
        async def place_sell_order_tool(
            market_id: Annotated[str, Field(description="Polymarket market ID")],
            quantity: Annotated[int, Field(description="Number of shares/contracts (must be > 0)")],
            price: Annotated[float, Field(description="Limit price (0.01 to 0.99)")]
        ) -> str:
            result = await toolkit.place_sell_order(market_id, quantity, price)
            return str(result)
        
        tools.append(FunctionTool(
            func=place_sell_order_tool,
            description="Place a sell order to close a position or take profits. Requires authentication (POLYGON_PRIVATE_KEY)."
        ))
        
        # Get open orders tool
        async def get_open_orders_tool() -> str:
            result = await toolkit.get_open_orders()
            return str(result)
        
        tools.append(FunctionTool(
            func=get_open_orders_tool,
            description="Get all open orders for the authenticated account. Shows pending buy/sell orders."
        ))
        
        # Cancel order tool
        async def cancel_order_tool(
            order_id: Annotated[str, Field(description="Order ID to cancel")]
        ) -> str:
            result = await toolkit.cancel_order(order_id)
            return str(result)
        
        tools.append(FunctionTool(
            func=cancel_order_tool,
            description="Cancel an open order. Returns confirmation of cancellation."
        ))
        
        return tools
