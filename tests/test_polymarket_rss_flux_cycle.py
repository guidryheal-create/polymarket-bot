import asyncio
from unittest.mock import AsyncMock

import pytest

from core.pipelines.polymarket_rss_flux import PolymarketRSSFlux


@pytest.mark.asyncio
async def test_polymarket_rss_flux_one_cycle():
    """Run a single RSS flux batch with mocked market scan and tasks."""
    workforce = AsyncMock()

    # Mock task execution to return BUY decisions with confidence
    async def _execute_task(task):
        return {"decision": "BUY", "confidence": 0.7, "reasoning": "test"}

    workforce.execute_task = _execute_task

    from datetime import datetime, timezone, timedelta
    close_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    class DummyClient:
        async def search_markets(self, query="", limit=20, filters=None):
            return [{"id": "m1", "title": "Test Market", "volume_24h": 1000, "liquidity_score": 80, "bid_ask_spread": 1.0, "close_time": close_time}]

    flux = PolymarketRSSFlux(workforce=workforce, api_client=DummyClient(), scan_interval=1, batch_size=1, review_threshold=1)

    # Force scanner to return a simple market list
    flux._execute_market_scanner = AsyncMock(return_value=[
        {"id": "m1", "title": "Test Market", "volume_24h": 1000, "liquidity_score": 80, "bid_ask_spread": 1.0, "close_time": close_time}
    ])
    # Force analysis and trade execution to bypass CAMEL Task schema
    flux._analyze_and_decide = AsyncMock(return_value={
        "market_id": "m1",
        "market_title": "Test Market",
        "decision": "BUY",
        "confidence": 0.7,
        "reasoning": "test",
    })
    flux._execute_trade = AsyncMock(return_value={"status": "success", "position_id": "pos_m1"})

    summary = await flux.process_market_batch()
    assert summary.get("status") != "failed", f"Batch failed: {summary}"
    assert summary["markets_scanned"] == 1
    assert summary["trades_executed"] == 1
