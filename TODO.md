# Trading System Roadmap — Updated Phase 4b-5

**Goal**: Complete Polymarket trading bot (crypto markets focus) with workforce integration, RSS flux signals, and comprehensive trading controls.

**Polymarket Execution Focus (Yes/No Tokens)**:
- Treat trades as **BUY YES** / **BUY NO** token operations (Polymarket CLOB binary markets).
- Keep LLM-facing identifiers **string-only** (e.g., "yes token", "no token", "contract address", "bet string").
- Store **byte/hex token IDs internally** in a mapping and retrieve at execution time.
- Use a **single simple trade ID** in LLM tool calls; all byte data and token IDs stay internal.
- Do not bias decisions: only use client-returned names/IDs and market data.
- **Trading client must follow `examples/` methodology** with `py_clob_client` (`ClobClient`, `OrderArgs`, `OrderType`).

---

## ✅ COMPLETED PHASES

- [x] **Phase 1**: Client Consolidation (23 tests passing)
- [x] **Phase 2**: Environment Setup (Python 3.11, uv, all dependencies)
- [x] **Phase 3**: Workforce Orchestration (29 tests passing)
- [x] **Phase 4a**: Polymarket Trading with Proper Schemas (59 tests passing)
  - ✅ PolymarketTradingToolkit (7 functions)
  - ✅ PolymarketTradeService (9 methods)
  - ✅ OpenAI/CAMEL-AI compatible schemas
  - ✅ Crypto/stock market focus
  - ✅ Built-in result tracking

---

## 🔄 IN PROGRESS

### Phase 4b: API Endpoints & Services (THIS PHASE)
### Phase 4c: RSS Flux & Workforce Management
### Phase 5: End-to-End Testing & Deployment

---

# 🎯 PHASE 4B: API ENDPOINTS & TRADING SERVICES

## Priority 1: Polymarket Market Data Toolkit

**File**: `core/camel_tools/polymarket_data_toolkit.py` (Update)

### Token ID Mapping & LLM-Safe Identifiers

- Maintain an **internal map**: `token_label -> token_id_bytes` (or hex string).
- `token_label` is **string-only** for LLMs: "yes token", "no token", "contract address", "bet string".
- LLM never sees byte data; it only references a **simple trade ID** when executing.
- When executing:
  1. Resolve `trade_id` -> `token_label`
  2. Resolve `token_label` -> `token_id_bytes`
  3. Place order with `token_id_bytes` via `py_clob_client`
- Do **not** transform or bias data; use only Polymarket client-returned IDs/names.

### Functions to Implement:

- [x] `scan_markets_by_category` / `search_high_conviction_markets`:
  - Search active Polymarket markets
  - Filter by category (crypto, stock, politics, sports)
  - Filter by liquidity minimum (default: $10k)
  - Return ranked by volume/liquidity
  - Response: List of markets with metadata

- [x] `get_market_data(market_id)`:
  - Get current market price + orderbook
  - Return: bid/ask spread, mid-price, orderbook depth (top 5)
  - Include: 24h volume, total liquidity, market age
  - Error handling: Invalid market ID, API failures

- [ ] `monitor_positions()` (Update to remove mock data):
  - Retrieve all current open positions
  - Return: Entry price, current price, quantity, P&L
  - Include: Market details for each position
  - Error handling: Auth failures, no positions

- [ ] `get_position_history(limit, asset_filter)`:
  - Get closed/historical positions
  - Filter by asset (optional)
  - Return: Entry, exit prices, profit/loss, duration

### Schema Design (OpenAI-Compatible):

```python
# Use simple types, Annotated descriptions
async def get_markets(
    query: Annotated[str, "Search query (e.g., 'bitcoin price')"],
    category: Annotated[str, "Category: crypto, stock, politics"] = "crypto",
    limit: Annotated[int, "Max results 1-50"] = 10,
    min_liquidity: Annotated[float, "Min liquidity in USD"] = 10000.0
) -> Dict[str, Any]:
    """Search Polymarket markets with filters."""
```

### Integration:
- [x] Added `PolymarketDataToolkit` to `core/camel_runtime/registries.py` (toolkit registry)
- [x] Integrate with PolymarketClient for data fetching

---

## Priority 2: Workforce Trading Tasks

**File**: `core/camel_runtime/polymarket_trading_tasks.py` (Scaffold added)

### LLM Tooling Rules
- Trade execution is exposed **only** as a FunctionTool with a **single simple `trade_id`**.
- LLM-visible fields are strings and floats; **no byte data** in tool inputs/outputs.
- Internal map resolves `trade_id -> token_label -> token_id_bytes` at execution time.

### Task 1: Market Scanning

**Input**:
- `category`: str (crypto, stock, politics)
- `confidence_threshold`: float (0.55-0.95)
- `max_markets`: int (default: 20)

**Output**:
- List of high-conviction market opportunities
- Format: `[{market_id, title, confidence, reason, expected_value}]`

**Process**:
1. Fetch markets in category from data toolkit
2. Call forecasting API for signal strength
3. Score by: confidence, liquidity, volume, market_age
4. Rank by expected value (EV = probability * payout)
5. Agent reasons about opportunities (why worth trading?)
6. Return top N markets

**Implementation**:
```python
async def market_scanning_task(
    category: str,
    confidence_threshold: float,
    max_markets: int = 20
) -> Dict[str, Any]:
    """Scan and identify high-conviction markets."""
    # 1. Get candidate markets
    # 2. Score each by forecasting + market data
    # 3. Filter by confidence threshold
    # 4. Rank by expected value
    # 5. Return top N
```

