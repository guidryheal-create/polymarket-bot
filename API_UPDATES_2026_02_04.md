## Agentic Polymarket Trading System - Architecture & API Updates (Feb 4, 2026)

### Executive Summary

**Status**: Workforce + API integration complete with embedding error fixes, authentication, and simplified betting workflow.

**Key Updates**:
1. ✅ **Embedding Error Fixed**: Added detailed logging and graceful fallback for `_collect_shared_memory` empty message errors
2. ✅ **API Authentication**: Added Bearer token authentication to all endpoints
3. ✅ **Bet Visibility**: New `/api/polymarket/bets/*` endpoints for real-time bet tracking
4. ✅ **Simplified Workflow**: Created `SimplifiedBettingWorkflow` focused on market analysis → bet placement
5. ✅ **CAMEL Compatibility**: Added `WorkforceMode` and `WorkforceSnapshot` fallbacks for version flexibility

---

## Problem: Embedding Error in Shared Memory

### Error Log
```
2026-02-04 12:30:02 | WARNING  | camel.societies.workforce.workforce:_collect_shared_memory:1136 
- Error collecting shared memory: Invalid text input for embedding:
```

### Root Cause
The CAMEL Workforce's `_collect_shared_memory()` method was trying to embed empty or whitespace-only messages. When the embedding provider (Ollama) received these empty strings, it raised a ValueError about shape mismatch.

### Solution
**File**: `core/camel_runtime/societies.py`

Added comprehensive error handling:
```python
# Filter out empty messages BEFORE embedding
for key in ['coordinator', 'task_agent', 'workers']:
    original_count = len(shared_memory[key])
    valid_msgs = [msg for msg in shared_memory[key] if msg and has_content(msg)]
    shared_memory[key] = valid_msgs
    
    if original_count != filtered_count:
        logger.debug(f"Filtered {original_count - filtered_count} empty messages from {key}")

# Catch embedding shape errors gracefully
except ValueError as ve:
    if "shape" in str(ve).lower() or "dimension" in str(ve).lower():
        logger.warning(f"Embedding shape error (empty text): {ve}")
        return {'coordinator': [], 'task_agent': [], 'workers': []}
```

**Result**: Empty messages are now filtered before embedding, preventing shape errors. If an error still occurs, the system returns empty memory instead of crashing.

---

## New Feature: API Authentication & Rate Limiting

### Authentication
**File**: `api/middleware/auth.py`

All API endpoints now require Bearer token authentication:

```bash
# Correct
curl -H "Authorization: Bearer sk_polymarket_xxx" https://api.example.com/api/polymarket/bets

# Incorrect - will get 401
curl https://api.example.com/api/polymarket/bets
```

**Configuration**:
```bash
# .env
POLYMARKET_API_KEY=sk_polymarket_your_secret_key
RATE_LIMIT_PER_MINUTE=60
```

### Rate Limiting
- Per-client rate limiting (based on client IP)
- Default: 60 requests/minute
- Returns 429 Too Many Requests when exceeded

---

## New Endpoint: Bets API

### Overview
The new **Bets API** provides real-time visibility into all placed bets.

**File**: `api/routers/polymarket/bets.py`

### Endpoints

#### 1. List All Bets
```
GET /api/polymarket/bets
Headers: Authorization: Bearer <api_key>

Query Parameters:
  - limit: 1-500 (default 50)
  - status: active | closed | pending (optional)
  - sort: recent | confidence | roi | size (default recent)

Response:
{
  "bets": [
    {
      "bet_id": "market_123",
      "market_id": "0x...",
      "market_name": "Will ETH reach $5k by Q3 2026?",
      "side": "YES",
      "confidence": 0.72,
      "size": 100,
      "price": 0.65,
      "status": "active",
      "roi": null,
      "reasoning": "Strong technical setup + macroeconomic tailwinds",
      "executed_at": "2026-02-04T12:15:00Z"
    }
  ],
  "count": 42,
  "limit": 50
}
```

#### 2. Get Bet Details
```
GET /api/polymarket/bets/{bet_id}
Headers: Authorization: Bearer <api_key>

Response:
{
  "bet_id": "market_123",
  "market_id": "0x...",
  "market_name": "Will ETH reach $5k by Q3 2026?",
  "side": "YES",
  "confidence": 0.72,
  "size": 100,
  "price": 0.65,
  "status": "active",
  "roi": null,
  "roi_percent": null,
  "reasoning": "Strong technical setup + macroeconomic tailwinds",
  "agent_input": { ... },
  "agent_output": { ... },
  "executed_at": "2026-02-04T12:15:00Z",
  "completed_at": null,
  "order_details": { ... },
  "error": null
}
```

#### 3. Bet Summary Statistics
```
GET /api/polymarket/bets/stats/summary
Headers: Authorization: Bearer <api_key>

Response:
{
  "total_bets": 42,
  "active_bets": 18,
  "closed_bets": 22,
  "pending_bets": 2,
  "win_rate": 0.68,
  "avg_confidence": 0.71,
  "avg_roi": 0.042,
  "total_roi": 0.924,
  "largest_win": 0.25,
  "largest_loss": -0.15
}
```

#### 4. Get Active Bets
```
GET /api/polymarket/bets/recent/active
Headers: Authorization: Bearer <api_key>
Query: limit=10

Response:
{
  "active_bets": [
    {
      "bet_id": "market_123",
      "market_id": "0x...",
      "market_name": "Will ETH reach $5k by Q3 2026?",
      "side": "YES",
      "confidence": 0.72,
      "size": 100,
      "price": 0.65,
      "current_price": 0.68,
      "unrealized_roi": 0.045,
      "executed_at": "2026-02-04T12:15:00Z"
    }
  ],
  "count": 10,
  "limit": 10
}
```

