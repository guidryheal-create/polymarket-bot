"""
Polymarket Trading Bot - Standalone API
Separate from forecasting API, focused only on Polymarket prediction market trading
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
from api.middleware.session import SessionAuthMiddleware
from core.camel_runtime import CamelTradingRuntime
from api.services.polymarket.config_service import process_config_service
from api.routers.polymarket.rss_flux import ensure_rss_flux

# Import routers
from api.routers.polymarket import (
    markets,
    positions,
    trades,
    analysis,
    decisions,
    chat,
    config,
    logs,
    settings,
    results,
    monitoring,
    ui,
    clob,
    rss_flux,
    bets,
    auth,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Polymarket Trading Bot API",
    description="Agentic trading system for Polymarket prediction markets",
    version="0.1.0",
)

@app.on_event("startup")
async def startup_event():
    """
    Application startup event.
    Initializes the CamelTradingRuntime.
    """
    logger.info("Application startup: Initializing CamelTradingRuntime...")
    await CamelTradingRuntime.instance()
    logger.info("CamelTradingRuntime initialized.")
    try:
        config = process_config_service.get_config()
        if config.get("active_flux") == "polymarket_rss_flux":
            flux = await ensure_rss_flux()
            if flux.trigger_type == "interval" and not flux._running:
                await flux.start()
                logger.info("RSS Flux started on startup (interval trigger).")
    except Exception as exc:
        logger.warning("RSS Flux startup init failed: %s", exc)

# Static assets for Jinja UI
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Attach session middleware so request.state.session is available
app.add_middleware(SessionAuthMiddleware)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "polymarket-trading-bot",
            "version": "0.1.0",
        },
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse(
        status_code=200,
        content={
            "message": "Polymarket Trading Bot API",
            "docs": "/docs",
            "health": "/health",
        },
    )


# Register routers
app.include_router(
    markets.router,
    prefix="/api/polymarket",
    tags=["Markets"],
)

app.include_router(
    positions.router,
    prefix="/api/polymarket",
    tags=["Positions"],
)

app.include_router(
    trades.router,
    prefix="/api/polymarket",
    tags=["Trades"],
)

app.include_router(
    analysis.router,
    prefix="/api/polymarket",
    tags=["Analysis"],
)

app.include_router(
    decisions.router,
    prefix="/api/polymarket",
    tags=["Decisions"],
)

app.include_router(
    chat.router,
    prefix="/api/polymarket",
    tags=["Chat"],
)

app.include_router(
    config.router,
    prefix="/api/polymarket",
    tags=["Config"],
)

app.include_router(
    logs.router,
    prefix="/api/polymarket",
    tags=["Logs"],
)

app.include_router(
    settings.router,
    prefix="/api/polymarket",
    tags=["Settings"],
)

app.include_router(
    results.router,
    prefix="/api/polymarket",
    tags=["Results"],
)

app.include_router(
    monitoring.router,
    prefix="/api/polymarket",
    tags=["Monitoring"],
)

app.include_router(
    clob.router,
    prefix="/api/polymarket",
    tags=["CLOB"],
)

app.include_router(
    rss_flux.router,
    prefix="/api/polymarket",
    tags=["RSS Flux"],
)

app.include_router(
    bets.router,
    prefix="/api/polymarket",
    tags=["Bets"],
)

app.include_router(
    auth.router,
    prefix="/api/polymarket",
    tags=["Auth"],
)

app.include_router(
    ui.router,
    tags=["UI"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main_polymarket:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
