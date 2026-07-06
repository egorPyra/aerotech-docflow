"""Бизнес-логика обработки заданий на сканирование."""

import asyncio
import logging
from uuid import UUID

from app.config import settings
from app.repository import job_repository
from app.scanner import (
    ScannerTimeoutError,
    wait_for_new_pdf,
)
from app.schemas import JobStatus, ScanRequest
from app.storage import StorageError, archive_pdf


logger = logging.getLogger(__name__)


# Один физический сканер обслуживает одно задание за раз.
_scanner_lock = asyncio.Lock()

# request_id → работающая фоновая задача.
_running_tasks: dict[
    UUID,
    asyncio.Task[None],
] = {}


async def process_scan_job(
    request_id: UUID,
    payload: ScanRequest,
) -> None:
    """Получить PDF и сохранить его в архиве."""

    try:
        logger.info(
            "Задание ожидает освобождения сканера: "
            "request_id=%s task_id=%s",
            request_id,
            payload.task_id,
        )

        async with _scanner_lock:
            job_repository.update_status(
                request_id=request_id,
                status=JobStatus.WAITING_FOR_FILE,
            )

            logger.info(
                "Ожидание PDF: "
                "request_id=%s task_id=%s folder=%s",
                request_id,
                payload.task_id,
                settings.scan_inbox,
            )

            pdf_path = await wait_for_new_pdf(
                folder=settings.scan_inbox,
                timeout_seconds=(
                    settings.scan_timeout_seconds
                ),
                poll_interval_seconds=(
                    settings.scan_poll_interval_seconds
                ),
                stable_checks=(
                    settings.scan_stable_checks
                ),
            )

            job_repository.set_source_file(
                request_id=request_id,
                source_file=str(pdf_path),
            )

            job_repository.update_status(
                request_id=request_id,
                status=JobStatus.FILE_RECEIVED,
            )

            logger.info(
                "PDF получен: request_id=%s file=%s",
                request_id,
                pdf_path,
            )

            job_repository.update_status(
                request_id=request_id,
                status=JobStatus.ARCHIVING,
            )

            archived_document = await asyncio.to_thread(
                archive_pdf,
                pdf_path,
                settings.archive_root,
                payload.document_type,
                payload.document_number,
                payload.user_code,
            )

            job_repository.set_archive_result(
                request_id=request_id,
                result_file=str(
                    archived_document.path
                ),
                result_filename=(
                    archived_document.filename
                ),
                sha256=archived_document.sha256,
            )

            job_repository.update_status(
                request_id=request_id,
                status=JobStatus.DONE,
            )

            logger.info(
                "Документ сохранён: "
                "request_id=%s file=%s sha256=%s",
                request_id,
                archived_document.path,
                archived_document.sha256,
            )

    except asyncio.CancelledError:
        logger.info(
            "Фоновая обработка отменена: "
            "request_id=%s",
            request_id,
        )

        # Статус cancelled устанавливает HTTP endpoint.
        raise

    except ScannerTimeoutError as error:
        logger.warning(
            "Истёк таймаут ожидания PDF: "
            "request_id=%s",
            request_id,
        )

        job_repository.update_status(
            request_id=request_id,
            status=JobStatus.FAILED,
            error=str(error),
        )

    except StorageError as error:
        logger.exception(
            "Ошибка сохранения документа: "
            "request_id=%s",
            request_id,
        )

        job_repository.update_status(
            request_id=request_id,
            status=JobStatus.FAILED,
            error=str(error),
        )

    except Exception as error:
        logger.exception(
            "Неожиданная ошибка обработки: "
            "request_id=%s",
            request_id,
        )

        job_repository.update_status(
            request_id=request_id,
            status=JobStatus.FAILED,
            error=str(error),
        )


def _remove_finished_task(
    request_id: UUID,
    completed_task: asyncio.Task[None],
) -> None:
    """Удалить завершившуюся задачу из реестра."""

    current_task = _running_tasks.get(
        request_id
    )

    if current_task is completed_task:
        _running_tasks.pop(
            request_id,
            None,
        )


def start_scan_job(
    request_id: UUID,
    payload: ScanRequest,
) -> None:
    """Запустить обработку в отдельной asyncio-задаче."""

    existing_task = _running_tasks.get(
        request_id
    )

    if (
        existing_task is not None
        and not existing_task.done()
    ):
        raise RuntimeError(
            "Задание уже запущено: "
            f"{request_id}"
        )

    task = asyncio.create_task(
        process_scan_job(
            request_id=request_id,
            payload=payload,
        )
    )

    _running_tasks[request_id] = task

    task.add_done_callback(
        lambda completed_task: _remove_finished_task(
            request_id=request_id,
            completed_task=completed_task,
        )
    )


async def cancel_scan_job(
    request_id: UUID,
) -> bool:
    """
    Отменить работающую фоновую задачу.

    Возвращает True, если задача была найдена и отменена.
    """

    task = _running_tasks.get(
        request_id
    )

    if task is None:
        return False

    if task.done():
        _running_tasks.pop(
            request_id,
            None,
        )
        return False

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    return True