---

## Simplified Betting Workflow

### Architecture
Instead of the heavy portfolio optimization, we now have a lightweight betting workflow:

**File**: `core/pipelines/simplified_betting_workflow.py`

**Class**: `SimplifiedBettingWorkflow`

### Process

```
1. Market Analysis
   - Get market details (volume, orderbook depth)
   - Check liquidity and spreads
   - Score opportunity (0.0-1.0)

2. Bet Decision
   - If score > confidence_threshold (default 0.65)
   - Place BET signal via log_trading_signal

3. Tracking
   - Decision saved to decision_service
   - ROI tracked when market closes
```

### Usage

```python
from camel.societies.workforce import Workforce
from core.pipelines.simplified_betting_workflow import SimplifiedBettingWorkflow
from core.clients.polymarket_client import PolymarketClient

# Initialize
workforce = ...  # Your CAMEL Workforce
api_client = PolymarketClient()

workflow = SimplifiedBettingWorkflow(workforce, api_client)

# Run
result = await workflow.analyze_and_bet(
    market_ids=["0x...", "0x..."],
    confidence_threshold=0.65,
    max_bets_per_run=5,
)

# Result:
# {
#   "run_id": "betting_run_1707012602",
#   "bets_placed": 3,
#   "bets": [...],
#   "status": "completed"
# }
```

### Key Features
- **Fast**: No heavy portfolio math, just market scoring
- **Simple**: 2-step pipeline (analyze → bet)
- **Focused**: Only bet if confidence high enough
- **Trackable**: All decisions logged and tied to bets

---

## Workforce Compatibility Updates

### WorkforceMode & WorkforceSnapshot
**File**: `core/camel_runtime/societies.py` (lines 248-290)

Added fallback implementations for different CAMEL versions:

```python
# Try CAMEL's WorkforceMode
try:
    from camel.societies.workforce import WorkforceMode
except:
    try:
        from camel.societies.workforce.workforce import WorkforceMode
    except:
        # Fallback: define minimal WorkforceMode
        class WorkforceMode(Enum):
            AUTO_DECOMPOSE = "AUTO_DECOMPOSE"
            PIPELINE = "PIPELINE"

# WorkforceSnapshot fallback
try:
    from camel.societies.workforce import WorkforceSnapshot
except:
    @dataclass
    class WorkforceSnapshot:
        main_task: Optional[Any] = None
        pending_tasks: Optional[Deque[Any]] = None
        completed_tasks: Optional[List[Any]] = None
        task_dependencies: Optional[Dict[str, List[str]]] = None
        assignees: Optional[Dict[str, str]] = None
        current_task_index: int = 0
        description: str = ''
```

This ensures compatibility across CAMEL versions without crashing on import failures.

---

## Logging & Debugging

### Better Error Logging for Embedding Issues

The system now logs detailed information about embedding errors:

```python
logger.warning(f"🔴 Vector shape error when collecting shared memory: {ve}\n"
             f"   This indicates embedding dimension mismatch (likely empty text input).\n"
             f"   Returning empty memory as fallback.")
```

### Message Filtering Logs

```python
logger.debug(f"Skipping empty {msg_type} message in {key}")
logger.info(f"✅ Collected shared memory: {coordinator_msgs} coordinator, "
           f"{task_agent_msgs} task_agent, {worker_msgs} worker records")
```

---

## Configuration

### .env Updates

```bash
# Authentication
POLYMARKET_API_KEY=sk_polymarket_your_secret_key

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Disable Neo4j (prevents segfaults)
DISABLE_NEO4J=true

# Ollama Configuration
OLLAMA_URL=http://localhost:11434  # or http://ats-ollama:11434 in Docker
```

---

## Testing

### Import Test
```python
from core.camel_runtime.societies import society_factory
from core.pipelines.simplified_betting_workflow import SimplifiedBettingWorkflow

# Should not raise ImportError even if CAMEL versions differ
```

### API Test
```bash
# List bets
curl -H "Authorization: Bearer sk_test_key" http://localhost:8000/api/polymarket/bets

# Get stats
curl -H "Authorization: Bearer sk_test_key" http://localhost:8000/api/polymarket/bets/stats/summary

# Active bets
curl -H "Authorization: Bearer sk_test_key" http://localhost:8000/api/polymarket/bets/recent/active
```

---

## Migration Guide

### For Existing Code

1. **Authentication**: Add Bearer token header to all API calls
   ```python
   headers = {"Authorization": f"Bearer {api_key}"}
   ```

2. **Bet Tracking**: Use new `/api/polymarket/bets/*` endpoints instead of manual decision queries

3. **Workflow**: Consider migrating heavy processes to `SimplifiedBettingWorkflow` for better performance

### For New Code

Use the new authenticated Bets API for all bet visibility needs:
```python
async def get_bets():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://api:8000/api/polymarket/bets",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        return response.json()
```

---

## Next Steps

1. **Production Deployment**: Set `POLYMARKET_API_KEY` in production .env
2. **Rate Limit Tuning**: Adjust `RATE_LIMIT_PER_MINUTE` based on expected load
3. **Bet Analysis**: Monitor Win Rate and ROI trends from stats endpoint
4. **Workflow Optimization**: Refine confidence thresholds in `SimplifiedBettingWorkflow`
5. **Monitoring**: Set up alerts for authentication failures and rate limit hits

---

## Related Files

- **Authentication**: `api/middleware/auth.py`
- **Bets Router**: `api/routers/polymarket/bets.py`
- **Betting Workflow**: `core/pipelines/simplified_betting_workflow.py`
- **Embedding Fix**: `core/camel_runtime/societies.py` (lines 1335-1395)
- **API Main**: `api/main_polymarket.py`
