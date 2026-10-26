from hmac import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_admin(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    """Protege los endpoints administrativos durante la ejecucion local."""
    expected_key = get_settings().admin_api_key
    if not x_admin_key or not compare_digest(x_admin_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial administrativa invalida",
            headers={"WWW-Authenticate": "ApiKey"},
        )
