"""Тесты отмены заданий."""

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
    """Создать тело тестового POST /scan."""

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


def test_cancel_accepted_job(
    client: TestClient,
    repository: JobRepository,
    cancelled_jobs: list[UUID],
) -> None:
    """Задание в статусе accepted можно отменить."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "cancel-accepted-request"
        ),
    )

    assert create_response.status_code == 202

    request_id_text = (
        create_response.json()["request_id"]
    )

    response = client.post(
        f"/jobs/{request_id_text}/cancel"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "cancelled",
        "request_id": request_id_text,
        "job_status": "cancelled",
        "message": "Задание успешно отменено",
    }

    request_id = UUID(
        request_id_text
    )

    assert cancelled_jobs == [
        request_id
    ]

    saved_job = repository.get(
        request_id
    )

    assert saved_job is not None
    assert saved_job.status == JobStatus.CANCELLED


def test_cancel_waiting_for_file_job(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """Задание, ожидающее PDF, можно отменить."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "cancel-waiting-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.WAITING_FOR_FILE,
    )

    response = client.post(
        f"/jobs/{request_id}/cancel"
    )

    assert response.status_code == 200

    saved_job = repository.get(
        request_id
    )

    assert saved_job is not None
    assert saved_job.status == JobStatus.CANCELLED


def test_cancel_unknown_job_returns_404(
    client: TestClient,
) -> None:
    """Неизвестное задание нельзя отменить."""

    response = client.post(
        f"/jobs/{uuid4()}/cancel"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Задание не найдено",
    }


def test_cancel_done_job_returns_409(
    client: TestClient,
    repository: JobRepository,
    cancelled_jobs: list[UUID],
) -> None:
    """Завершённое задание нельзя отменить."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "cancel-done-request"
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
        f"/jobs/{request_id}/cancel"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Завершённое задание нельзя отменить"
        )
    }

    assert cancelled_jobs == []


def test_cancel_failed_job_returns_409(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """Неудачное задание нельзя отменить."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "cancel-failed-request"
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
        f"/jobs/{request_id}/cancel"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Неудачное задание нельзя отменить"
        )
    }


def test_cancel_already_cancelled_job_returns_409(
    client: TestClient,
) -> None:
    """Повторная отмена возвращает конфликт."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "already-cancelled-request"
        ),
    )

    request_id = (
        create_response.json()["request_id"]
    )

    first_response = client.post(
        f"/jobs/{request_id}/cancel"
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/jobs/{request_id}/cancel"
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Задание уже отменено",
    }


def test_file_received_job_cannot_be_cancelled(
    client: TestClient,
    repository: JobRepository,
) -> None:
    """После получения PDF отмена запрещена."""

    create_response = client.post(
        "/scan",
        json=create_request(
            "file-received-request"
        ),
    )

    request_id = UUID(
        create_response.json()["request_id"]
    )

    repository.update_status(
        request_id=request_id,
        status=JobStatus.FILE_RECEIVED,
    )

    response = client.post(
        f"/jobs/{request_id}/cancel"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "PDF уже получен. "
            "Задание нельзя безопасно отменить"
        )
    }


def test_cancelled_job_is_not_marked_failed(
    repository: JobRepository,
) -> None:
    """Отменённое задание не меняется после перезапуска."""

    payload = ScanRequest(
        external_request_id=(
            "cancelled-restart-request"
        ),
        task_id=52418,
        document_type="UPD",
        document_number="2455/1",
        user_code="IV",
        context={
            "source": "planfix",
        },
    )

    job = repository.create(
        payload
    )

    repository.update_status(
        request_id=job.request_id,
        status=JobStatus.CANCELLED,
    )

    changed_count = (
        repository.mark_interrupted_jobs_failed()
    )

    loaded_job = repository.get(
        job.request_id
    )

    assert changed_count == 0
    assert loaded_job is not None
    assert loaded_job.status == JobStatus.CANCELLED