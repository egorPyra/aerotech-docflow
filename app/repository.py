"""Временное хранилище заданий в памяти приложения."""

from datetime import datetime, timezone
from threading import RLock
from uuid import UUID, uuid4

from app.schemas import JobResponse, JobStatus, ScanRequest


class JobRepository:
    """Управляет заданиями на обработку документов."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, JobResponse] = {}
        self._lock = RLock()

    def create(self, payload: ScanRequest) -> JobResponse:
        """Создать новое задание."""

        now = datetime.now(timezone.utc)

        job = JobResponse(
            request_id=uuid4(),
            task_id=payload.task_id,
            document_type=payload.document_type,
            document_number=payload.document_number,
            user_code=payload.user_code,
            context=payload.context,
            status=JobStatus.ACCEPTED,
            created_at=now,
            updated_at=now,
            source_file=None,
            result_file=None,
            result_filename=None,
            sha256=None,
            error=None,
        )

        with self._lock:
            self._jobs[job.request_id] = job

        return job.model_copy(deep=True)

    def get(self, request_id: UUID) -> JobResponse | None:
        """Получить задание по request_id."""

        with self._lock:
            job = self._jobs.get(request_id)

            if job is None:
                return None

            return job.model_copy(deep=True)

    def update_status(
        self,
        request_id: UUID,
        status: JobStatus,
        error: str | None = None,
    ) -> JobResponse | None:
        """Изменить статус задания."""

        with self._lock:
            current_job = self._jobs.get(request_id)

            if current_job is None:
                return None

            updated_job = current_job.model_copy(
                update={
                    "status": status,
                    "error": error,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

            self._jobs[request_id] = updated_job

            return updated_job.model_copy(deep=True)

    def set_source_file(
        self,
        request_id: UUID,
        source_file: str,
    ) -> JobResponse | None:
        """Записать путь к PDF из папки сканера."""

        with self._lock:
            current_job = self._jobs.get(request_id)

            if current_job is None:
                return None

            updated_job = current_job.model_copy(
                update={
                    "source_file": source_file,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

            self._jobs[request_id] = updated_job

            return updated_job.model_copy(deep=True)

    def set_archive_result(
        self,
        request_id: UUID,
        result_file: str,
        result_filename: str,
        sha256: str,
    ) -> JobResponse | None:
        """Записать результат архивирования документа."""

        with self._lock:
            current_job = self._jobs.get(request_id)

            if current_job is None:
                return None

            updated_job = current_job.model_copy(
                update={
                    "result_file": result_file,
                    "result_filename": result_filename,
                    "sha256": sha256,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

            self._jobs[request_id] = updated_job

            return updated_job.model_copy(deep=True)


job_repository = JobRepository()