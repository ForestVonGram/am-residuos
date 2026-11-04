import hmac
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.core.config import get_settings
from app.core.security import (
    ADMIN_SESSION_COOKIE,
    create_admin_session,
    get_admin_session_username,
    is_configured_secret,
)
from app.schemas.auth import AdminLogin, AdminSession

router = APIRouter()


@router.post("/login", response_model=AdminSession)
async def login(data: AdminLogin, response: Response) -> AdminSession:
    settings = get_settings()
    expected_password = settings.admin_password.get_secret_value()
    session_secret = settings.admin_session_secret.get_secret_value()
    if (
        not settings.admin_username
        or not is_configured_secret(expected_password, 12)
        or not is_configured_secret(session_secret, 32)
        or (
            settings.app_env.casefold() == "production"
            and not settings.admin_cookie_secure
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La autenticación administrativa no está configurada",
        )

    username_matches = hmac.compare_digest(
        data.username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    password_matches = hmac.compare_digest(
        data.password.encode("utf-8"), expected_password.encode("utf-8")
    )
    if not (username_matches and password_matches):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    session = create_admin_session(
        settings.admin_username,
        session_secret,
        settings.admin_session_ttl_seconds,
    )
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=session,
        max_age=settings.admin_session_ttl_seconds,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        path=f"{settings.api_v1_prefix}/admin",
    )
    return AdminSession(username=settings.admin_username)


@router.get("/session", response_model=AdminSession)
async def get_session(
    admin_session: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> AdminSession:
    settings = get_settings()
    username = get_admin_session_username(
        admin_session, settings.admin_session_secret.get_secret_value()
    )
    if not username or username != settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión administrativa inválida",
        )
    return AdminSession(username=username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE,
        path=f"{settings.api_v1_prefix}/admin",
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
    )