---

### Task 2: Position Sizing

**Input**:
- `markets`: List[Dict] (from market scanning)
- `wallet_balance`: float (total available USD)
- `risk_parameters`: Dict (max_exposure, kelly_fraction, etc.)

**Output**:
- Order plan: `[{market_id, outcome, token_label, quantity, price, expected_roi}]`
- `outcome`: "YES" | "NO"
- `token_label`: string-only identifier (e.g., "yes token", "no token", "contract address")
- Format includes: total_spend, total_exposure, risk_metrics

**Process**:
1. Get wallet distribution from forecasting API
2. For each market:
   - Calculate Kelly criterion position size
   - Apply risk adjustments (portfolio correlation, volatility)
   - Validate against max_exposure limit
   - Validate against wallet balance
3. Get current market prices + orderbooks
4. Determine order price (mid - spread*0.25 for buys)
5. Validate with DEX simulator (mock execution)
6. Return order plan

**Risk Calculations**:
```python
# Kelly Criterion: f* = (bp - q) / b
# Where: b = odds, p = win probability, q = lose probability

# Position size = wallet * kelly_fraction * adjustment_factor
# adjustment_factor = 1 / (1 + portfolio_correlation + volatility_adjusted)
```

**Implementation**:
```python
async def position_sizing_task(
    markets: List[Dict],
    wallet_balance: float,
    risk_parameters: Dict
) -> Dict[str, Any]:
    """Calculate optimal position sizes using Kelly criterion."""
    # 1. Get wallet distribution
    # 2. Calculate position sizes for each market
    # 3. Apply risk limits
    # 4. Validate total exposure
    # 5. Get market prices + predict slippage
    # 6. Return order plan
```

---

### Task 3: Order Placement

**Input**:
- `order_plan`: List[Dict] (from position sizing)
- `execution_mode`: str ('mock' or 'real')

**Output**:
- Execution results: `[{market_id, order_id, status, execution_price, slippage}]`
- Trade log with all metadata

**Process (Mock Mode - DEMO_MODE=TRUE)**:
1. Use DEX simulator to simulate execution
2. Calculate realistic slippage based on orderbook
3. Return simulated execution results
4. Log trade with full context

**Process (Real Mode)**:
1. Check POLYGON_PRIVATE_KEY is set
2. Use `PolymarketClient` with **py-clob-client** following `examples/`:
   - `ClobClient(host, key, chain_id, creds)`
   - `OrderArgs(price, size, side, token_id, expiration)`
   - `client.create_order(...)` + `client.post_order(..., OrderType.GTD)`
3. Place orders to CLOB using **YES/NO token IDs** from internal map
4. Track execution price vs target
5. Record in trade history
6. Error handling: rate limits, auth failures, order rejection

**Implementation**:
```python
async def order_placement_task(
    order_plan: List[Dict],
    execution_mode: str = 'mock'
) -> Dict[str, Any]:
    """Execute orders (mock or real based on mode)."""
    if execution_mode == 'mock':
        # Use DEX simulator
        results = await dex_simulator.execute_batch(order_plan)
    else:
        # Use PolymarketClient + py-clob-client (examples methodology)
        results = await polymarket_client.place_batch_orders(order_plan)
    
    # Log all trades
    await trade_service.log_batch_execution(results)
    return results
```

---

### Task 4: Consensus Copy Risk Analysis

**File**: `core/camel_runtime/polymarket_trading_tasks.py` (Scaffold added)

**Input**:
- `consensus_probability`: float (0-1, e.g., 0.60)
- `market_implied_probability`: float (0-1)
- `fees_pct`: float (0-1)
- `spread_pct`: float (0-1)
- `latency_penalty`: float (0-1)
- `historical_edge`: Optional[float] (0-1)

**Output**:
- `copy_trade_edge`: float
- `estimated_win_rate`: float
- `decision`: "follow" | "avoid" | "needs_more_data"

**Purpose**:
Estimate whether copying crowd consensus is likely profitable before final trade decision.

---

## Priority 3: REST API Endpoints (Crypto-only focus)

**File**: `api/routers/polymarket/` routers (Existing; currently stubbed)

### Process Config & Logging
- [x] Add `/api/polymarket/config` (GET/POST) for workflow weights/limits/flux selection
- [x] Add `/api/polymarket/logs` (GET/POST/DELETE) for process logging

### Endpoints to Implement:

#### 1. Search Markets
```
GET /api/polymarket/markets/search?q=bitcoin&category=crypto&limit=10

Response:
{
    "success": true,
    "query": "bitcoin",
    "category": "crypto",
    "found": 5,
    "markets": [
        {
            "id": "market_1",
            "title": "BTC Price > $50k",
            "category": "crypto",
            "liquidity": 150000,
            "volume_24h": 75000,
            "mid_price": 0.75,
            "bid": 0.74,
            "ask": 0.76
        }
    ]
}
```

- [x] Implement search handler
- [ ] Connect to `get_markets()` from data toolkit
- [ ] Add pagination support
- [ ] Add error handling

---

#### 2. Get Market Details
```
GET /api/polymarket/markets/{market_id}

Response:
{
    "success": true,
    "market_id": "market_1",
    "title": "BTC Price > $50k",
    "mid_price": 0.75,
    "bid": 0.74,
    "ask": 0.76,
    "spread": 0.02,
    "liquidity": 150000,
    "volume_24h": 75000,
    "orderbook": {
        "bids": [{"price": 0.74, "quantity": 100}, ...],
        "asks": [{"price": 0.76, "quantity": 150}, ...]
    }
}
```

