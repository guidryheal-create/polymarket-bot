# Bets API Quick Reference

## Base URL
```
https://api.example.com/api/polymarket
```

## Authentication
All endpoints require Bearer token:
```
Authorization: Bearer sk_polymarket_your_api_key
```

## Endpoints

### 1. List Bets
```http
GET /bets
```

**Query Parameters**:
- `limit` (int, 1-500, default 50)
- `status` (string, optional): "active" | "closed" | "pending"
- `sort` (string, default "recent"): "recent" | "confidence" | "roi" | "size"

**Example**:
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets?limit=50&status=active&sort=confidence"
```

**Response**:
```json
{
  "bets": [
    {
      "bet_id": "market_123",
      "market_id": "0x...",
      "market_name": "Will ETH reach $5k?",
      "side": "YES",
      "confidence": 0.72,
      "size": 100,
      "price": 0.65,
      "status": "active",
      "roi": null,
      "reasoning": "Strong technical setup",
      "executed_at": "2026-02-04T12:15:00Z"
    }
  ],
  "count": 10,
  "limit": 50,
  "status_filter": "active",
  "sort": "confidence",
  "timestamp": "2026-02-04T12:50:00Z"
}
```

---

### 2. Get Bet Details
```http
GET /bets/{bet_id}
```

**Parameters**:
- `bet_id` (path, string): Bet identifier

**Example**:
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets/market_123"
```

**Response**:
```json
{
  "bet_id": "market_123",
  "market_id": "0x...",
  "market_name": "Will ETH reach $5k?",
  "side": "YES",
  "confidence": 0.72,
  "size": 100,
  "price": 0.65,
  "status": "active",
  "roi": null,
  "roi_percent": null,
  "reasoning": "Strong technical setup + macroeconomic tailwinds",
  "agent_input": {
    "market_id": "0x...",
    "analysis_type": "BET"
  },
  "agent_output": {
    "decision": "BET_YES",
    "confidence_score": 0.72,
    "expected_value": 0.045
  },
  "executed_at": "2026-02-04T12:15:00Z",
  "completed_at": null,
  "order_details": {
    "order_id": "order_xyz",
    "filled_at": "2026-02-04T12:15:15Z",
    "slippage": 0.02
  },
  "error": null,
  "timestamp": "2026-02-04T12:50:00Z"
}
```

---

### 3. Get Summary Statistics
```http
GET /bets/stats/summary
```

**No query parameters**

**Example**:
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets/stats/summary"
```

**Response**:
```json
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
  "largest_loss": -0.15,
  "timestamp": "2026-02-04T12:50:00Z"
}
```

**Interpretation**:
- `win_rate`: Percentage of closed bets that were profitable (68%)
- `avg_confidence`: Average confidence score on all bets (0.71 = 71%)
- `avg_roi`: Average return on closed bets (4.2% per bet)
- `total_roi`: Cumulative return across all closed bets (92.4%)
- `largest_win`: Best single bet ROI (25%)
- `largest_loss`: Worst single bet ROI (-15%)

---

### 4. Get Active Bets
```http
GET /bets/recent/active
```

**Query Parameters**:
- `limit` (int, 1-100, default 10)

**Example**:
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets/recent/active?limit=10"
```

**Response**:
```json
{
  "active_bets": [
    {
      "bet_id": "market_123",
      "market_id": "0x...",
      "market_name": "Will ETH reach $5k?",
      "side": "YES",
      "confidence": 0.72,
      "size": 100,
      "price": 0.65,
      "current_price": 0.68,
      "unrealized_roi": 0.045,
      "executed_at": "2026-02-04T12:15:00Z"
    }
  ],
  "count": 5,
  "limit": 10,
  "timestamp": "2026-02-04T12:50:00Z"
}
```

**Interpretation**:
- `unrealized_roi`: Current profit/loss if closed now at current_price
  - Entered at 0.65, now at 0.68 = +4.5% unrealized gain

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 401 | Missing/invalid Authorization header |
| 403 | Invalid API key |
| 404 | Bet not found |
| 429 | Rate limit exceeded (60 req/min) |
| 500 | Server error |

