"""Авторизация HTTP-запросов по API-ключу."""

import secrets
from typing import Annotated

from fastapi import (
    HTTPException,
    Security,
    status,
)
from fastapi.security import APIKeyHeader

from app.config import settings


API_KEY_HEADER_NAME = "X-API-Key"


api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    description=(
        "Секретный API-ключ Aerotech Docflow"
    ),
    auto_error=False,
)


async def require_api_key(
    provided_api_key: Annotated[
        str | None,
        Security(api_key_header),
    ],
) -> None:
    """Проверить API-ключ входящего запроса."""

    configured_api_key = settings.api_key

    if not configured_api_key:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "API-ключ сервиса не настроен"
            ),
        )

    if (
        provided_api_key is None
        or not secrets.compare_digest(
            provided_api_key,
            configured_api_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Неверный или отсутствующий API-ключ"
            ),
            headers={
                "WWW-Authenticate": "ApiKey",
            },
        )