- [x] Implement market details handler
- [x] Connect to `get_market_data()` from toolkit
- [x] Include orderbook depth
- [x] Error handling for invalid market ID

---

#### 3. Get Positions
```
GET /api/polymarket/positions

Response:
{
    "success": true,
    "positions": [
        {
            "position_id": "pos_1",
            "market_id": "market_1",
            "market_title": "BTC Price > $50k",
            "outcome": "YES",
            "entry_price": 0.70,
            "current_price": 0.75,
            "quantity": 100,
            "entry_value": 7000,
            "current_value": 7500,
            "unrealized_pnl": 500,
            "unrealized_pnl_pct": 7.14,
            "entry_time": "2024-01-03T10:00:00Z"
        }
    ],
    "summary": {
        "total_open_value": 7500,
        "total_unrealized_pnl": 500,
        "total_positions": 1
    }
}
```

- [x] Implement positions handler
- [x] Connect to `get_positions()` from toolkit
- [x] Calculate P&L in real-time
- [x] Error handling for auth issues

---

#### 4. Propose Trade
```
POST /api/polymarket/trades/propose

Request:
{
    "market_id": "market_1",
    "outcome": "YES",
    "confidence": 0.75,
    "reasoning": "Bullish sentiment from RSS signals"
}

Response:
{
    "success": true,
    "proposal_id": "prop_1",
    "market_id": "market_1",
    "market_title": "BTC Price > $50k",
    "outcome": "YES",
    "token_label": "yes token",
    "recommended_quantity": 15,
    "recommended_price": 0.73,
    "estimated_value": 1095,
    "confidence": 0.75,
    "expected_roi": 0.08,
    "reasoning": "...",
    "risks": ["High spread", "Low volume"],
    "status": "ready_to_execute"
}
```

- [x] Implement propose handler
- [ ] Run market scanning task
- [ ] Run position sizing task
- [x] Get current market data
- [x] Return proposal with reasoning
- [x] Store proposal for later execution

---

#### 5. Execute Trade
```
POST /api/polymarket/trades/execute

Request:
{
    "proposal_id": "prop_1"  // or "market_id", "outcome", "quantity", "price"
}

Response:
{
    "success": true,
    "trade_id": "trade_123",
    "market_id": "market_1",
    "outcome": "YES",
    "quantity": 15,
    "target_price": 0.73,
    "execution_price": 0.732,
    "slippage": 0.002,
    "slippage_pct": 0.27,
    "execution_time": "2024-01-03T10:00:05Z",
    "order_id": "order_789",
    "status": "filled",
    "execution_mode": "mock"
}
```

- [x] Implement execute handler
- [ ] Run order placement task
- [ ] Track execution vs. target
- [ ] Log trade with all metadata
- [ ] Check trading limits before execution
- [x] Return execution result

---

#### 6. List Trades
```
GET /api/polymarket/trades?status=filled&asset=BTC&limit=20&offset=0

Response:
{
    "success": true,
    "trades": [
        {
            "trade_id": "trade_123",
            "market_id": "market_1",
            "asset": "BTC",
            "outcome": "YES",
            "quantity": 15,
            "entry_price": 0.732,
            "status": "filled",
            "timestamp": "2024-01-03T10:00:05Z",
            "rss_signal": "bullish_sentiment",
            "agent_confidence": 0.75
        }
    ],
    "total": 50,
    "limit": 20,
    "offset": 0
}
```

- [x] Implement list handler
- [x] Support filtering: status, asset, date_range
- [x] Support pagination (limit, offset)
- [x] Connect to trade service
- [x] Error handling

---

#### 7. Get Trade Details
```
GET /api/polymarket/trades/{trade_id}

Response: (Full trade record with execution details)
```

- [x] Implement trade details handler
- [ ] Return full execution history
- [ ] Include P&L if closed

---

#### 8. Get Trading Summary
```
GET /api/polymarket/summary?period=day|week|month

Response:
{
    "success": true,
    "period": "day",
    "date": "2024-01-03",
    "trades": {
        "total": 10,
        "successful": 9,
        "failed": 1,
        "pending": 0,
        "success_rate": 0.90
    },
    "pnl": {
        "realized": 500,
        "unrealized": 250,
        "total": 750,
        "roi_pct": 3.5
    },
    "limits": {
        "max_trades_per_day": 10,
        "trades_today": 9,
        "max_exposure_usd": 5000,
        "current_exposure_usd": 4200
    },
    "assets": {
        "BTC": {"trades": 4, "pnl": 200},
        "ETH": {"trades": 3, "pnl": 150},
        "SOL": {"trades": 2, "pnl": 150}
    },
    "signals": {
        "rss_signals_used": 8,
        "rss_accuracy": 0.875,
        "high_confidence_trades": 7
    }
}
```

- [x] Implement summary handler
- [ ] Calculate all metrics
- [ ] Show trading limits status
- [ ] Include RSS signal performance

---

### Router Integration:
- [x] Register in `api/main_polymarket.py`
- [ ] Add authentication middleware (if needed)
- [ ] Add error handling middleware
- [ ] Add logging middleware

---

# 🔗 PHASE 4C: RSS FLUX & WORKFORCE MANAGEMENT

## Priority 1: RSS Feed Integration Service

**File**: `core/services/rss_flux_service.py` (Create)

### Features to Implement:

#### 1. Feed Parser
- [ ] `parse_feed(feed_url)`: Parse RSS/Atom feeds
  - Extract title, description, timestamp
  - Handle feed errors gracefully
  - Cache parsed content

