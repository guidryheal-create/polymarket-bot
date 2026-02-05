"""Polymarket RSS Flux router - Market scanning and automated trading control.

Provides API endpoints to:
- Start/stop RSS Flux scanning pipeline
- Configure scan intervals and trading limits
- Get flux status and active positions
- Trigger manual market batch processing
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks

from core.pipelines.polymarket_rss_flux import RSSFluxConfig, PolymarketRSSFlux
from core.logging import log
import asyncio

router = APIRouter()

# Global RSS Flux instance (initialized on startup)
_rss_flux_instance: Optional[PolymarketRSSFlux] = None


def set_rss_flux_instance(instance: PolymarketRSSFlux) -> None:
    """Set the global RSS Flux instance (called on API startup)."""
    global _rss_flux_instance
    _rss_flux_instance = instance
    log.info("[RSS FLUX API] Global instance initialized")


def get_rss_flux() -> PolymarketRSSFlux:
    """Get the global RSS Flux instance."""
    if _rss_flux_instance is None:
        raise HTTPException(
            status_code=503,
            detail="RSS Flux service not initialized",
        )
    return _rss_flux_instance


# ============================================================================
# Control Endpoints
# ============================================================================


@router.post("/flux/start")
async def start_rss_flux() -> Dict[str, Any]:
    """Start the RSS Flux market scanning pipeline.
    
    Returns:
        Status dict with flux configuration and initial state
    """
    flux = get_rss_flux()
    
    if flux._running:
        return {
            "status": "already_running",
            "message": "RSS Flux is already running",
            "config": {
                "scan_interval": flux.config.scan_interval,
                "batch_size": flux.config.batch_size,
                "max_trades_per_day": flux.config.max_trades_per_day,
            },
        }
    
    try:
        await flux.start()
        log.info("[RSS FLUX API] Flux started successfully")
        return {
            "status": "started",
            "message": "RSS Flux market scanning started",
            "config": {
                "scan_interval": flux.config.scan_interval,
                "batch_size": flux.config.batch_size,
                "max_trades_per_day": flux.config.max_trades_per_day,
                "min_confidence": flux.config.min_confidence,
            },
        }
    except Exception as exc:
        log.error("[RSS FLUX API] Failed to start flux: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start RSS Flux: {str(exc)}",
        )


@router.post("/flux/stop")
async def stop_rss_flux() -> Dict[str, Any]:
    """Stop the RSS Flux market scanning pipeline.
    
    Returns:
        Status dict confirming shutdown
    """
    flux = get_rss_flux()
    
    if not flux._running:
        return {
            "status": "already_stopped",
            "message": "RSS Flux is not running",
        }
    
    try:
        await flux.stop()
        log.info("[RSS FLUX API] Flux stopped successfully")
        return {
            "status": "stopped",
            "message": "RSS Flux market scanning stopped",
            "positions_active": len(flux._active_positions),
        }
    except Exception as exc:
        log.error("[RSS FLUX API] Failed to stop flux: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop RSS Flux: {str(exc)}",
        )


@router.post("/flux/trigger-scan")
async def trigger_manual_scan(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Manually trigger a market batch processing cycle.
    
    Runs the scan in a background task to avoid blocking the API response.
    
    Returns:
        Status dict with scan ID and configuration
    """
    flux = get_rss_flux()
    
    if not flux._running:
        # Start the flux in background if not running
        background_tasks.add_task(flux.start)
    
    try:
        # Trigger scan in background
        scan_id = f"manual_scan_{int(__import__('time').time())}"
        background_tasks.add_task(flux.process_market_batch)
        
        log.info("[RSS FLUX API] Manual scan triggered: %s", scan_id)
        
        return {
            "status": "triggered",
            "scan_id": scan_id,
            "message": "Market batch processing triggered in background",
            "config": {
                "batch_size": flux.config.batch_size,
                "review_threshold": flux.config.review_threshold,
            },
        }
    except Exception as exc:
        log.error("[RSS FLUX API] Failed to trigger scan: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger scan: {str(exc)}",
        )


# ============================================================================
# Status & Configuration Endpoints
# ============================================================================


@router.get("/flux/status")
async def get_flux_status() -> Dict[str, Any]:
    """Get current RSS Flux status and metrics.
    
    Returns:
        Status dict with running state, trades, positions, and configuration
    """
    flux = get_rss_flux()
    status = flux.get_status()
    
    return {
        "status": "running" if flux._running else "stopped",
        "running": flux._running,
        **status,
        "positions": {
            "active": len(flux._active_positions),
            "details": [
                {
                    "position_id": pos_id,
                    "market_id": pos_data.get("market_id"),
                    "market_title": pos_data.get("market_title"),
                    "entry_price": pos_data.get("entry_price"),
                    "confidence": pos_data.get("confidence"),
                }
                for pos_id, pos_data in flux._active_positions.items()
            ],
        },
    }


