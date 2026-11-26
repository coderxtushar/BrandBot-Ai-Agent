"""Accounts: sign up, sign in, sign out. Sessions are HTTP-only cookies."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import SESSION_COOKIE, current_user
from backend.config import get_settings
from backend.db import accounts as acc
from backend.db.models import User
from backend.db.session import get_session
from backend.ratelimit import check, ip_of
from backend.schemas import ChangePasswordRequest, LoginRequest, PasswordChanged, RegisterRequest, UserOut
from backend.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["accounts"])

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
async def register(data: RegisterRequest, request: Request, response: Response, s: AsyncSession = Depends(get_session)):
    await check(s, "signup", ip_of(request), "rate_limit_signup", what="new accounts")
    if await acc.get_user_by_email(s, data.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    user = await acc.create_user(s, name=data.name, email=data.email, password_hash=hash_password(data.password))
    token, _ = await acc.create_session(s, user, get_settings().session_days)
    _set_cookie(response, token)
    return acc.user_out(user)


@router.post("/login", response_model=UserOut)
async def login(data: LoginRequest, request: Request, response: Response, s: AsyncSession = Depends(get_session)):
    # Password guessing: limited per IP + email (shared across API instances).
    await check(s, "login", f"{ip_of(request)}|{data.email.strip().lower()}", "rate_limit_login", what="sign-in attempts")
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


@router.post("/password", response_model=PasswordChanged)
async def change_password(
    data: ChangePasswordRequest, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)
):
    """Change the password. Needs the current one, so a borrowed signed-in browser can't lock the owner out;
    limited like sign-in so it can't be used to guess it. Other sessions are signed out, this one stays."""
    await check(s, "password", user.id, "rate_limit_login", what="password attempts")
    if not verify_password(user.password_hash, data.current_password):
        # 400, not 401: the session is fine, and 401 would sign the browser out.
        raise HTTPException(status_code=400, detail="Your current password isn't right.")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="Choose a new password that's different from the current one.")
    signed_out = await acc.change_password(s, user, hash_password(data.new_password), request.cookies.get(SESSION_COOKIE))
    return PasswordChanged(signed_out_sessions=signed_out)