- [ ] `extract_signals(article_text)`: Extract trading signals
  - Identify sentiment (bullish, bearish, neutral)
  - Extract asset mentions (BTC, ETH, AAPL, etc.)
  - Extract confidence/certainty indicators
  - Map to Polymarket market outcomes

- [ ] `score_signal(signal_dict)`: Score signal reliability
  - Base score from confidence indicators (0.0-1.0)
  - Feed reliability multiplier (weighted by past accuracy)
  - Asset relevance factor
  - Time decay (older signals less relevant)

#### 2. Signal Management
- [ ] `add_signal(signal, source)`: Store new signal
  - Deduplication (combine similar signals from different sources)
  - Time-series tracking (for accuracy measurement)
  - Attribution (source feed, article, timestamp)

- [ ] `get_latest_signals(asset, limit, min_confidence)`: Fetch signals
  - Filter by asset (e.g., "BTC", "ETH", "AAPL")
  - Filter by confidence threshold
  - Return ranked by recency + confidence
  - Apply time decay

- [ ] `get_signal_consensus(asset)`: Get consensus view
  - Aggregate all signals for an asset
  - Calculate weighted consensus score
  - Show divergence (disagreement level)

#### 3. Signal Tracking & Validation
- [ ] `record_trade_from_signal(signal_id, trade_id)`: Link signal to trade
  - Track which signals led to which trades
  - Enable post-trade accuracy measurement

- [ ] `update_signal_accuracy(signal_id, trade_outcome)`: Update accuracy
  - Mark signal as correct/incorrect after trade closes
  - Update feed reliability weights
  - Track false positives/negatives

### Configuration (in `.env`):

```bash
# RSS Feed Configuration
RSS_FEEDS="https://coindesk.com/feed|https://cointelegraph.com/feed|https://example.com/feed"
RSS_UPDATE_INTERVAL=3600              # seconds (1 hour)
RSS_SIGNAL_RETENTION=604800            # seconds (7 days)
RSS_MIN_CONFIDENCE=0.6                 # Skip signals below this

# Feed Reliability (initial weights)
RSS_FEED_WEIGHTS="coindesk:1.0|cointelegraph:0.9|example:0.5"

# Signal Extraction
RSS_SENTIMENT_MODEL=default            # or custom model name
RSS_ASSET_MAPPING_FILE=config/asset_mappings.json
```

### Implementation Example:

```python
class RSSFluxService:
    """RSS feed parsing and signal extraction for trading."""
    
    async def initialize(self):
        """Load feeds and start update cycle."""
        self.feeds = self._load_feeds_from_config()
        self.signals = {}  # {asset: [signals]}
        self.feed_reliability = {}
        
        # Start background update task
        asyncio.create_task(self._update_loop())
    
    async def _update_loop(self):
        """Periodically fetch and parse feeds."""
        while True:
            for feed_url in self.feeds:
                try:
                    articles = await self._fetch_feed(feed_url)
                    for article in articles:
                        signal = await self._extract_signal(article)
                        if signal and signal['confidence'] >= self.min_confidence:
                            await self.add_signal(signal, feed_url)
                except Exception as e:
                    logger.error(f"Feed error: {feed_url}: {e}")
            
            await asyncio.sleep(self.update_interval)
    
    async def add_signal(self, signal, source):
        """Add signal with deduplication."""
        # Check for duplicates
        # Update feed reliability
        # Store signal
        # Emit event to agents
        pass
    
    def get_latest_signals(self, asset, limit=10, min_confidence=0.6):
        """Get latest signals for asset."""
        # Filter by confidence
        # Apply time decay
        # Return ranked by score
        pass
```

---

## Priority 2: Workforce Configuration & Management

**File**: `core/services/workforce_config_service.py` (Already implemented)

### Trading Controls:

```python
class TradingControls:
    """Configure trading limits and filters."""
    
    # Trade Limits
    max_trades_per_day: int = 10          # Max trades per calendar day
    max_amount_per_trade: float = 500     # Max USD per trade
    max_exposure_total: float = 5000      # Max total USD exposure
    max_spread_tolerance: float = 0.05    # Max bid-ask spread (5%)
    
    # Market Filters
    min_liquidity: float = 10000           # Min market liquidity
    min_volume_24h: float = 5000           # Min 24h volume
    min_market_age_hours: int = 24         # Don't trade brand-new markets
    
    # Probability Filters
    min_probability: float = 0.55          # Skip if below 55% probability
    max_probability: float = 0.95          # Skip if above 95% (unlikely profit)
    
    # Asset Whitelist/Blacklist
    asset_whitelist: List[str] = [        # Only trade these
        "BTC", "ETH", "SOL", "AAPL", "MSFT", "GOOGL"
    ]
    asset_blacklist: List[str] = []       # Never trade these
    
    # Category Filters
    category_whitelist: List[str] = ["crypto", "stock"]
    category_blacklist: List[str] = ["politics"]
```

- [x] Implement `TradingControls` dataclass
- [ ] Implement `load_from_config()`: Load from `.env` and YAML (env-only exists; YAML optional)
- [x] Implement `validate()`: Check configuration consistency
- [x] Implement `check_trade(market, quantity, price)`: Pre-flight check

### Filtering Implementation:

```python
async def should_allow_trade(self, market_data, proposed_quantity, proposed_price):
    """Check if trade passes all filters."""
    
    # 1. Check trade count limit
    trades_today = await self.get_trades_today()
    if len(trades_today) >= self.max_trades_per_day:
        return False, "Max trades per day reached"
    
    # 2. Check amount limit
    trade_value = proposed_quantity * proposed_price
    if trade_value > self.max_amount_per_trade:
        return False, "Trade amount exceeds max_amount_per_trade"
    
    # 3. Check exposure limit
    current_exposure = await self.get_current_exposure()
    if current_exposure + trade_value > self.max_exposure_total:
        return False, "Total exposure would exceed max_exposure_total"
    
    # 4. Check market filters
    if market_data['liquidity'] < self.min_liquidity:
        return False, "Market liquidity below minimum"
    
    if market_data['volume_24h'] < self.min_volume_24h:
        return False, "Market volume too low"
    
    # 5. Check spread
    spread = market_data['ask'] - market_data['bid']
    if spread > self.max_spread_tolerance:
        return False, f"Spread {spread:.4f} exceeds max {self.max_spread_tolerance}"
    
    # 6. Check asset whitelist
    if self.asset_whitelist and market_data['asset'] not in self.asset_whitelist:
        return False, f"Asset {market_data['asset']} not in whitelist"
    
    # 7. Check category
    if market_data['category'] not in self.category_whitelist:
        return False, f"Category {market_data['category']} not whitelisted"
    
    # 8. Check probability
    if market_data['probability'] < self.min_probability:
        return False, f"Probability {market_data['probability']:.2%} below minimum"
    
    return True, "All checks passed"
```

---

### Workforce Trigger Configuration:

```python
class WorkforceTriggerConfig:
    """Configure how and when to trigger trading workflow."""
    
    # Trigger Types
    trigger_type: str = "hybrid"           # "interval", "signal", "market", "hybrid"
    
    # Interval-based Trigger
    interval_hours: int = 4                # Run workflow every N hours
    
    # Signal-based Trigger
    signal_threshold_confidence: float = 0.75    # Trigger if signal above 0.75
    min_signals_required: int = 2               # Require at least N signals
    
    # Market-based Trigger
    new_markets_threshold: int = 5         # Trigger if N new markets appear
    
    # Hybrid: Trigger if ANY condition met (or use AND for ALL)
    hybrid_mode: str = "OR"                # "OR" = any trigger, "AND" = all triggers
```

- [ ] Implement trigger logic
- [ ] Integrate with scheduler (APScheduler or similar)
- [ ] Log all trigger events

#### Example Trigger Check:

```python
async def should_trigger_workflow(self):
    """Check if workflow should run based on configured triggers."""
    
    triggers_met = []
    
    # Interval-based
    last_run = await self.get_last_workflow_run()
    if datetime.utcnow() - last_run > timedelta(hours=self.interval_hours):
        triggers_met.append("interval")
    
    # Signal-based
    recent_signals = await self.rss_service.get_latest_signals(min_confidence=0.75)
    if len(recent_signals) >= self.min_signals_required:
        triggers_met.append("signals")
    
    # Market-based
    new_markets = await self.market_data_toolkit.get_new_markets(limit=1000)
    if len(new_markets) >= self.new_markets_threshold:
        triggers_met.append("new_markets")
    
    # Decide based on hybrid mode
    if self.hybrid_mode == "OR":
        return len(triggers_met) > 0
    else:  # AND
        return len(triggers_met) == len(self.trigger_types)
```

---

### Agent Weight Configuration:

```python
class AgentWeightConfig:
    """Configure agent influence on trading decisions."""
    
    # How much agent recommendations affect decisions
    agent_weight: float = 0.60             # 60% weight from agent reasoning
    signal_weight: float = 0.30            # 30% weight from RSS signals
    market_data_weight: float = 0.10       # 10% weight from raw market data
    
    # Strategy per agent
    agent_strategies: Dict[str, str] = {
        "market_scanner": "aggressive",     # Scan more markets
        "risk_manager": "conservative",     # Smaller positions
        "trend_follower": "momentum"        # Follow market trends
    }
    
    # Per-agent risk limits
    per_agent_max_exposure: float = 2000   # Each agent controls max $2k
    per_agent_max_trades: int = 5          # Each agent max 5 trades/day
```

- [ ] Use weights in trade proposal scoring
- [ ] Combine agent reasoning with signals + market data
- [ ] Implement final decision logic in `execute_trading_cycle()`

#### Example Decision Combining Weights:

```python
def calculate_trade_score(self, agent_score, signal_score, market_data_score):
    """Combine scores using configured weights."""
    
    weighted_score = (
        agent_score * self.agent_weight +
        signal_score * self.signal_weight +
        market_data_score * self.market_data_weight
    )
    
    # Normalize to 0-1
    return max(0, min(1, weighted_score))
```

---

## Priority 3: Workforce Manager Service

**File**: `core/camel_runtime/polymarket_workforce_manager.py` (Create/Update)

### Main Functions:

```python
class PolymarketWorkforceManager:
    """Manage workforce trading configuration and execution."""
    
    async def initialize(self):
        """Load config, initialize services, start scheduler."""
        self.trading_controls = await TradingControls.load_from_config()
        self.trigger_config = await WorkforceTriggerConfig.load_from_config()
        self.agent_weights = await AgentWeightConfig.load_from_config()
        
        self.rss_service = RSSFluxService()
        await self.rss_service.initialize()
        
        self.trade_service = PolymarketTradeService()
        await self.trade_service.initialize()
        
        # Start scheduler
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
```

#### 1. Run Full Trading Cycle

