"""Точка входа FastAPI-сервиса Aerotech Docflow."""

import logging
from datetime import date as Date
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("aerotech-docflow")


class ScanRequest(BaseModel):
    """Данные, необходимые для запуска обработки документа."""

    planfix_task_id: int = Field(
        gt=0,
        description="Идентификатор задачи Planfix",
    )
    doc_type: str = Field(
        min_length=1,
        max_length=20,
        description="Код типа документа",
        examples=["NKL"],
    )
    number: str = Field(
        min_length=1,
        max_length=100,
        description="Номер документа",
        examples=["001"],
    )
    date: Date = Field(
        description="Дата документа",
        examples=["2026-06-24"],
    )
    counterparty: str | None = Field(
        default=None,
        max_length=255,
        description="Контрагент",
    )


class ScanResponse(BaseModel):
    """Ответ на запрос запуска обработки."""

    status: Literal["ok"]
    planfix_task_id: int
    message: str


app = FastAPI(
    title="Aerotech Docflow",
    description="Backend-сервис обработки и сканирования документов",
    version="0.1.0",
)


@app.get("/health", tags=["Состояние"])
async def health_check() -> dict[str, str]:
    """Проверить, что сервис запущен."""

    return {"status": "ok"}


@app.post("/scan", response_model=ScanResponse, tags=["Сканирование"])
async def start_scan(request: ScanRequest) -> ScanResponse:
    """Принять запрос и запустить обработку документа."""

    logger.info(
        "Получен запрос на обработку: task_id=%s, type=%s, number=%s",
        request.planfix_task_id,
        request.doc_type,
        request.number,
    )

    # В следующих этапах здесь будет вызываться сервис обработки:
    #
    # result = await process_document(request)
    #
    # Пока только подтверждаем получение корректного запроса.

    return ScanResponse(
        status="ok",
        planfix_task_id=request.planfix_task_id,
        message="Запрос принят",
    )