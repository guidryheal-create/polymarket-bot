import asyncio

from api.routers.polymarket import settings as settings_router
from api.routers.polymarket import results as results_router
from api.models.polymarket import SettingsUpdateRequest


def test_settings_get_and_update():
    data = asyncio.run(settings_router.get_settings())
    payload = data.model_dump() if hasattr(data, "model_dump") else data
    assert payload["status"] == "ok"
    assert "config" in payload

    update_payload = {
        "process": {
            "active_flux": "polymarket_rss_flux",
            "trade_frequency_hours": 6,
            "max_ai_weighted_daily": 0.8,
            "max_ai_weighted_per_trade": 0.5,
        }
    }
    updated = asyncio.run(settings_router.update_settings(SettingsUpdateRequest(**update_payload)))
    updated_payload = updated.model_dump() if hasattr(updated, "model_dump") else updated
    assert updated_payload["status"] == "ok"
    assert updated_payload["config"]["active_flux"] == "polymarket_rss_flux"


def test_results_summary_and_trades(monkeypatch):
    monkeypatch.setattr(results_router.trade_service, "get_summary", lambda: {"total_trades": 0})
    monkeypatch.setattr(results_router.trade_service, "list_trades", lambda limit=50, status=None, asset=None: [])

    summary = asyncio.run(results_router.get_results_summary())
    summary_payload = summary.model_dump() if hasattr(summary, "model_dump") else summary
    assert summary_payload["status"] == "ok"
    assert "summary" in summary_payload

    trades = asyncio.run(results_router.get_recent_trades(limit=10))
    trades_payload = trades.model_dump() if hasattr(trades, "model_dump") else trades
    assert trades_payload["status"] == "ok"
    assert trades_payload["count"] == 0