```python
async def run_trading_cycle(self):
    """Execute complete workflow: scan → size → execute → track."""
    
    cycle_id = str(uuid.uuid4())
    log.info(f"Starting trading cycle {cycle_id}")
    
    try:
        # 1. Market Scanning
        markets = await self.market_scanning_task(
            category="crypto",
            confidence_threshold=self.agent_weights.signal_weight
        )
        log.info(f"Found {len(markets)} candidate markets")
        
        # 2. Position Sizing
        order_plan = await self.position_sizing_task(
            markets=markets,
            wallet_balance=await self.get_available_balance(),
            risk_parameters=self.trading_controls
        )
        log.info(f"Generated {len(order_plan)} orders")
        
        # 3. Filter Orders by Trading Controls
        filtered_orders = []
        for order in order_plan:
            allowed, reason = await self.trading_controls.should_allow_trade(
                market_data=order,
                quantity=order['quantity'],
                price=order['price']
            )
            if allowed:
                filtered_orders.append(order)
            else:
                log.warning(f"Order rejected: {reason}")
        
        log.info(f"Executing {len(filtered_orders)} orders after filtering")
        
        # 4. Order Placement
        execution_mode = 'real' if self.trading_controls.real_mode else 'mock'
        results = await self.order_placement_task(
            order_plan=filtered_orders,
            execution_mode=execution_mode
        )
        
        # 5. Trade Logging & Signal Attribution
        for result in results:
            await self.log_trade_execution(
                trade_result=result,
                cycle_id=cycle_id,
                signals_used=markets[result['market_idx']].get('signals', [])
            )
        
        # 6. Summary & Notifications
        summary = await self.get_cycle_summary(cycle_id)
        log.info(f"Cycle {cycle_id} complete: {summary}")
        
        return summary
        
    except Exception as e:
        log.error(f"Cycle {cycle_id} failed: {e}")
        raise
```

#### 2. Check & Enforce Trading Limits

```python
async def check_trading_limits(self):
    """Verify all trading limits before executing cycle."""
    
    checks = {
        "trades_today": {
            "current": len(await self.get_trades_today()),
            "limit": self.trading_controls.max_trades_per_day,
            "status": "OK"
        },
        "current_exposure": {
            "current": await self.get_current_exposure(),
            "limit": self.trading_controls.max_exposure_total,
            "status": "OK"
        },
        "rss_signals": {
            "active": len(await self.rss_service.get_latest_signals()),
            "min_confidence": self.trading_controls.min_confidence,
            "status": "OK"
        }
    }
    
    # Check each limit
    for check_name, check_data in checks.items():
        if 'limit' in check_data:
            if check_data['current'] >= check_data['limit']:
                check_data['status'] = "LIMIT_REACHED"
    
    return checks
```

#### 3. Log Trade Execution

```python
async def log_trade_execution(self, trade_result, cycle_id, signals_used):
    """Log trade with full context for later analysis."""
    
    trade_log = {
        "trade_id": trade_result['trade_id'],
        "cycle_id": cycle_id,
        "timestamp": datetime.utcnow().isoformat(),
        "market_id": trade_result['market_id'],
        "outcome": trade_result['outcome'],
        "quantity": trade_result['quantity'],
        "target_price": trade_result['target_price'],
        "execution_price": trade_result['execution_price'],
        "slippage": trade_result['slippage'],
        "status": trade_result['status'],
        "execution_mode": trade_result.get('execution_mode', 'mock'),
        
        # Signal attribution
        "signals_used": signals_used,
        "signal_confidence": max([s.get('confidence', 0) for s in signals_used]) if signals_used else 0,
        
        # Agent attribution
        "agent_name": trade_result.get('agent_name'),
        "agent_weight": self.agent_weights.agent_weight,
        
        # Risk metrics
        "portfolio_impact": trade_result['quantity'] * trade_result['execution_price'],
        "current_exposure_after": await self.get_current_exposure()
    }
    
    # Store in database/log file
    await self.trade_logger.log_trade(trade_log)
    
    # Update signal accuracy tracking
    if signals_used:
        for signal in signals_used:
            await self.rss_service.record_trade_from_signal(
                signal_id=signal['id'],
                trade_id=trade_result['trade_id']
            )
```

#### 4. Get Trading Summary

```python
async def get_daily_summary(self, date: Optional[str] = None):
    """Get daily trading report."""
    
    date = date or datetime.utcnow().date().isoformat()
    trades = await self.trade_service.list_trades(
        filters={"date": date}
    )
    
    summary = {
        "date": date,
        "trades": {
            "total": len(trades),
            "successful": sum(1 for t in trades if t['status'] == 'filled'),
            "failed": sum(1 for t in trades if t['status'] == 'failed'),
            "pending": sum(1 for t in trades if t['status'] == 'pending')
        },
        "pnl": {
            "realized": sum(t.get('pnl', 0) for t in trades if t.get('closed')),
            "unrealized": sum(t.get('unrealized_pnl', 0) for t in trades if not t.get('closed')),
        },
        "limits": {
            "max_trades": self.trading_controls.max_trades_per_day,
            "trades_used": len(trades),
            "max_exposure": self.trading_controls.max_exposure_total,
            "current_exposure": await self.get_current_exposure()
        },
        "signals": {
            "rss_signals_used": sum(1 for t in trades if t.get('signals_used')),
            "avg_signal_confidence": np.mean([t.get('signal_confidence', 0) for t in trades if t.get('signals_used')]),
            "signal_accuracy": await self.rss_service.get_daily_accuracy(date)
        },
        "assets": self._group_by_asset(trades)
    }
    
    return summary
```

---

## Priority 4: Enhanced Logging & Monitoring

**File**: `core/services/trading_metrics_service.py` (Create)