---

## Error Response Format

```json
{
  "detail": "Invalid API key"
}
```

---

## Rate Limiting

- **Limit**: 60 requests per minute per client IP
- **Response**: HTTP 429 when exceeded
- **Reset**: Per-minute window (resets after 60 seconds)

To check your usage, monitor response headers (when implemented).

---

## Field Reference

### Bet Object

| Field | Type | Description |
|-------|------|-------------|
| bet_id | string | Unique bet identifier |
| market_id | string | Polymarket market ID |
| market_name | string | Human-readable market question |
| side | string | "YES" or "NO" |
| confidence | float | 0.0-1.0 confidence score |
| size | float | Amount bet (USDC) |
| price | float | Entry price (0.0-1.0) |
| current_price | float | Current market price |
| status | string | "active", "closed", "pending" |
| roi | float | Realized ROI for closed bets (0.25 = 25%) |
| roi_percent | float | Realized ROI percentage |
| unrealized_roi | float | Unrealized ROI for active bets |
| reasoning | string | Why this bet was placed |
| executed_at | timestamp | When bet was placed |
| completed_at | timestamp | When bet was closed (if closed) |
| error | string | Error message if bet failed |

---

## Common Use Cases

### Get Winning Bets
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets?status=closed&sort=roi" \
  | jq '.bets[] | select(.roi > 0)'
```

### Monitor Win Rate
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets/stats/summary" \
  | jq '.win_rate'
```

### Check Current Exposure
```bash
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets/recent/active" \
  | jq '[.active_bets[].size] | add'
```

### Track Performance Over Time
```bash
# Save stats daily
curl -H "Authorization: Bearer sk_..." \
  "https://api/polymarket/bets/stats/summary" \
  >> performance_history.jsonl
```

---

## Python Client Example

```python
import httpx
from datetime import datetime

class PolymarketBetsClient:
    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    async def list_bets(self, limit: int = 50, status: str = None, sort: str = "recent"):
        async with httpx.AsyncClient() as client:
            params = {"limit": limit, "sort": sort}
            if status:
                params["status"] = status
            
            response = await client.get(
                f"{self.base_url}/api/polymarket/bets",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def get_bet(self, bet_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/polymarket/bets/{bet_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_stats(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/polymarket/bets/stats/summary",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_active_bets(self, limit: int = 10):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/polymarket/bets/recent/active",
                headers=self.headers,
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()

# Usage
async def main():
    client = PolymarketBetsClient("sk_polymarket_xxx")
    
    # Get stats
    stats = await client.get_stats()
    print(f"Win rate: {stats['win_rate']}")
    print(f"Total ROI: {stats['total_roi']}")
    
    # Get active bets
    active = await client.get_active_bets(limit=5)
    for bet in active["active_bets"]:
        print(f"{bet['market_name']}: {bet['unrealized_roi']*100:.1f}%")

# asyncio.run(main())
```

---

## Debugging

### 401 Unauthorized
```json
{"detail": "Missing Authorization header"}
```
**Fix**: Add header: `Authorization: Bearer sk_...`

```json
{"detail": "Invalid Authorization header format. Expected 'Bearer <api_key>'"}
```
**Fix**: Format must be exactly: `Bearer sk_xxx` (no extra spaces)

### 403 Forbidden
```json
{"detail": "Invalid API key"}
```
**Fix**: Check `POLYMARKET_API_KEY` in `.env` matches header value

### 429 Rate Limited
```json
{"detail": "Rate limit exceeded: 60 requests per minute"}
```
**Fix**: Wait 60 seconds before retrying, or increase `RATE_LIMIT_PER_MINUTE` in `.env`

### 404 Not Found
```json
{"detail": "Bet market_xyz not found"}
```
**Fix**: Verify bet_id exists, use `/bets` to list available bets

---

## Changelog

**v1.0 - Feb 4, 2026**
- Initial release
- 4 core endpoints
- Bearer token authentication
- Rate limiting (60 req/min)
- Real-time ROI tracking
