"""Polymarket router package - Monitoring endpoints for UI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from api.models.polymarket import RssCacheResponse, WorkforceStatusResponse
from api.services.polymarket.config_service import process_config_service

from api.services.polymarket.logging_service import logging_service
from core.camel_runtime.societies import TradingWorkforceSociety

router = APIRouter()


@router.post("/workforce/trigger")
async def trigger_workforce():
    """Manually trigger a workforce agent cycle."""
    try:
        logging_service.log_event("INFO", "Manual workforce trigger received", {})
        society = TradingWorkforceSociety()
        workforce = await society.build()
        task = "Run the workforce agent cycle to check for new opportunities."
        if hasattr(workforce, "execute_task"):
            result = await workforce.execute_task(task)
        else:
            result = await workforce.process(task)
        
        logging_service.log_event("INFO", "Manual workforce trigger completed", {"result": result})
        return {"status": "ok", "message": "Workforce triggered successfully.", "result": result}
    except Exception as e:
        logging_service.log_event("ERROR", "Manual workforce trigger failed", {"error": str(e)})
        return {"status": "error", "message": str(e)}



@router.get("/workforce/status", response_model=WorkforceStatusResponse)
async def get_workforce_status():
    """Get workforce configuration and limits status for UI."""
    config = process_config_service.get_config()
    payload = {
        "status": "ok",
        "active_flux": config.get("active_flux"),
        "trade_frequency_hours": config.get("trade_frequency_hours"),
        "limits_status": config.get("limits_status"),
        "trigger_config": config.get("trigger_config"),
        "agent_weights": config.get("agent_weights"),
        "timestamp": config.get("last_updated"),
    }
    logging_service.log_event("INFO", "Fetched workforce status", payload)
    return WorkforceStatusResponse(**payload)


@router.get("/rss/cache", response_model=RssCacheResponse)
async def get_rss_cache():
    """Read cached Polymarket feed state (JSON file)."""
    cache_path = Path("logs/polymarket_feed_cache.json")
    if not cache_path.exists():
        return RssCacheResponse(status="ok", updated_at=None, count=0, markets={})

    try:
        data = json.loads(cache_path.read_text())
        markets = data.get("markets", {}) if isinstance(data, dict) else {}
        updated_at = data.get("updated_at") if isinstance(data, dict) else None
        count = data.get("count") if isinstance(data, dict) else len(markets)
        payload: Dict[str, Any] = {
            "status": "ok",
            "updated_at": updated_at,
            "count": count,
            "markets": markets,
        }
        logging_service.log_event("INFO", "Fetched RSS cache", {"count": count})
        return RssCacheResponse(**payload)
    except Exception:
        return RssCacheResponse(status="error", updated_at=None, count=0, markets={})


@router.post("/flux/start")
async def start_flux():
    """Start the RSS flux."""
    try:
        config = process_config_service.get_config()
        config["active_flux"] = "polymarket_rss_flux"
        process_config_service.update_config(config)
        logging_service.log_event("INFO", "Flux started", {})
        return {"status": "ok", "success": True, "message": "Flux started"}
    except Exception as e:
        logging_service.log_event("ERROR", "Failed to start flux", {"error": str(e)})
        return {"status": "error", "success": False, "message": str(e)}


@router.post("/flux/stop")
async def stop_flux():
    """Stop the RSS flux."""
    try:
        config = process_config_service.get_config()
        config["active_flux"] = "manual_trigger"
        process_config_service.update_config(config)
        logging_service.log_event("INFO", "Flux stopped", {})
        return {"status": "ok", "success": True, "message": "Flux stopped"}
    except Exception as e:
        logging_service.log_event("ERROR", "Failed to stop flux", {"error": str(e)})
        return {"status": "error", "success": False, "message": str(e)}

