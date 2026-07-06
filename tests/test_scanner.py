"""Тесты наблюдения за папкой сканера."""

import asyncio
from pathlib import Path

import pytest

from app.scanner import (
    ScannerTimeoutError,
    wait_for_new_pdf,
)


def test_wait_for_new_pdf(
    tmp_path: Path,
) -> None:
    """Сервис замечает PDF, появившийся после запуска ожидания."""

    async def scenario() -> Path:
        wait_task = asyncio.create_task(
            wait_for_new_pdf(
                folder=tmp_path,
                timeout_seconds=1,
                poll_interval_seconds=0.01,
                stable_checks=2,
            )
        )

        await asyncio.sleep(0.05)

        pdf_path = tmp_path / "scan.pdf"

        pdf_path.write_bytes(
            b"%PDF-1.4\nTest document"
        )

        return await wait_task

    result = asyncio.run(
        scenario()
    )

    assert result == (
        tmp_path / "scan.pdf"
    ).resolve()


def test_existing_pdf_is_ignored(
    tmp_path: Path,
) -> None:
    """PDF, существовавший до начала задания, игнорируется."""

    existing_pdf = tmp_path / "old.pdf"

    existing_pdf.write_bytes(
        b"%PDF-1.4\nOld document"
    )

    async def scenario() -> None:
        with pytest.raises(ScannerTimeoutError):
            await wait_for_new_pdf(
                folder=tmp_path,
                timeout_seconds=0.1,
                poll_interval_seconds=0.01,
                stable_checks=2,
            )

    asyncio.run(
        scenario()
    )


def test_invalid_pdf_is_ignored(
    tmp_path: Path,
) -> None:
    """Файл с расширением PDF без PDF-заголовка не принимается."""

    async def scenario() -> None:
        wait_task = asyncio.create_task(
            wait_for_new_pdf(
                folder=tmp_path,
                timeout_seconds=0.15,
                poll_interval_seconds=0.01,
                stable_checks=2,
            )
        )

        await asyncio.sleep(0.03)

        invalid_pdf = tmp_path / "fake.pdf"
        invalid_pdf.write_text(
            "Это не настоящий PDF",
            encoding="utf-8",
        )

        with pytest.raises(ScannerTimeoutError):
            await wait_task

    asyncio.run(
        scenario()
    )


def test_wait_for_new_pdf_timeout(
    tmp_path: Path,
) -> None:
    """Если файл не появился, возникает таймаут."""

    async def scenario() -> None:
        with pytest.raises(ScannerTimeoutError):
            await wait_for_new_pdf(
                folder=tmp_path,
                timeout_seconds=0.05,
                poll_interval_seconds=0.01,
                stable_checks=2,
            )

    asyncio.run(
        scenario()
    )