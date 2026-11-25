"""Connecting social accounts with OAuth."""

import logging
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import clients_dep, current_user
from backend.config import get_settings
from backend.db import accounts as acc
from backend.db.models import User, utcnow
from backend.db.session import get_session
from backend.schemas import PUBLISHABLE, ConnectionsOut, PlatformConnectInfo
from backend.security import get_cipher, new_state, pkce_pair

router = APIRouter(prefix="/connections", tags=["connections"])
log = logging.getLogger("brandbot")

ENV_NAMES = {
    "linkedin": "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET",
    "x": "X_CLIENT_ID and X_CLIENT_SECRET",
    "threads": "THREADS_APP_ID and THREADS_APP_SECRET",
    "instagram": "INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET",
}
NOTES = {
    "linkedin": "Posts to your personal profile, with the image if the draft has one.",
    "x": "Posts threads as text. Images aren't attached on X yet.",
    "threads": "Posts threads, with the image on the first post.",
    "instagram": "Business or Creator accounts. Posts the cover image with the caption.",
}


def _redirect_uri(platform: str) -> str:
    return f"{get_settings().api_public_url.rstrip('/')}/connections/{platform}/callback"


def _client(platform: str, clients: dict):
    if platform not in PUBLISHABLE:
        raise HTTPException(status_code=404, detail="Publishing to this platform isn't supported.")
    return clients[platform]


@router.get("", response_model=ConnectionsOut)
async def list_connections(s: AsyncSession = Depends(get_session), user: User = Depends(current_user), clients=Depends(clients_dep)):
    platforms = []
    for p in PUBLISHABLE:
        available = clients[p].configured()
        note = NOTES[p] if available else f"Ask whoever runs this server to add {ENV_NAMES[p]}."
        platforms.append(PlatformConnectInfo(platform=p, available=available, note=note))
    return ConnectionsOut(accounts=[acc.connection_out(a) for a in await acc.list_accounts(s, user.id)], platforms=platforms)


@router.post("/{platform}/start")
async def start_connection(
    platform: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user), clients=Depends(clients_dep)
):
    """Returns the platform's consent URL. The browser goes there, then comes back to /callback."""
    client = _client(platform, clients)
    if not client.configured():
        raise HTTPException(status_code=400, detail=f"{client.label} isn't set up on this server yet ({ENV_NAMES[platform]}).")
    state = new_state()
    verifier, challenge = pkce_pair()
    await acc.save_oauth_state(s, state=state, user_id=user.id, platform=platform, verifier=verifier)
    return {"url": client.authorize_url(state=state, code_challenge=challenge, redirect_uri=_redirect_uri(platform))}


def _back(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{get_settings().web_url.rstrip('/')}/studio/connections?{urlencode(params)}", status_code=303)


@router.get("/{platform}/callback", include_in_schema=False)
async def finish_connection(
    platform: str,
    state: str = "",
    code: str = "",
    error: str = "",
    error_description: str = "",
    s: AsyncSession = Depends(get_session),
    clients=Depends(clients_dep),
):
    """The platform sends the browser here. The one-time state says who started it (no cookie needed)."""
    client = _client(platform, clients)
    pending = await acc.pop_oauth_state(s, state, platform) if state else None
    if pending is None:
        return _back(error="That connection link expired. Try connecting again.")
    if error or not code:
        return _back(error=error_description or f"{client.label} didn't grant access.")
    try:
        tokens = await client.exchange_code(code=code, code_verifier=pending.code_verifier, redirect_uri=_redirect_uri(platform))
        profile = await client.fetch_profile(tokens.access_token)
    except Exception as exc:
        log.warning("Connecting %s failed: %s", platform, exc)
        return _back(error=f"Couldn't connect {client.label}: {exc}")

    cipher = get_cipher()
    await acc.upsert_account(
        s,
        user_id=pending.user_id,
        platform=platform,
        external_id=profile.external_id,
        display_name=profile.display_name,
        username=profile.username,
        access_token=cipher.encrypt(tokens.access_token),
        refresh_token=cipher.encrypt(tokens.refresh_token) if tokens.refresh_token else None,
        expires_at=utcnow() + timedelta(seconds=tokens.expires_in) if tokens.expires_in else None,
        scopes=tokens.scope,
    )
    return _back(connected=platform)


@router.delete("/{account_id}", status_code=204)
async def disconnect(account_id: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)):
    account = await acc.get_account(s, account_id, user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    await acc.delete_account(s, account)
    return Response(status_code=204)
