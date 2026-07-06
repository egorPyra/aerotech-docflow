"""Точка входа FastAPI-приложения Aerotech Docflow."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    status,
)

from app.repository import (
    IdempotencyConflictError,
    RetryNotAllowedError,
    job_repository,
)
from app.schemas import (
    CancelJobResponse,
    JobResponse,
    JobStatus,
    RetryJobResponse,
    ScanAcceptedResponse,
    ScanRequest,
)
from app.security import require_api_key
from app.service import (
    cancel_scan_job,
    start_scan_job,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    """Действия при запуске и остановке сервиса."""

    interrupted_jobs = (
        job_repository.mark_interrupted_jobs_failed()
    )

    if interrupted_jobs > 0:
        logger.warning(
            "После перезапуска помечено как failed "
            "прерванных заданий: %s",
            interrupted_jobs,
        )

    logger.info("Aerotech Docflow запущен")

    yield

    logger.info("Aerotech Docflow остановлен")


app = FastAPI(
    title="Aerotech Docflow",
    description="Backend-сервис обработки документов",
    version="0.8.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    """Вернуть информацию о сервисе."""

    return {
        "service": "aerotech-docflow",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "jobs": "/jobs",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Проверить доступность сервиса."""

    return {
        "status": "ok",
    }


@app.post(
    "/scan",
    response_model=ScanAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(require_api_key),
    ],
)
async def start_scan(
    payload: ScanRequest,
    response: Response,
) -> ScanAcceptedResponse:
    """Идемпотентно создать задание."""

    try:
        creation_result = (
            job_repository.create_or_get(payload)
        )

    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    job = creation_result.job

    if creation_result.created:
        start_scan_job(
            request_id=job.request_id,
            payload=payload,
        )

        logger.info(
            "Создано задание: "
            "request_id=%s "
            "external_request_id=%s "
            "task_id=%s",
            job.request_id,
            payload.external_request_id,
            job.task_id,
        )

        response.status_code = (
            status.HTTP_202_ACCEPTED
        )

        response_status = "accepted"

    else:
        logger.info(
            "Получен повторный запрос: "
            "request_id=%s "
            "external_request_id=%s",
            job.request_id,
            payload.external_request_id,
        )

        response.status_code = status.HTTP_200_OK
        response_status = "existing"

    return ScanAcceptedResponse(
        status=response_status,
        created=creation_result.created,
        request_id=job.request_id,
        job_status=job.status,
        status_url=f"/jobs/{job.request_id}",
    )


@app.get(
    "/jobs",
    response_model=list[JobResponse],
    dependencies=[
        Depends(require_api_key),
    ],
)
async def list_jobs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> list[JobResponse]:
    """Получить историю заданий."""

    return job_repository.list(
        limit=limit,
        offset=offset,
    )


@app.get(
    "/jobs/{request_id}",
    response_model=JobResponse,
    dependencies=[
        Depends(require_api_key),
    ],
)
async def get_job(
    request_id: UUID,
) -> JobResponse:
    """Получить конкретное задание."""

    job = job_repository.get(
        request_id
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    return job


@app.post(
    "/jobs/{request_id}/cancel",
    response_model=CancelJobResponse,
    dependencies=[
        Depends(require_api_key),
    ],
)
async def cancel_job(
    request_id: UUID,
) -> CancelJobResponse:
    """Отменить задание, ожидающее PDF."""

    job = job_repository.get(
        request_id
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    cancellable_statuses = {
        JobStatus.ACCEPTED,
        JobStatus.WAITING_FOR_FILE,
    }

    if job.status not in cancellable_statuses:
        if job.status == JobStatus.CANCELLED:
            detail = "Задание уже отменено"

        elif job.status == JobStatus.DONE:
            detail = (
                "Завершённое задание нельзя отменить"
            )

        elif job.status == JobStatus.FAILED:
            detail = (
                "Неудачное задание нельзя отменить"
            )

        else:
            detail = (
                "PDF уже получен. "
                "Задание нельзя безопасно отменить"
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    was_cancelled = await cancel_scan_job(
        request_id
    )

    if not was_cancelled:
        refreshed_job = job_repository.get(
            request_id
        )

        if (
            refreshed_job is not None
            and refreshed_job.status
            not in cancellable_statuses
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Задание уже перешло "
                    "в другое состояние"
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Фоновая задача не найдена "
                "или уже завершена"
            ),
        )

    updated_job = job_repository.update_status(
        request_id=request_id,
        status=JobStatus.CANCELLED,
        error=None,
    )

    if updated_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    logger.info(
        "Задание отменено: request_id=%s",
        request_id,
    )

    return CancelJobResponse(
        status="cancelled",
        request_id=request_id,
        job_status=updated_job.status,
        message="Задание успешно отменено",
    )


@app.post(
    "/jobs/{request_id}/retry",
    response_model=RetryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(require_api_key),
    ],
)
async def retry_job(
    request_id: UUID,
) -> RetryJobResponse:
    """Повторно запустить failed или cancelled задание."""

    try:
        updated_job = (
            job_repository.prepare_retry(
                request_id
            )
        )

    except RetryNotAllowedError as error:
        current_status = error.current_status

        if current_status == JobStatus.DONE:
            detail = (
                "Завершённое задание "
                "нельзя повторно запустить"
            )

        elif current_status in {
            JobStatus.ACCEPTED,
            JobStatus.WAITING_FOR_FILE,
            JobStatus.FILE_RECEIVED,
            JobStatus.ARCHIVING,
        }:
            detail = (
                "Задание уже активно "
                "или находится в процессе обработки"
            )

        else:
            detail = (
                "Задание нельзя повторно запустить "
                f"из статуса {current_status.value}"
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from error

    if updated_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    payload = ScanRequest(
        external_request_id=(
            updated_job.external_request_id
            or f"legacy-retry-{updated_job.request_id}"
        ),
        task_id=updated_job.task_id,
        document_type=updated_job.document_type,
        document_number=updated_job.document_number,
        user_code=updated_job.user_code,
        context=updated_job.context,
    )

    try:
        start_scan_job(
            request_id=updated_job.request_id,
            payload=payload,
        )

    except Exception as error:
        job_repository.update_status(
            request_id=updated_job.request_id,
            status=JobStatus.FAILED,
            error=(
                "Не удалось повторно запустить "
                f"фоновую задачу: {error}"
            ),
        )

        logger.exception(
            "Ошибка повторного запуска: "
            "request_id=%s",
            updated_job.request_id,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Не удалось повторно запустить задание"
            ),
        ) from error

    logger.info(
        "Задание повторно запущено: "
        "request_id=%s attempt_count=%s",
        updated_job.request_id,
        updated_job.attempt_count,
    )

    return RetryJobResponse(
        status="accepted",
        request_id=updated_job.request_id,
        job_status=updated_job.status,
        attempt_count=updated_job.attempt_count,
        message="Задание повторно запущено",
    )