- [ ] `log_trade()`: Record every trade with full context
- [ ] `log_cycle()`: Record each trading cycle execution
- [ ] `log_signal()`: Record RSS signals used
- [ ] `update_signal_accuracy()`: Post-trade signal review
- [ ] `get_agent_performance()`: Per-agent performance metrics
- [ ] `get_daily_report()`: Daily trading report

### Metrics to Track:

```python
class TradingMetrics:
    """Track trading performance metrics."""
    
    # Per-trade metrics
    total_trades: int
    successful_trades: int
    failed_trades: int
    success_rate: float
    avg_slippage: float
    avg_roi: float
    
    # Per-signal metrics
    rss_signals_used: int
    signal_accuracy: float  # % correct after trade closes
    best_performing_feed: str
    
    # Per-agent metrics
    agent_trades: Dict[str, int]  # {agent_name: trade_count}
    agent_success_rate: Dict[str, float]  # {agent_name: success_rate}
    agent_roi: Dict[str, float]  # {agent_name: avg_roi}
    
    # Portfolio metrics
    daily_pnl: float
    cumulative_pnl: float
    max_exposure_used: float
    total_trades_today: int
```

---

# 🧪 PHASE 5: TESTING & VALIDATION

**Test Runner Notes**
- Use `bash -lc "UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q tests/test_api_polymarket_config_logs_trades.py --ignore examples/polymarket-mcp-server/tests"` for non-workforce tests.
- Latest run: 4 passed, 1 warning (Pydantic dict deprecated) → warning fixed by using `model_dump`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q -k "not workforce"` now passes (42 passed, 118 skipped, 48 deselected) after pruning non-Polymarket tests via `tests/conftest.py`.
- `uv run pytest -q -k "not workforce"` still picks legacy/agentic tests and can time out; prefer targeted tests until legacy suite is pruned.
- Legacy tests skipped for Polymarket-only scope: `test_api_main`, `test_full_agentic_cycle`, `test_wallet_endpoint`, `test_redis_wallet_distribution`, `test_verify_agentic_outputs`, `test_portfolio_agentic`, `test_neo4j_memory_toolkit`.

## Priority 1: Workflow Integration Tests

**File**: `tests/test_trading_workflow_full.py` (Create)

- [ ] `test_full_workflow_mock`:
  - Market scan → Position size → Mock order execution
  - Verify no real orders placed (DEMO_MODE=TRUE)
  - Check all limits enforced

- [ ] `test_rss_signal_integration`:
  - Create RSS signals
  - Run market scanning with signals
  - Verify signals influence market selection

- [ ] `test_trading_limits_enforced`:
  - Test max_trades_per_day limit
  - Test max_amount_per_trade limit
  - Test max_exposure_total limit
  - Test spread tolerance

- [ ] `test_filter_rules`:
  - Test asset whitelist/blacklist
  - Test category filters
  - Test liquidity minimum
  - Test probability filters

---

## Priority 2: Workforce Configuration Tests

**File**: `tests/test_workforce_config.py` (Create)

- [ ] `test_load_config()`: Load from .env
- [ ] `test_validate_config()`: Check consistency
- [ ] `test_should_allow_trade()`: Trade approval logic
- [ ] `test_trigger_conditions()`: Trigger logic
- [ ] `test_agent_weight_calculation()`: Weight combination

---

## Priority 3: RSS Flux Tests

**File**: `tests/test_rss_flux_service.py` (Create)

- [ ] `test_parse_rss_feed()`: Parse sample RSS
- [ ] `test_extract_signals()`: Extract sentiment + assets
- [ ] `test_score_signal()`: Signal scoring
- [ ] `test_signal_deduplication()`: Combine duplicates
- [ ] `test_signal_accuracy_tracking()`: Track after trade

---

## Priority 4: Performance Tests

**File**: `tests/test_performance.py` (Create)

- [ ] `test_market_scanning_speed()`: Should complete in < 5s
- [ ] `test_position_sizing_speed()`: Should complete in < 3s
- [ ] `test_rss_parsing_speed()`: Should parse 100 articles < 10s
- [ ] `test_end_to_end_latency()`: Full cycle < 30s

---

# 📋 CONFIGURATION CHECKLIST

### Files to Create/Update:

```
✅ Production Code:
  [x] core/camel_tools/polymarket_data_toolkit.py
  [x] core/camel_runtime/polymarket_trading_tasks.py (scaffold added)
  [x] api/routers/polymarket/ (implemented real handlers)
  
  [ ] core/services/rss_flux_service.py
  [x] core/services/workforce_config_service.py
  [ ] core/camel_runtime/polymarket_workforce_manager.py
  [ ] core/services/trading_metrics_service.py

📋 Test Code:
  [ ] tests/test_polymarket_data_toolkit.py
  [ ] tests/test_trading_workflow_full.py
  [ ] tests/test_workforce_config.py
  [ ] tests/test_rss_flux_service.py
  [ ] tests/test_performance.py

🔧 Configuration Files:
  [ ] .env (add RSS_FEEDS, trading limits)
  [ ] config/fusion_config.yaml (add trading config)
  [ ] config/asset_mappings.json (RSS → Polymarket mapping)
  [x] api/main_polymarket.py (register new router)
```

### .env Variables to Add:

```bash
# RSS Feed Configuration
RSS_FEEDS="https://coindesk.com/feed|https://cointelegraph.com/feed"
RSS_UPDATE_INTERVAL=3600
RSS_SIGNAL_RETENTION=604800
RSS_MIN_CONFIDENCE=0.6

# Trading Limits
TRADING_MAX_TRADES_PER_DAY=10
TRADING_MAX_AMOUNT_PER_TRADE=500
TRADING_MAX_EXPOSURE_TOTAL=5000
TRADING_MIN_PROBABILITY=0.55

