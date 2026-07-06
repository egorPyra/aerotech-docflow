"""Тесты SQLite-репозитория."""

from pathlib import Path

from app.repository import JobRepository
from app.schemas import JobStatus, ScanRequest


def create_payload(
    task_id: int = 52418,
) -> ScanRequest:
    """Создать тестовый запрос."""

    return ScanRequest(
        task_id=task_id,
        document_type="UPD",
        document_number="2455/1",
        user_code="IV",
        context={
            "source": "planfix",
        },
    )


def test_create_and_get_job(
    repository: JobRepository,
) -> None:
    """Задание сохраняется и читается из SQLite."""

    created_job = repository.create(
        create_payload()
    )

    loaded_job = repository.get(
        created_job.request_id
    )

    assert loaded_job is not None
    assert loaded_job.request_id == created_job.request_id
    assert loaded_job.task_id == 52418
    assert loaded_job.document_type == "UPD"
    assert loaded_job.status == JobStatus.ACCEPTED
    assert loaded_job.context == {
        "source": "planfix",
    }


def test_job_survives_repository_restart(
    tmp_path: Path,
) -> None:
    """Новое подключение видит ранее сохранённое задание."""

    database_path = tmp_path / "persistent.db"

    first_repository = JobRepository(
        database_path=database_path,
    )

    created_job = first_repository.create(
        create_payload()
    )

    second_repository = JobRepository(
        database_path=database_path,
    )

    loaded_job = second_repository.get(
        created_job.request_id
    )

    assert loaded_job is not None
    assert loaded_job.request_id == created_job.request_id
    assert loaded_job.task_id == created_job.task_id


def test_update_status(
    repository: JobRepository,
) -> None:
    """Статус задания изменяется."""

    job = repository.create(
        create_payload()
    )

    updated_job = repository.update_status(
        request_id=job.request_id,
        status=JobStatus.WAITING_FOR_FILE,
    )

    assert updated_job is not None
    assert updated_job.status == JobStatus.WAITING_FOR_FILE
    assert updated_job.error is None
    assert updated_job.updated_at >= job.updated_at


def test_set_source_file(
    repository: JobRepository,
) -> None:
    """Исходный путь PDF сохраняется."""

    job = repository.create(
        create_payload()
    )

    updated_job = repository.set_source_file(
        request_id=job.request_id,
        source_file=r"D:\scan\document.pdf",
    )

    assert updated_job is not None
    assert updated_job.source_file == (
        r"D:\scan\document.pdf"
    )


def test_set_archive_result(
    repository: JobRepository,
) -> None:
    """Результат архивирования сохраняется."""

    job = repository.create(
        create_payload()
    )

    updated_job = repository.set_archive_result(
        request_id=job.request_id,
        result_file=r"D:\archive\document.pdf",
        result_filename="document.pdf",
        sha256="a" * 64,
    )

    assert updated_job is not None
    assert updated_job.result_file == (
        r"D:\archive\document.pdf"
    )
    assert updated_job.result_filename == "document.pdf"
    assert updated_job.sha256 == "a" * 64


def test_list_jobs_returns_newest_first(
    repository: JobRepository,
) -> None:
    """История сортируется от новых заданий к старым."""

    repository.create(
        create_payload(task_id=100)
    )

    repository.create(
        create_payload(task_id=200)
    )

    jobs = repository.list()

    assert len(jobs) == 2
    assert jobs[0].task_id == 200
    assert jobs[1].task_id == 100


def test_interrupted_jobs_are_marked_failed(
    repository: JobRepository,
) -> None:
    """Незавершённые задания помечаются как failed."""

    job = repository.create(
        create_payload()
    )

    repository.update_status(
        request_id=job.request_id,
        status=JobStatus.WAITING_FOR_FILE,
    )

    changed_count = (
        repository.mark_interrupted_jobs_failed()
    )

    loaded_job = repository.get(
        job.request_id
    )

    assert changed_count == 1
    assert loaded_job is not None
    assert loaded_job.status == JobStatus.FAILED
    assert loaded_job.error == (
        "Обработка была прервана "
        "перезапуском backend-сервиса"
    )


def test_done_job_is_not_marked_failed(
    repository: JobRepository,
) -> None:
    """Завершённое задание не меняется после перезапуска."""

    job = repository.create(
        create_payload()
    )

    repository.update_status(
        request_id=job.request_id,
        status=JobStatus.DONE,
    )

    changed_count = (
        repository.mark_interrupted_jobs_failed()
    )

    loaded_job = repository.get(
        job.request_id
    )

    assert changed_count == 0
    assert loaded_job is not None
    assert loaded_job.status == JobStatus.DONE