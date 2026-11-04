import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Cookie, Header, HTTPException, status

from app.core.config import get_settings

ADMIN_SESSION_COOKIE = "axm_admin_session"


def is_configured_secret(value: str, minimum_length: int) -> bool:
    return len(value) >= minimum_length and not value.startswith("replace-with-")


def _encode_urlsafe(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_urlsafe(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded, altchars=b"-_", validate=True)


def create_admin_session(username: str, secret: str, ttl_seconds: int) -> str:
    payload = json.dumps(
        {"sub": username, "exp": int(time.time()) + ttl_seconds},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = _encode_urlsafe(payload)
    signature = hmac.new(
        secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
    )
    return f"{encoded_payload}.{_encode_urlsafe(signature.digest())}"


def get_admin_session_username(token: str | None, secret: str) -> str | None:
    if not token or not secret:
        return None
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        signature = _decode_urlsafe(encoded_signature)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = _decode_urlsafe(encoded_payload)
        claims = json.loads(payload)
    except (ValueError, UnicodeError, binascii.Error):
        return None
    if (
        not isinstance(claims, dict)
        or not isinstance(claims.get("sub"), str)
        or not isinstance(claims.get("exp"), int)
        or isinstance(claims.get("exp"), bool)
        or claims["exp"] <= time.time()
    ):
        return None
    return claims["sub"]


async def require_admin(
    x_admin_key: Annotated[str | None, Header()] = None,
    admin_session: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> None:
    settings = get_settings()
    expected_key = settings.admin_api_key.get_secret_value()
    valid_api_key = (
        bool(is_configured_secret(expected_key, 32) and x_admin_key)
        and hmac.compare_digest(
            (x_admin_key or "").encode("utf-8"), expected_key.encode("utf-8")
        )
    )
    valid_session = (
        get_admin_session_username(
            admin_session, settings.admin_session_secret.get_secret_value()
        )
        == settings.admin_username
        and bool(settings.admin_username)
    )
    if not valid_api_key and not valid_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial administrativa invalida",
            headers={"WWW-Authenticate": "ApiKey"},
        )
