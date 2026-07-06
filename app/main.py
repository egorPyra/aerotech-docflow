"""Точка входа FastAPI-приложения Aerotech Docflow."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response,
    status,
)

from app.repository import (
    IdempotencyConflictError,
    job_repository,
)
from app.schemas import (
    CancelJobResponse,
    JobResponse,
    JobStatus,
    ScanAcceptedResponse,
    ScanRequest,
)
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
    """Выполнить действия при запуске и остановке сервиса."""

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
    version="0.6.0",
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
)
async def start_scan(
    payload: ScanRequest,
    response: Response,
) -> ScanAcceptedResponse:
    """Идемпотентно создать задание на сканирование."""

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
)
async def get_job(
    request_id: UUID,
) -> JobResponse:
    """Получить конкретное задание."""

    job = job_repository.get(request_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    return job


@app.post(
    "/jobs/{request_id}/cancel",
    response_model=CancelJobResponse,
)
async def cancel_job(
    request_id: UUID,
) -> CancelJobResponse:
    """Отменить задание, которое ещё ожидает PDF."""

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