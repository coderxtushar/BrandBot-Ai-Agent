"""Passwords, session tokens, and encryption of platform tokens at rest."""

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings

_hasher = PasswordHasher()

# A real hash to verify against when the email doesn't exist, so response time doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Sessions store only this hash, so a database leak doesn't leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_state() -> str:
    return secrets.token_urlsafe(24)


def pkce_pair() -> tuple[str, str]:
    """(code_verifier, S256 code_challenge) for OAuth 2.0 PKCE."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class TokenCipher:
    """Encrypts OAuth tokens before they're written to the database."""

    def __init__(self, secret_key: str):
        # Derive a Fernet key from the app secret (domain-separated so it isn't reused elsewhere).
        key = hmac.new(secret_key.encode(), b"brandbot/platform-tokens/v1", hashlib.sha256).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Stored token can't be decrypted. Was SECRET_KEY changed? Reconnect the account.") from exc


@lru_cache
def get_cipher() -> TokenCipher:
    return TokenCipher(get_settings().secret_key)
