"""UI routes for Polymarket dashboard (Jinja2)."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.config import settings
from api.routers.polymarket.clob import client as polymarket_client

templates = Jinja2Templates(directory="frontend/templates")
router = APIRouter()


def get_ui_context(request: Request) -> dict:
    """Get base context for all UI routes."""
    is_authenticated = polymarket_client.is_authenticated
    wallet_address = None
    if is_authenticated:
        # The client's get_address() method might exist on the underlying clob_client
        if hasattr(polymarket_client._clob_client, 'get_address'):
            wallet_address = polymarket_client._clob_client.get_address()
        else:
            # Fallback to the address from settings if available
            wallet_address = settings.polygon_address
            
    return {
        "request": request,
        "is_authenticated": is_authenticated,
        "wallet_address": wallet_address,
    }


@router.get("/ui", response_class=HTMLResponse)
async def ui_home(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/ui/markets", response_class=HTMLResponse)
async def ui_markets(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("markets.html", context)


@router.get("/ui/workforce", response_class=HTMLResponse)
async def ui_workforce(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("workforce.html", context)


@router.get("/ui/results", response_class=HTMLResponse)
async def ui_results(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("results.html", context)


@router.get("/ui/settings", response_class=HTMLResponse)
async def ui_settings(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("settings.html", context)


@router.get("/ui/chat", response_class=HTMLResponse)
async def ui_chat(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("chat.html", context)


@router.get("/ui/orders", response_class=HTMLResponse)
async def ui_orders(request: Request):
    context = get_ui_context(request)
    return templates.TemplateResponse("orders.html", context)
