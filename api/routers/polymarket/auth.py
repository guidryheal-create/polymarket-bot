"""Authentication endpoints for Polymarket UI.

This router issues a session token and stores session data via the
`api.middleware.session` store. It returns the session token on login so
the frontend can persist it (in `localStorage` or as a cookie) and include
it in subsequent requests using the `X-Session-Token` header.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os

from api.services.polymarket.logging_service import logging_service
from api.middleware.session import set_session, get_session, delete_session

router = APIRouter()


# Pydantic models
class LoginRequest(BaseModel):
    api_key: str
    wallet_address: str | None = None


class LoginResponse(BaseModel):
    status: str
    message: str
    is_authenticated: bool
    wallet_address: str | None = None
    session_token: str | None = None


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user with API key and issue a session token."""
    try:
        # Validate the API key
        if not request.api_key or not request.api_key.strip():
            raise ValueError("API key is required and cannot be empty")

        if len(request.api_key) < 10:
            raise ValueError("API key appears to be too short")

        # Create a session token and persist session data
        session_id = os.urandom(16).hex()
        session_data = {
            "api_key": request.api_key,
            "wallet_address": request.wallet_address,
            "authenticated_at": str(__import__("datetime").datetime.now()),
        }
        try:
            set_session(session_id, session_data)
        except Exception:
            # If session store fails, still return token with in-memory fallback in middleware
            logging_service.log_event("WARN", "Session store set failed, falling back to memory", {})

        logging_service.log_event(
            "INFO",
            "User authenticated",
            {
                "api_key": request.api_key[:8] + "...",
                "wallet": request.wallet_address or "not provided",
            }
        )

        return LoginResponse(
            status="ok",
            message="Successfully authenticated",
            is_authenticated=True,
            wallet_address=request.wallet_address,
            session_token=session_id,
        )
    except ValueError as e:
        logging_service.log_event("WARN", "Authentication validation failed", {"error": str(e)})
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logging_service.log_event("ERROR", "Authentication failed", {"error": str(e)})
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


@router.get("/auth/status")
async def get_auth_status(request: Request):
    """Get current authentication status using session token header/cookie."""
    try:
        token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")
        if not token:
            return {"status": "ok", "is_authenticated": False, "wallet_address": None}

        session = get_session(token)
        if not session:
            return {"status": "ok", "is_authenticated": False, "wallet_address": None}

        return {"status": "ok", "is_authenticated": True, "wallet_address": session.get("wallet_address")}
    except Exception as e:
        logging_service.log_event("ERROR", "Auth status check failed", {"error": str(e)})
        return {"status": "error", "is_authenticated": False, "wallet_address": None}


@router.post("/auth/logout")
async def logout(request: Request):
    """Logout and remove the session from the store if token provided."""
    try:
        token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")
        if token:
            try:
                delete_session(token)
            except Exception:
                logging_service.log_event("WARN", "Failed to delete session (non-fatal)", {"token": token[:8] + "..."})

        logging_service.log_event("INFO", "User logged out", {})
        return {"status": "ok", "message": "Logged out successfully"}
    except Exception as e:
        logging_service.log_event("ERROR", "Logout failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

