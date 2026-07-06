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
    """Создать репозиторий с временной SQLite-базой."""

    return JobRepository(
        database_path=tmp_path / "test.db",
    )


@pytest.fixture
def started_jobs() -> list[
    tuple[UUID, ScanRequest]
]:
    """Задания, переданные фоновой обработке."""

    return []


@pytest.fixture
def cancelled_jobs() -> list[UUID]:
    """Задания, переданные функции отмены."""

    return []


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    repository: JobRepository,
    started_jobs: list[
        tuple[UUID, ScanRequest]
    ],
    cancelled_jobs: list[UUID],
) -> Iterator[TestClient]:
    """Создать тестовый HTTP-клиент."""

    def fake_start_scan_job(
        request_id: UUID,
        payload: ScanRequest,
    ) -> None:
        started_jobs.append(
            (
                request_id,
                payload,
            )
        )

    async def fake_cancel_scan_job(
        request_id: UUID,
    ) -> bool:
        cancelled_jobs.append(
            request_id
        )

        return True

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

    monkeypatch.setattr(
        main_module,
        "cancel_scan_job",
        fake_cancel_scan_job,
    )

    with TestClient(
        main_module.app
    ) as test_client:
        yield test_client