# Workforce Trigger
WORKFORCE_TRIGGER_TYPE=hybrid
WORKFORCE_TRIGGER_INTERVAL_HOURS=4
WORKFORCE_MIN_SIGNALS=2

# Agent Weights
AGENT_WEIGHT=0.60
SIGNAL_WEIGHT=0.30
MARKET_DATA_WEIGHT=0.10

# Execution Mode
EXECUTION_MODE=mock  # mock or real
```

---

# 🎯 SUCCESS CRITERIA

✅ **Phase 4b Complete When**:
- [ ] All 3 priorities (Data toolkit, Tasks, API endpoints) implemented
- [ ] 8+ API endpoints working (search, details, positions, propose, execute, list, summary)
- [ ] All endpoints have tests and pass

✅ **Phase 4c Complete When**:
- [ ] RSS flux service parsing feeds and extracting signals
- [ ] Workforce config service enforcing all trading limits
- [ ] Workforce manager orchestrating full trading cycle
- [ ] Metrics service tracking performance
- [ ] All 4 test suites passing

✅ **Phase 5 Complete When**:
- [ ] Full end-to-end workflow tested
- [ ] DEMO_MODE prevents real orders
- [ ] Trading limits enforced in tests
- [ ] Performance acceptable (< 30s per cycle)
- [ ] All tests passing (100+ total tests)

---

# 🚀 DEPLOYMENT STEPS

1. **Complete Phase 4b**:
   ```bash
   pytest tests/test_polymarket_data_toolkit.py -v
   pytest tests/test_trading_workflow_full.py -v
   ```

2. **Complete Phase 4c**:
   ```bash
   pytest tests/test_rss_flux_service.py -v
   pytest tests/test_workforce_config.py -v
   ```

3. **Full Integration**:
   ```bash
   pytest tests/ -v --tb=short
   # Target: 150+ tests passing
   ```

4. **Start Server**:
   ```bash
   python api/main_polymarket.py --enable-trading --demo-mode=true
   ```

5. **Docker (Polymarket-only)**:
   ```bash
   docker compose up --build
   ```

5. **Monitor**:
   ```bash
   # Check trading cycle logs
   tail -f logs/trading_*.log
   
   # Check trading summary
   curl http://localhost:8000/api/polymarket/summary?period=day
   ```

---

**Last Updated**: February 3, 2026
**Status**: Phase 4b-5 Planning Complete - Ready for Implementation

---

# 🚀 ACTION PLAN: PHASE 4B IMPLEMENTATION CHECKLIST

This is a step-by-step guide for a developer to implement Phase 4b.

### Step 1: Implement Data Toolkit & Tests
- [x] **Update File**: `core/camel_tools/polymarket_data_toolkit.py` (Exists)
- [ ] **Implement Functions**:
  - [x] `scan_markets_by_category` & `search_high_conviction_markets`
  - [x] `get_market_data(market_id)`
  - [ ] `monitor_positions()` (Real implementation needed)
  - [ ] `get_position_history(limit, asset_filter)`
- [ ] **Write Tests**: Create `tests/test_polymarket_data_toolkit.py` and write unit tests for each function, mocking the `PolymarketClient` calls.
- [x] **Integrate**: Add the new toolkit to the agent toolkit registry in `core/camel_runtime/registries.py`.

### Step 2: Implement Core Trading Tasks
- [x] **Create File**: `core/camel_runtime/polymarket_trading_tasks.py` (scaffold added)
- [ ] **Implement Tasks**:
  - [ ] `market_scanning_task(...)`: Implement the logic to fetch, score, and rank markets.
  - [ ] `position_sizing_task(...)`: Implement Kelly criterion and risk adjustment logic.
  - [ ] `order_placement_task(...)`: Implement the `mock` execution path first. The `real` mode can be stubbed out until Phase 5.

### Step 3: Build the REST API Endpoints
- [x] **Update Files**: `api/routers/polymarket/*.py` (replace stubs with real handlers)
- [x] **Implement Read-Only Endpoints**: Start with endpoints that don't change state.
  - [x] `GET /api/polymarket/markets/search`
  - [x] `GET /api/polymarket/markets/{market_id}`
  - [x] `GET /api/polymarket/positions`
  - [x] `GET /api/polymarket/trades`
  - [x] `GET /api/polymarket/trades/{trade_id}`
  - [x] `GET /api/polymarket/summary`
- [x] **Implement State-Changing Endpoints**:
  - [x] `POST /api/polymarket/trades/propose`: This should call the `market_scanning_task` and `position_sizing_task`. (stubbed with direct sizing; task integration pending)
  - [x] `POST /api/polymarket/trades/execute`: This should call the `order_placement_task`. (stubbed with trade service; task integration pending)
- [x] **Register Router**: Add the new router to your main FastAPI app in `api/main_polymarket.py`.

### Step 4: Write API & Integration Tests
- [x] **Create File**: `tests/test_api_polymarket_config_logs_trades.py` (minimal config/log/proposal/execute tests).
- [ ] **Test Each Endpoint**: Write tests to confirm status codes, response schemas, and error handling for all 8 endpoints.
- [x] **Test Workflow**: Create an integration test that calls `POST /propose` and then uses its response to call `POST /execute` to verify the end-to-end flow in `mock` mode.

### Crypto-only Scope Notes
- [ ] Enforce crypto-only categories in market search/trending/analysis endpoints.
- [ ] Ensure proposal/execution logic validates crypto market category.
- [ ] Wallet distribution handled externally; API returns “not_supported”.
