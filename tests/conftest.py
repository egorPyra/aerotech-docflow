"""Общие фикстуры тестов."""

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.repository import JobRepository
from app.schemas import ScanRequest


@pytest.fixture
def repository(
    tmp_path: Path,
) -> JobRepository:
    """Создать репозиторий с отдельной временной базой."""

    database_path = tmp_path / "test.db"

    return JobRepository(
        database_path=database_path,
    )


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    repository: JobRepository,
) -> Iterator[TestClient]:
    """
    Создать HTTP-клиент с временной базой.

    Фоновый процесс сканирования отключается, чтобы API-тесты
    не ждали появления настоящего PDF.
    """

    def fake_start_scan_job(
        request_id: UUID,
        payload: ScanRequest,
    ) -> None:
        del request_id
        del payload

    monkeypatch.setattr(
        main_module,
        "job_repository",
        repository,
    )

    monkeypatch.setattr(
        main_module,
        "start_scan_job",
        fake_start_scan_job,
    )

    with TestClient(main_module.app) as test_client:
        yield test_client