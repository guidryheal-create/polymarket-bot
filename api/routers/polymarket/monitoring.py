"""Polymarket router package - Monitoring endpoints for UI."""
from __future__ import annotations

import asyncio
import inspect
import threading
import json
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.models.polymarket import RssCacheResponse, WorkforceStatusResponse
from api.services.polymarket.config_service import process_config_service

from api.services.polymarket.logging_service import logging_service
from core.camel_runtime.societies import TradingWorkforceSociety

router = APIRouter()

_workforce_mcp_instance: Optional[Any] = None
_workforce_mcp_task: Optional[asyncio.Task] = None
_workforce_mcp_thread: Optional[threading.Thread] = None
_workforce_mcp_meta: Dict[str, Any] = {}


class MCPStartRequest(BaseModel):
    name: str = Field(default="CAMEL-Workforce")
    description: str = Field(default="A workforce system using the CAM multi-agent collaboration.")
    dependencies: List[str] = Field(default_factory=list)
    host: str = Field(default="localhost")
    port: int = Field(default=8001, ge=1, le=65535)
    start_server: bool = Field(default=True)


@router.post("/workforce/trigger")
async def trigger_workforce():
    """Manually trigger a workforce agent cycle."""
    global _workforce_mcp_thread
    try:
        logging_service.log_event("INFO", "Manual workforce trigger received", {})
        society = TradingWorkforceSociety()
        workforce = await society.build()
        task = "Run the workforce agent cycle to check for new opportunities."
        if hasattr(workforce, "process_task_async"):
            result = await workforce.process_task_async(task)
        else:
            result = await workforce.process_task(task)

        if hasattr(workforce, "get_workforce_log_tree"):
            print(workforce.get_workforce_log_tree())
        if hasattr(workforce, "get_pending_tasks"):
            print(workforce.get_pending_tasks())
        if hasattr(workforce, "get_completed_tasks"):
            print(workforce.get_completed_tasks())
        if hasattr(workforce, "get_workforce_kpis"):
            print(workforce.get_workforce_kpis())
        
        logging_service.log_event("INFO", "Manual workforce trigger completed", {"result": result})
        return {"status": "ok", "message": "Workforce triggered successfully.", "result": result}
    except Exception as e:
        logging_service.log_event("ERROR", "Manual workforce trigger failed", {"error": str(e)})
        return {"status": "error", "message": str(e)}



@router.get("/workforce/status", response_model=WorkforceStatusResponse)
async def get_workforce_status():
    """Get workforce configuration and limits status for UI."""
    config = process_config_service.get_config()
    limits_status = config.get("limits_status") or {}
    open_positions = None
    try:
        from api.routers.polymarket.rss_flux import get_rss_flux

        flux = get_rss_flux()
        open_positions = len(flux.get_active_positions())
    except Exception:
        open_positions = None

    if open_positions is not None:
        limits_status["open_positions"] = open_positions
    payload = {
        "status": "ok",
        "active_flux": config.get("active_flux"),
        "trade_frequency_hours": config.get("trade_frequency_hours"),
        "limits_status": limits_status,
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


@router.post("/workforce/mcp")
async def start_workforce_mcp(payload: MCPStartRequest):
    """Create (and optionally start) an MCP server from the workforce."""
    global _workforce_mcp_instance, _workforce_mcp_task, _workforce_mcp_meta
    try:
        society = TradingWorkforceSociety()
        workforce = await society.build()

        if not hasattr(workforce, "to_mcp"):
            return {"status": "error", "message": "Workforce does not support to_mcp()."}

        dependency_list = [d.strip() for d in payload.dependencies if d.strip()]

        _workforce_mcp_instance = workforce.to_mcp(
            name=payload.name,
            description=payload.description,
            dependencies=dependency_list or None,
            host=payload.host,
            port=payload.port,
        )

        _workforce_mcp_meta = {
            "name": payload.name,
            "description": payload.description,
            "dependencies": dependency_list,
            "host": payload.host,
            "port": payload.port,
        }

        started = False
        if payload.start_server:
            if _workforce_mcp_task and not _workforce_mcp_task.done():
                return {
                    "status": "ok",
                    "message": "MCP server already running.",
                    "mcp": _workforce_mcp_meta,
                    "started": True,
                }
            if _workforce_mcp_thread and _workforce_mcp_thread.is_alive():
                return {
                    "status": "ok",
                    "message": "MCP server already running.",
                    "mcp": _workforce_mcp_meta,
                    "started": True,
                }

            serve_method = getattr(_workforce_mcp_instance, "serve", None)
            run_method = getattr(_workforce_mcp_instance, "run", None)
            if callable(serve_method):
                if inspect.iscoroutinefunction(serve_method):
                    _workforce_mcp_task = asyncio.create_task(serve_method())
                    started = True
                else:
                    _workforce_mcp_thread = threading.Thread(target=serve_method, daemon=False)
                    _workforce_mcp_thread.start()
                    started = True
            elif callable(run_method):
                _workforce_mcp_thread = threading.Thread(target=run_method, daemon=False)
                _workforce_mcp_thread.start()
                started = True

        return {
            "status": "ok",
            "message": "MCP server initialized.",
            "started": started,
            "mcp": _workforce_mcp_meta,
        }
    except Exception as exc:
        logging_service.log_event("ERROR", "Failed to start workforce MCP", {"error": str(exc)})
        return {"status": "error", "message": str(exc)}


@router.get("/workforce/mcp")
async def workforce_mcp_status():
    """Get MCP server status for the workforce."""
    return {
        "status": "ok",
        "started": (
            (_workforce_mcp_task is not None and not _workforce_mcp_task.done())
            or (_workforce_mcp_thread is not None and _workforce_mcp_thread.is_alive())
        ),
        "mcp": _workforce_mcp_meta or None,
    }
