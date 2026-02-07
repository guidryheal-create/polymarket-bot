"""
Polymarket client supporting both public APIs and authenticated CLOB trading.

Supports two modes:
1. Public API (Gamma & CLOB read-only): https://gamma-api.polymarket.com, https://clob.polymarket.com
2. Authenticated CLOB client (py-clob-client): Private key + chain ID for trading

Reference: https://github.com/polymarket/py-clob-client
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import httpx
import json
from core.logging import log
from core.config import settings
from tests.test_api_main import client

# Public API URLs (no auth required)
GAMMA_API_URL = os.getenv("GAMMA_API_URL", "https://gamma-api.polymarket.com")
CLOB_API_URL = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")

# Try to import py-clob-client for authenticated trading
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        ApiCreds,
        OrderArgs,
        OrderType,
        OpenOrderParams,
        TradeParams,
        OrderScoringParams,
    )
    from py_clob_client.endpoints import ORDERS
    from py_clob_client.order_builder.constants import BUY, SELL
    from py_clob_client.constants import AMOY
    CLOB_CLIENT_AVAILABLE = True
except ImportError:
    ClobClient = None  # type: ignore
    ApiCreds = None  # type: ignore
    OrderArgs = None  # type: ignore
    OrderType = None  # type: ignore
    OpenOrderParams = None  # type: ignore
    TradeParams = None  # type: ignore
    OrderScoringParams = None  # type: ignore
    AMOY = 80002
    BUY = "BUY"
    SELL = "SELL"
    ORDERS = "/orders"
    CLOB_CLIENT_AVAILABLE = False


class PolymarketClient:
    """Polymarket client supporting public APIs and authenticated CLOB trading.
    
    Can operate in two modes:
    1. Public API mode (no authentication): read-only market data
    2. Authenticated mode: full trading capabilities via py-clob-client
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        private_key: Optional[str] = None,
        polygon_address: Optional[str] = None,
        chain_id: Optional[int] = None,
        host: Optional[str] = None
    ):
        """Initialize client.
        
        Args:
            timeout: Request timeout in seconds (default: 30.0)
            private_key: Wallet private key for authenticated mode (from env: POLYGON_PRIVATE_KEY)
            polygon_address: Wallet address (from env: POLYGON_ADDRESS)
            chain_id: Polygon chain ID (from env: POLYMARKET_CHAIN_ID, default: 80002 for testnet)
            host: CLOB API endpoint (default: https://clob.polymarket.com)
        """
        self.timeout = timeout
        self._clob_client: Optional[Any] = None  # ClobClient instance
        
        # Get credentials from settings, allowing override by direct arguments.
        self.private_key = private_key or settings.polygon_private_key
        self.polygon_address = polygon_address or settings.polygon_address
        self.chain_id = chain_id or settings.polymarket_chain_id
        
        self.host = host or os.getenv("CLOB_API_URL") or CLOB_API_URL
        self._api_creds = self._load_api_creds()
        
        # Initialize authenticated CLOB client if credentials provided
        if self.private_key and CLOB_CLIENT_AVAILABLE:
            self._init_clob_client()
        else:
            if self.private_key or self.polygon_address:
                log.warning(
                    "CLOB client not available: py-clob-client not installed or missing credentials. "
                    "Falling back to public API mode."
                )

    def refresh_from_env(self) -> None:
        """Reload credentials from environment and (re)initialize CLOB client."""
        print(settings.polygon_private_key)
        self.private_key = os.getenv("POLYGON_PRIVATE_KEY", settings.polygon_private_key)
        self.polygon_address = os.getenv("POLYGON_ADDRESS", settings.polygon_address) 
        self.chain_id = int(os.getenv("POLYMARKET_CHAIN_ID", settings.polymarket_chain_id) or 137)
        self.host = os.getenv("CLOB_API_URL") or self.host or CLOB_API_URL
        self._api_creds = self._load_api_creds()
        if self.private_key and CLOB_CLIENT_AVAILABLE:
            self._init_clob_client()

    def auth_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostic info for auth readiness."""
        return {
            "clob_client_available": CLOB_CLIENT_AVAILABLE,
            "has_private_key": bool(self.private_key),
            "has_polygon_address": bool(self.polygon_address),
            "has_api_creds": bool(self._api_creds),
            "chain_id": self.chain_id,
            "host": self.host,
            "is_authenticated": self.is_authenticated,
        }
    
    def _load_api_creds(self) -> Optional[Any]:
        """Load API credentials from environment if available."""
        if not CLOB_CLIENT_AVAILABLE or ApiCreds is None:
            return None
        api_key = os.getenv("POLYMARKET_API_KEY")
        api_secret = os.getenv("POLYMARKET_API_SECRET")
        api_passphrase = os.getenv("POLYMARKET_PASSPHRASE")
        if api_key and api_secret and api_passphrase:
            return ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
        return None

    def _init_clob_client(self) -> None:
        """Initialize the authenticated CLOB client."""
        try:
            if not CLOB_CLIENT_AVAILABLE:
                log.warning("py-clob-client not available. Install with: pip install py-clob-client")
                return

            # Create CLOB client with wallet credentials (py-clob-client examples methodology)
            self._clob_client = ClobClient(
                host=self.host,
                key=self.private_key,
                chain_id=self.chain_id,
                creds=self._api_creds,
            )

            # If API creds were not provided, derive them
            if self._api_creds is None:
                api_creds = self._clob_client.create_or_derive_api_creds()
                self._clob_client.set_api_creds(api_creds)
            
            log.info(f"✅ Authenticated CLOB client initialized (chain_id={self.chain_id}, address={self.polygon_address})")
        except Exception as e:
            log.warning(f"Failed to initialize CLOB client: {e}. Falling back to public API mode.")
            self._clob_client = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client has authenticated CLOB access."""
        return self._clob_client is not None
    
    async def close(self):
        """Close any authenticated client resources."""
        self._clob_client = None
    
    async def _fetch_gamma_api(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Fetch from Gamma API."""
        try:
            url = f"{GAMMA_API_URL}{endpoint}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params or {})
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log.error(f"Gamma API error for {endpoint}: {e}")
            raise
    
    async def _fetch_clob_api(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Fetch from CLOB public API."""
        try:
            url = f"{CLOB_API_URL}{endpoint}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params or {})
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log.error(f"CLOB API error for {endpoint}: {e}")
            raise
    
    async def get_market_details(
        self,
        market_id: Optional[str] = None,
        condition_id: Optional[str] = None,
        slug: Optional[str] = None,
        market_maker_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get complete market information.
        
        Args:
            market_id: Market ID
            condition_id: Condition ID (alternative identifier)
            slug: Market slug (alternative identifier)
            market_maker_address: Market maker address (alternative identifier)
        
        Returns:
            Full market object with all metadata
        """
        try:
            # Determine which identifier to use
            if market_maker_address:
                data = await self._fetch_gamma_api("/markets", {"marketMakerAddress": market_maker_address})
            elif slug:
                data = await self._fetch_gamma_api("/markets", {"slug": slug})
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                data = await self._fetch_gamma_api(f"/markets/{slug}")
            elif condition_id:
                data = await self._fetch_gamma_api("/markets", {"condition_id": condition_id})
            elif market_id:
                if isinstance(market_id, str) and market_id.startswith("0x") and len(market_id) == 42:
                    data = await self._fetch_gamma_api("/markets", {"marketMakerAddress": market_id})
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                data = await self._fetch_gamma_api(f"/markets/{market_id}")
            else:
                raise ValueError("One of market_id, condition_id, or slug must be provided")
            
            # Handle list response
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            
            return data
        except Exception as e:
            log.error(f"Failed to get market details: {e}")
            raise

    async def search_markets(
        self,
        query: str = "",
        limit: int = 20,
        page: int = 1,
        active_only: bool = True,
        sort: str = "volume_24hr",
    ) -> List[Dict[str, Any]]:
        """
        Search active Polymarket markets using the Gamma public search API.

        Server-side filtering & sorting to minimize payload size.
        """
        try:
            params = {
                "q": query,
                "page": page,
                "limit_per_type": limit,
                "type": "events",
                "sort": sort,
                "presets": ["EventsTitle", "Events"],
            }

            if active_only:
                params["events_status"] = "active"

            data = await self._fetch_gamma_api("/public-search", params)

            return data["events"]

        except Exception as e:
            log.error(f"Gamma market search failed: {e}")
            raise
    
    async def get_event_markets(
        self,
        event_slug: Optional[str] = None,
        event_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all markets for a specific event.
        
        Args:
            event_slug: Event slug (e.g., "presidential-election-2024")
            event_id: Event ID (alternative to slug)
        
        Returns:
            All markets belonging to the event
        """
        try:
            if not event_slug and not event_id:
                raise ValueError("Either event_slug or event_id must be provided")
            
            # First, get the event details
            if event_slug:
                event_data = await self._fetch_gamma_api(f"/events/{event_slug}")
            else:
                event_data = await self._fetch_gamma_api(f"/events/{event_id}")
            
            # Extract markets from event
            if isinstance(event_data, list) and len(event_data) > 0:
                event = event_data[0]
            else:
                event = event_data
            
            markets = event.get("markets", [])
            return markets
        except Exception as e:
            log.error(f"Failed to get event markets: {e}")
            raise
    
    async def filter_markets_by_category(
        self,
        category: str = "crypto",
        active_only: bool = True,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Filter markets by category or tag.
        
        Args:
            category: Category/tag to filter by (e.g., "Politics", "Sports", "Crypto")
            active_only: Only return active markets (default True)
            limit: Maximum number of results (default 20)
        
        Returns:
            Markets in the specified category
        """
        try:
            params = {"tag": category}
            
            if active_only:
                params["active"] = "true"
            
            if limit:
                params["limit"] = limit
            
            data = await self._fetch_gamma_api("/markets", params)
            
            # Handle different response formats
            if isinstance(data, list):
                return data[:limit] if limit else data
            elif isinstance(data, dict):
                if "data" in data:
                    return data["data"][:limit] if limit else data["data"]
                return [data]
            
            return []
        except Exception as e:
            log.error(f"Failed to filter markets by category: {e}")
            raise
    
    async def get_orderbook(
        self,
        token_id: str,
        depth: int = 20
    ) -> Dict[str, Any]:
        """Get complete order book.
        
        Args:
            token_id: Token ID
            depth: Number of price levels to return per side (default 20)
        
        Returns:
            Order book with bids and asks
        """
        try:
            book_data = await self._fetch_clob_api("/book", {"token_id": token_id})
            
            # Parse bids and asks
            bids = [
                {"price": float(entry["price"]), "size": float(entry["size"])}
                for entry in book_data.get("bids", [])[:depth]
            ]
            
            asks = [
                {"price": float(entry["price"]), "size": float(entry["size"])}
                for entry in book_data.get("asks", [])[:depth]
            ]
            
            return {
                "token_id": token_id,
                "bids": bids,
                "asks": asks
            }
        except Exception as e:
            log.error(f"Failed to get orderbook: {e}")
            raise

    async def get_trending_markets(
        self,
        timeframe: str = "24h",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        # correct timeframe schema
        # correct limit schema
        """Get trending markets by sorting on volume."""
        markets = await self._clob_client.get_markets("_c=15M&_s=volume_24hr&_sts=active&_l=4&_offset=0")
        
        return markets[:limit]

    async def get_closing_soon_markets(
        self,
        hours: int = 24,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get markets closing within the next N hours."""
        markets = await self._clob_client.get_markets("_c=15M&_s=volume_24hr&_sts=active&_l=4&_offset=0")
        now = datetime.utcnow()
        # maybe not close time and etc
        closing = []
        for m in markets:
            close_time = m.get("close_time") or m.get("closing_time") or m.get("end_time")
            if isinstance(close_time, str):
                try:
                    dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                except Exception:
                    continue
            elif isinstance(close_time, datetime):
                dt = close_time
            else:
                continue
            delta_hours = (dt - now).total_seconds() / 3600
            if 0 <= delta_hours <= hours:
                closing.append(m)
        return closing[:limit]

    def extract_outcome_token_ids(self, details: Dict[str, Any]) -> Dict[str, str]:
        """Extract YES/NO token IDs from a market details payload."""
        tokens = details.get("tokens", []) if isinstance(details, dict) else []
        outcome_map: Dict[str, str] = {}
        for token in tokens:
            outcome = str(token.get("outcome", "")).upper()
            token_id = token.get("token_id")
            if outcome in ("YES", "NO") and token_id:
                outcome_map[outcome] = str(token_id)
        if not outcome_map and isinstance(details, dict):
            clob_token_ids = details.get("clobTokenIds") or details.get("clob_token_ids")
            outcomes = details.get("outcomes")
            try:
                if isinstance(clob_token_ids, str):
                    clob_token_ids = json.loads(clob_token_ids)
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
            except Exception:
                pass
            if isinstance(clob_token_ids, list) and isinstance(outcomes, list):
                for outcome, token_id in zip(outcomes, clob_token_ids):
                    outcome_map[str(outcome).upper()] = str(token_id)
        if not outcome_map and isinstance(details, dict) and details.get("clob_token_id"):
            outcome_map["YES"] = str(details["clob_token_id"])
        return outcome_map

    async def get_outcome_token_ids(
        self,
        market_id: Optional[str] = None,
        condition_id: Optional[str] = None,
        slug: Optional[str] = None,
        market_maker_address: Optional[str] = None,
    ) -> Dict[str, str]:
        """Get YES/NO token IDs for a market."""
        details = await self.get_market_details(
            market_id=market_id,
            condition_id=condition_id,
            slug=slug,
            market_maker_address=market_maker_address,
        )
        return self.extract_outcome_token_ids(details)
    
    # ========================================
    # Authenticated Trading Methods (requires CLOB client)
    # ========================================
    
    async def get_balance(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Get account balance (authenticated mode only).
        
        Args:
            token: Optional token address. If None, returns USDC balance.
        
        Returns:
            Balance information
        """
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated. Provide private_key and polygon_address to enable trading.")
        
        try:
            if token:
                balance = self._clob_client.get_balance(token)
            else:
                # Get USDC balance by default
                balance = self._clob_client.get_balance()
            
            log.debug(f"Balance retrieved: {balance}")
            return {"balance": balance, "token": token or "USDC"}
        except Exception as e:
            log.error(f"Failed to get balance: {e}")
            raise
    
    async def place_order(
        self,
        token_id: str,
        side: str,  # "BUY" or "SELL"
        quantity: float,
        price: float,
        expiration: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Place a limit order via py-clob-client (authenticated mode only)."""
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated. Provide private_key to enable trading.")

        try:
            side_upper = side.upper()
            if side_upper not in ("BUY", "SELL"):
                raise ValueError(f"Invalid side: {side}. Must be 'BUY' or 'SELL'.")

            if OrderArgs is None or OrderType is None:
                raise RuntimeError("py-clob-client is not available for order placement.")
            # manage error and check format ? maybe a check if possible 
            expiration_value = expiration or os.getenv("CLOB_ORDER_EXPIRATION") or "1000000000000"
            order_args = OrderArgs(
                price=price,
                size=float(quantity),
                side=BUY if side_upper == "BUY" else SELL,
                token_id=str(token_id),
                expiration=str(expiration_value),
            )
            signed_order = self._clob_client.create_order(order_args)
            resp = self._clob_client.post_order(signed_order, OrderType.GTD)

            log.info(f"Order placed: {side_upper} {quantity} @ {price} (token_id={token_id})")
            return resp if isinstance(resp, dict) else {"response": resp}
        except Exception as e:
            log.error(f"Failed to place order: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order (authenticated mode only).
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Cancellation result
        """
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        
        try:
            result = self._clob_client.cancel(order_id)
            log.info(f"Order cancelled: {order_id}")
            return result
        except Exception as e:
            log.error(f"Failed to cancel order: {e}")
            raise
    
    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders (authenticated mode only).
        
        Returns:
            List of open orders
        """
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        
        try:
            orders = self._clob_client.get_orders()
            log.debug(f"Retrieved {len(orders)} open orders")
            return orders
        except Exception as e:
            log.error(f"Failed to get orders: {e}")
            raise

    async def get_open_orders(
        self,
        market: Optional[str] = None,
        maker_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get open orders with optional filtering (py-clob-client OpenOrderParams)."""
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        if OpenOrderParams is None:
            raise RuntimeError("py-clob-client OpenOrderParams unavailable.")

        try:
            if maker_address is None:
                params = OpenOrderParams(
                    market=market,
                    # taker=maker_address or self._clob_client.get_address(),
                )
                orders = self._clob_client.get_orders(params)
                log.debug(f"Retrieved {len(orders)} open orders (filtered)")
                return orders
            else :
                params = TradeParams(market=market, maker_address=maker_address)
                trades = self._clob_client.get_trades(params)
                return trades
        except Exception as e:
            log.error(f"Failed to get open orders: {e}")
            raise

    async def get_trades(
        self,
        market: Optional[str] = None,
        maker_address: Optional[str] = None,
        taker_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get trades (py-clob-client TradeParams)."""
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        if TradeParams is None:
            raise RuntimeError("py-clob-client TradeParams unavailable.")

        try:
            params = TradeParams(
                maker_address=maker_address or self._clob_client.get_address(),
                market=market,
            )
            trades = self._clob_client.get_trades(params)
            log.debug(f"Retrieved {len(trades)} trades")
            return trades
        except Exception as e:
            log.error(f"Failed to get trades: {e}")
            raise

    async def get_price(self, token_id: str, side: str = "BUY") -> Dict[str, Any]:
        """Get best price for a token and side (py-clob-client get_price)."""
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        try:
            result = self._clob_client.get_price(str(token_id), side.upper())
            return {"token_id": token_id, "side": side.upper(), "price": result}
        except Exception as e:
            log.error(f"Failed to get price: {e}")
            raise

    async def is_order_scoring(self, order_id: str) -> Dict[str, Any]:
        """Check if an order is scoring (py-clob-client OrderScoringParams)."""
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        if OrderScoringParams is None:
            raise RuntimeError("py-clob-client OrderScoringParams unavailable.")

        try:
            scoring = self._clob_client.is_order_scoring(
                OrderScoringParams(orderId=order_id)
            )
            return {"order_id": order_id, "scoring": scoring}
        except Exception as e:
            log.error(f"Failed to check order scoring: {e}")
            raise

    async def get_readonly_api_keys(self) -> Dict[str, Any]:
        """Get readonly API keys (py-clob-client get_readonly_api_keys)."""
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        try:
            keys = self._clob_client.get_readonly_api_keys()
            return {"keys": keys}
        except Exception as e:
            log.error(f"Failed to get readonly API keys: {e}")
            raise
    
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details (authenticated mode only).
        
        Args:
            order_id: Order ID
        
        Returns:
            Order details
        """
        if not self.is_authenticated:
            raise RuntimeError("Not authenticated.")
        
        try:
            order = self._clob_client.get_order(order_id)
            return order
        except Exception as e:
            log.error(f"Failed to get order: {e}")
            raise

    # Additional methods for authenticated trading can be added here (e.g., modify_order, get_position, etc.)
    def get_open_positions(self) -> Dict[str, Any]:
        """Get open positions (authenticated or readonly CLOB access).

        Returns:
            Dict mapping market_id -> list of open orders/positions.
        """
        try:
            # Prefer authenticated client if available
            if self.is_authenticated:
                orders = self._clob_client.get_orders()
            else:
                host = self.host or os.getenv("CLOB_API_URL", CLOB_API_URL)
                address = self.polygon_address or os.getenv("POLYGON_ADDRESS") or settings.polygon_address
                readonly_api_key = os.getenv("CLOB_READONLY_API_KEY")
                if not readonly_api_key or not address:
                    log.warning(
                        "Readonly CLOB access not configured (missing CLOB_READONLY_API_KEY or address)."
                    )
                    return {}

                response = httpx.get(
                    f"{host}{ORDERS}",
                    headers={
                        "POLY_READONLY_API_KEY": readonly_api_key,
                        "POLY_ADDRESS": address,
                        "Content-Type": "application/json",
                    },
                    params={"maker_address": address},
                    follow_redirects=True,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                orders = response.json()

            if isinstance(orders, dict) and "data" in orders and isinstance(orders["data"], list):
                orders = orders["data"]
            if not isinstance(orders, list):
                log.warning("Unexpected open orders response format: %s", type(orders).__name__)
                return {}

            positions_by_market: Dict[str, List[Dict[str, Any]]] = {}
            for order in orders:
                market_id = order.get("market") or order.get("market_id")
                if not market_id:
                    continue
                positions_by_market.setdefault(str(market_id), []).append(order)

            log.debug("Retrieved %d markets with open positions", len(positions_by_market))
            return positions_by_market
        except Exception as exc:
            log.error(f"Failed to get open positions: {exc}")
            return {}

    def get_open_position(self, market_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get open positions for a single market_id."""
        if not market_id:
            return None
        positions = self.get_open_positions()
        return positions.get(str(market_id))
