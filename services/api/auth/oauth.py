"""Platform connection endpoints: Google OAuth skeleton + dev credential entry.

Credentials always land in `HelmSecretStore` (server-side custody). The UI
never holds tokens; it only sees masked connection status.

Google (development setup via Google Cloud Console):
  1. Create an OAuth client (type "Web application") in Cloud Console,
     authorized redirect URI = {HELM_PUBLIC_URL}/api/oauth/google/callback.
  2. Set GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET in .env.
  3. GET /api/oauth/google/start → consent URL → callback stores the
     refresh token. developer_token + customer_id are added via
     POST /api/connections/google.

Meta: paste a Graph API access token + act_ ad account id (dev flow);
full Meta OAuth (app id/secret + code exchange) follows the same shape.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from services.api.auth.secret_store import HelmSecretStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["connections"])

secret_store = HelmSecretStore()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"


def _public_url() -> str:
    return os.environ.get("HELM_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")


def _mask(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "…" + value[-4:] if len(value) > 10 else "…" + value[-2:]


# ---------------------------------------------------------------------------
# Google OAuth (Cloud Console) skeleton
# ---------------------------------------------------------------------------


@router.get("/oauth/google/start")
def google_oauth_start() -> dict[str, Any]:
    """Build the Google consent URL for the Ads scope (offline access)."""
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "GOOGLE_OAUTH_CLIENT_ID is not set. Create an OAuth client in "
                "Google Cloud Console and set GOOGLE_OAUTH_CLIENT_ID / "
                "GOOGLE_OAUTH_CLIENT_SECRET in .env."
            ),
        )
    params = {
        "client_id": client_id,
        "redirect_uri": f"{_public_url()}/api/oauth/google/callback",
        "response_type": "code",
        "scope": _GOOGLE_ADS_SCOPE,
        "access_type": "offline",  # required to receive a refresh_token
        "prompt": "consent",
    }
    return {"auth_url": f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"}


@router.get("/oauth/google/callback")
async def google_oauth_callback(code: str = "", error: str = "") -> Any:
    """Exchange the authorization code for tokens; store the refresh token."""
    if error or not code:
        raise HTTPException(status_code=400, detail=f"Google OAuth failed: {error or 'no code returned'}")

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth client env vars are not configured.")

    async with httpx.AsyncClient(timeout=20.0) as http:
        resp = await http.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": f"{_public_url()}/api/oauth/google/callback",
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        logger.error("Google token exchange failed with HTTP %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Google token exchange failed.")

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google returned no refresh_token (re-run with prompt=consent).",
        )

    existing = secret_store.load("google_ads")
    existing.update(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    )
    secret_store.save("google_ads", existing)
    logger.info("Stored Google Ads refresh token in server-side custody.")
    return RedirectResponse(url="/?connected=google")


# ---------------------------------------------------------------------------
# Dev credential entry (manual paste while OAuth app is in dev/test mode)
# ---------------------------------------------------------------------------


class GoogleConnectionRequest(BaseModel):
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    refresh_token: str = Field(default="")
    developer_token: str = Field(default="")
    customer_id: str = Field(default="", description="Google Ads customer id, digits only")
    login_customer_id: str = Field(default="", description="MCC id if applicable")


class MetaConnectionRequest(BaseModel):
    access_token: str = Field(default="")
    ad_account_id: str = Field(default="", description="act_XXXX format")


@router.post("/connections/google")
def save_google_connection(req: GoogleConnectionRequest) -> dict[str, Any]:
    """Merge Google Ads credentials into server-side custody (partial updates ok)."""
    existing = secret_store.load("google_ads")
    for key, value in req.model_dump().items():
        if value:
            existing[key] = value.strip()
    if not existing:
        raise HTTPException(status_code=400, detail="No credential fields provided.")
    secret_store.save("google_ads", existing)
    return _connection_summary()


@router.post("/connections/meta")
def save_meta_connection(req: MetaConnectionRequest) -> dict[str, Any]:
    """Store Meta Graph credentials in server-side custody."""
    if not req.access_token or not req.ad_account_id:
        raise HTTPException(status_code=400, detail="access_token and ad_account_id are both required.")
    if not req.ad_account_id.startswith("act_"):
        raise HTTPException(status_code=400, detail="ad_account_id must start with 'act_'.")
    secret_store.save(
        "meta_ads",
        {"access_token": req.access_token.strip(), "ad_account_id": req.ad_account_id.strip()},
    )
    return _connection_summary()


@router.get("/connections")
def get_connections() -> dict[str, Any]:
    """Masked connection status for the console. Raw secrets never leave custody."""
    return _connection_summary()


@router.delete("/connections/{platform}")
def delete_connection(platform: str) -> dict[str, Any]:
    if platform not in ("google_ads", "meta_ads"):
        raise HTTPException(status_code=400, detail="platform must be google_ads or meta_ads")
    secret_store.delete(platform)
    return _connection_summary()


def _connection_summary() -> dict[str, Any]:
    google = secret_store.load("google_ads")
    meta = secret_store.load("meta_ads")
    google_required = ("client_id", "client_secret", "refresh_token", "developer_token", "customer_id")
    google_missing = [k for k in google_required if not google.get(k)]
    return {
        "google_ads": {
            "connected": not google_missing,
            "missing_fields": google_missing,
            "customer_id": google.get("customer_id", ""),
            "client_id": _mask(google.get("client_id", "")),
        },
        "meta_ads": {
            "connected": bool(meta.get("access_token") and meta.get("ad_account_id")),
            "ad_account_id": meta.get("ad_account_id", ""),
            "access_token": _mask(meta.get("access_token", "")),
        },
    }
