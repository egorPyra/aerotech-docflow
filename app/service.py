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

# Сохраняем ссылки на фоновые задачи до их завершения.
_running_tasks: set[asyncio.Task[None]] = set()


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
                stable_checks=settings.scan_stable_checks,
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
                result_file=str(archived_document.path),
                result_filename=archived_document.filename,
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


def start_scan_job(
    request_id: UUID,
    payload: ScanRequest,
) -> None:
    """Запустить обработку в отдельной asyncio-задаче."""

    task = asyncio.create_task(
        process_scan_job(
            request_id=request_id,
            payload=payload,
        )
    )

    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)