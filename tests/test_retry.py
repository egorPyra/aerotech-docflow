"""Тесты повторного запуска заданий."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.repository import JobRepository
from app.schemas import (
    JobStatus,
    ScanRequest,
)


def create_request(
    external_request_id: str,
) -> dict[str, object]:
    """Создать тело POST /scan."""

    return {
        "external_request_id": external_request_id,
        "task_id": 52418,
        "document_type": "UPD",
        "document_number": "2455/1",
        "user_code": "IV",
        "context": {
            "source": "planfix",
        },
    }


def test_retry_failed_job(
    client: TestClient,
    repository: JobRepository,
    started_jobs: list[
        tuple[UUID, ScanRequest]
    ],
) -> None:
    """Failed-задание можно запустить повторно."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "retry-failed-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.FAILED,
        error="Тестовая ошибка",
    )

    response = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert response.status_code == 202

    assert response.json() == {
        "status": "accepted",
        "request_id": str(request_id),
        "job_status": "accepted",
        "attempt_count": 2,
        "message": "Задание повторно запущено",
    }

    saved_job = repository.get(
        request_id
    )

    assert saved_job is not None
    assert saved_job.status == JobStatus.ACCEPTED
    assert saved_job.attempt_count == 2
    assert saved_job.error is None

    assert len(started_jobs) == 2
    assert started_jobs[0][0] == request_id
    assert started_jobs[1][0] == request_id


def test_retry_cancelled_job(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """Отменённое задание можно запустить повторно."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "retry-cancelled-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.CANCELLED,
    )

    response = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert response.status_code == 202

    saved_job = repository.get(
        request_id
    )

    assert saved_job is not None
    assert saved_job.status == JobStatus.ACCEPTED
    assert saved_job.attempt_count == 2


def test_retry_clears_previous_result(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """Retry очищает данные предыдущей попытки."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "retry-clear-result-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.set_source_file(
        request_id=request_id,
        source_file=r"D:\incoming\scan.pdf",
    )

    repository.set_archive_result(
        request_id=request_id,
        result_file=r"D:\archive\result.pdf",
        result_filename="result.pdf",
        sha256="a" * 64,
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.FAILED,
        error="Ошибка архива",
    )

    response = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert response.status_code == 202

    saved_job = repository.get(
        request_id
    )

    assert saved_job is not None
    assert saved_job.source_file is None
    assert saved_job.result_file is None
    assert saved_job.result_filename is None
    assert saved_job.sha256 is None
    assert saved_job.error is None


def test_retry_increments_attempt_count(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """Каждый retry увеличивает счётчик попыток."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "retry-count-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.FAILED,
        error="Ошибка первой попытки",
    )

    first_retry = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert first_retry.status_code == 202
    assert (
        first_retry.json()["attempt_count"]
        == 2
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.FAILED,
        error="Ошибка второй попытки",
    )

    second_retry = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert second_retry.status_code == 202
    assert (
        second_retry.json()["attempt_count"]
        == 3
    )


def test_retry_done_job_returns_409(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """Завершённое задание нельзя перезапустить."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "retry-done-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.DONE,
    )

    response = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Завершённое задание "
            "нельзя повторно запустить"
        )
    }


def test_retry_active_job_returns_409(
    client: TestClient,
) -> None:
    """Активное задание нельзя запустить второй раз."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "retry-active-request"
        ),
    )

    request_id = (
        create_response.json()["request_id"]
    )

    response = client.post(
        f"/jobs/{request_id}/retry"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Задание уже активно "
            "или находится в процессе обработки"
        )
    }


def test_retry_unknown_job_returns_404(
    client: TestClient,
) -> None:
    """Неизвестное задание возвращает 404."""

    response = client.post(
        f"/jobs/{uuid4()}/retry"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Задание не найдено",
    }