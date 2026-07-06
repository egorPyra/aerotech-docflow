"""Точка входа FastAPI-приложения Aerotech Docflow."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    status,
)

from app.repository import job_repository
from app.schemas import (
    JobResponse,
    ScanAcceptedResponse,
    ScanRequest,
)
from app.service import start_scan_job


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

    logger.info(
        "Aerotech Docflow запущен"
    )

    yield

    logger.info(
        "Aerotech Docflow остановлен"
    )


app = FastAPI(
    title="Aerotech Docflow",
    description="Backend-сервис обработки документов",
    version="0.4.0",
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
) -> ScanAcceptedResponse:
    """Создать задание и начать ожидание PDF."""

    job = job_repository.create(payload)

    start_scan_job(
        request_id=job.request_id,
        payload=payload,
    )

    logger.info(
        "Создано задание: request_id=%s task_id=%s",
        job.request_id,
        job.task_id,
    )

    return ScanAcceptedResponse(
        status="accepted",
        request_id=job.request_id,
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