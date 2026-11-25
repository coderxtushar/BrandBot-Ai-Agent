"""Accounts: sign up, sign in, sign out. Sessions are HTTP-only cookies."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import SESSION_COOKIE, current_user
from backend.config import get_settings
from backend.db import accounts as acc
from backend.db.models import User
from backend.db.session import get_session
from backend.schemas import LoginRequest, RegisterRequest, UserOut
from backend.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["accounts"])

# Small in-process limiter for password guessing: 10 attempts per 5 minutes per IP + email.
_WINDOW, _LIMIT = 300, 10
_attempts: dict[str, deque] = defaultdict(deque)


def _rate_limit(key: str) -> None:
    now = time.monotonic()
    q = _attempts[key]
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= _LIMIT:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Wait a few minutes and try again.")
    q.append(now)


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=s.session_days * 86400,
        httponly=True,  # not readable by JavaScript
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: RegisterRequest, response: Response, s: AsyncSession = Depends(get_session)):
    if await acc.get_user_by_email(s, data.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    user = await acc.create_user(s, name=data.name, email=data.email, password_hash=hash_password(data.password))
    token, _ = await acc.create_session(s, user, get_settings().session_days)
    _set_cookie(response, token)
    return acc.user_out(user)


@router.post("/login", response_model=UserOut)
async def login(data: LoginRequest, request: Request, response: Response, s: AsyncSession = Depends(get_session)):
    _rate_limit(f"{request.client.host if request.client else '?'}|{data.email.strip().lower()}")
    user = await acc.get_user_by_email(s, data.email)
    if not verify_password(user.password_hash if user else None, data.password):
        raise HTTPException(status_code=401, detail="That email and password don't match.")
    token, _ = await acc.create_session(s, user, get_settings().session_days)
    _set_cookie(response, token)
    return acc.user_out(user)


@router.post("/logout", status_code=204)
async def logout(request: Request, s: AsyncSession = Depends(get_session)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await acc.delete_session(s, token)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return acc.user_out(user)
