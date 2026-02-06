"""Polymarket router package - Settings for UI and workflow."""
from fastapi import APIRouter

from api.models.polymarket import SettingsResponse, SettingsUpdateRequest
from api.services.polymarket.config_service import process_config_service
from api.services.polymarket.logging_service import logging_service

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get UI-friendly settings and workflow configuration."""
    config = process_config_service.get_config()
    response = SettingsResponse(
        status="ok",
        config=config,
        ui={
            "polymarket_only": True,
            "uses_env_defaults": True,
            "flux_trigger_types": ["manual", "interval"],
            "flux_default_interval_hours": config.get("trigger_config", {}).get("interval_hours", 4),
            "features": [
                "market_search",
                "market_details",
                "trade_propose_execute",
                "decision_history",
                "logs",
                "results_summary",
            ],
            "deprecated": [],
        },
        timestamp=config.get("last_updated", ""),
    )
    return response


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdateRequest):
    """Update workflow settings for UI and trading controls."""
    updated = process_config_service.update_config(payload.model_dump(exclude_none=True))
    logging_service.log_event("INFO", "Updated settings", updated)
    response = SettingsResponse(
        status="ok",
        config=updated,
        ui={
            "polymarket_only": True,
            "features": [
                "market_search",
                "market_details",
                "trade_propose_execute",
                "decision_history",
                "logs",
                "results_summary",
            ],
            "deprecated": [],
        },
        timestamp=updated.get("last_updated", ""),
    )
    return response
