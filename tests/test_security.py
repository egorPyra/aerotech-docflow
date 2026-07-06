"""Тесты авторизации по API-ключу."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import security as security_module


VALID_SCAN_REQUEST = {
    "external_request_id": "security-test-request",
    "task_id": 52418,
    "document_type": "UPD",
    "document_number": "2455/1",
    "user_code": "IV",
    "context": {
        "source": "planfix",
    },
}


def remove_api_key(
    client: TestClient,
) -> None:
    """Удалить API-ключ из заголовков клиента."""

    if "X-API-Key" in client.headers:
        del client.headers["X-API-Key"]


def test_scan_without_api_key_returns_401(
    client: TestClient,
) -> None:
    """POST /scan без ключа запрещён."""

    remove_api_key(client)

    response = client.post(
        "/scan",
        json=VALID_SCAN_REQUEST,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Неверный или отсутствующий API-ключ"
        )
    }

    assert (
        response.headers["www-authenticate"]
        == "ApiKey"
    )


def test_scan_with_wrong_api_key_returns_401(
    client: TestClient,
) -> None:
    """POST /scan с неверным ключом запрещён."""

    response = client.post(
        "/scan",
        json=VALID_SCAN_REQUEST,
        headers={
            "X-API-Key": "wrong-api-key",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Неверный или отсутствующий API-ключ"
        )
    }


def test_scan_with_correct_api_key_is_allowed(
    client: TestClient,
) -> None:
    """POST /scan с правильным ключом разрешён."""

    response = client.post(
        "/scan",
        json=VALID_SCAN_REQUEST,
    )

    assert response.status_code == 202


def test_jobs_without_api_key_returns_401(
    client: TestClient,
) -> None:
    """История заданий защищена API-ключом."""

    remove_api_key(client)

    response = client.get("/jobs")

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Неверный или отсутствующий API-ключ"
        )
    }


def test_health_does_not_require_api_key(
    client: TestClient,
) -> None:
    """Health-check доступен без API-ключа."""

    remove_api_key(client)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_unconfigured_api_key_returns_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Защищённый API недоступен без настройки ключа."""

    monkeypatch.setattr(
        security_module,
        "settings",
        SimpleNamespace(
            api_key="",
        ),
    )

    response = client.get("/jobs")

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "API-ключ сервиса не настроен"
        )
    }