@router.get("/flux/config")
async def get_flux_config() -> Dict[str, Any]:
    """Get current RSS Flux configuration.
    
    Returns:
        Configuration dict with all tunable parameters
    """
    flux = get_rss_flux()
    config = flux.config
    
    return {
        "scan_interval": config.scan_interval,
        "batch_size": config.batch_size,
        "review_threshold": config.review_threshold,
        "max_cache": config.max_cache,
        "max_trades_per_day": config.max_trades_per_day,
        "min_confidence": config.min_confidence,
        "cache_path": config.cache_path,
    }


@router.post("/flux/config")
async def update_flux_config(
    scan_interval: Optional[int] = Query(None, ge=10, le=3600),
    batch_size: Optional[int] = Query(None, ge=1, le=100),
    review_threshold: Optional[int] = Query(None, ge=1, le=500),
    max_trades_per_day: Optional[int] = Query(None, ge=1, le=100),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
) -> Dict[str, Any]:
    """Update RSS Flux configuration.
    
    All parameters are optional. Unspecified parameters retain current values.
    Config changes take effect immediately.
    
    Args:
        scan_interval: Seconds between market scans (10-3600)
        batch_size: Number of markets per scan (1-100)
        review_threshold: Markets cached before review (1-500)
        max_trades_per_day: Maximum trades per day (1-100)
        min_confidence: Minimum confidence to trade (0.0-1.0)
    
    Returns:
        Updated configuration
    """
    flux = get_rss_flux()
    config = flux.config
    
    # Update config values if provided
    if scan_interval is not None:
        config.scan_interval = scan_interval
        flux.scan_interval = scan_interval
    if batch_size is not None:
        config.batch_size = batch_size
        flux.batch_size = batch_size
    if review_threshold is not None:
        config.review_threshold = review_threshold
        flux.review_threshold = review_threshold
    if max_trades_per_day is not None:
        config.max_trades_per_day = max_trades_per_day
    if min_confidence is not None:
        config.min_confidence = min_confidence
    
    log.info(
        "[RSS FLUX API] Configuration updated: scan_interval=%s, batch_size=%s, "
        "max_trades_per_day=%s, min_confidence=%s",
        scan_interval,
        batch_size,
        max_trades_per_day,
        min_confidence,
    )
    
    return {
        "status": "updated",
        "message": "RSS Flux configuration updated",
        "config": {
            "scan_interval": config.scan_interval,
            "batch_size": config.batch_size,
            "review_threshold": config.review_threshold,
            "max_cache": config.max_cache,
            "max_trades_per_day": config.max_trades_per_day,
            "min_confidence": config.min_confidence,
        },
    }


# ============================================================================
# Positions & Results Endpoints
# ============================================================================


@router.get("/flux/positions")
async def get_active_positions() -> Dict[str, Any]:
    """Get all currently active trading positions.
    
    Returns:
        Dict mapping position IDs to position details
    """
    flux = get_rss_flux()
    positions = flux.get_active_positions()
    
    return {
        "count": len(positions),
        "positions": positions,
    }


@router.get("/flux/positions/{position_id}")
async def get_position_details(position_id: str) -> Dict[str, Any]:
    """Get details for a specific position.
    
    Args:
        position_id: Position ID to retrieve
    
    Returns:
        Position details or 404 if not found
    """
    flux = get_rss_flux()
    positions = flux.get_active_positions()
    
    if position_id not in positions:
        raise HTTPException(
            status_code=404,
            detail=f"Position {position_id} not found",
        )
    
    return {
        "position_id": position_id,
        "details": positions[position_id],
    }


@router.get("/flux/metrics")
async def get_flux_metrics() -> Dict[str, Any]:
    """Get flux performance metrics and statistics.
    
    Returns:
        Metrics dict with trades, positions, and cache stats
    """
    flux = get_rss_flux()
    status = flux.get_status()
    
    return {
        "status": status,
        "cache_efficiency": {
            "cached_markets": len(flux._feed_cache),
            "active_positions": len(flux._active_positions),
            "trades_today": flux._trades_today,
            "max_trades_allowed": flux.config.max_trades_per_day,
        },
        "configuration": {
            "scan_interval_seconds": flux.config.scan_interval,
            "batch_size": flux.config.batch_size,
            "review_threshold": flux.config.review_threshold,
        },
    }


# ============================================================================
# Health & Diagnostics
# ============================================================================


@router.get("/flux/health")
async def flux_health_check() -> Dict[str, Any]:
    """Check RSS Flux service health.
    
    Returns:
        Health status with component information
    """
    flux = get_rss_flux()
    
    health = {
        "status": "healthy",
        "running": flux._running,
        "workforce": {
            "connected": hasattr(flux.workforce, "agents"),
            "type": type(flux.workforce).__name__ if flux.workforce else "None",
        },
        "api_client": {
            "connected": flux.api_client is not None,
            "type": type(flux.api_client).__name__ if flux.api_client else "None",
        },
        "cache": {
            "ready": True,
            "path": str(flux.cache_path),
            "cached_markets": len(flux._feed_cache),
        },
        "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
    }
    
    return health
