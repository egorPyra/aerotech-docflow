"""Тесты формирования имени и архивирования PDF."""

import hashlib
from datetime import datetime
from pathlib import Path

from app.storage import (
    archive_pdf,
    build_document_filename,
    calculate_control_code,
    calculate_sha256,
    find_available_path,
    sanitize_filename_part,
)


def test_sanitize_filename_part() -> None:
    """Запрещённые Windows-символы заменяются."""

    result = sanitize_filename_part(
        value='  2455/1:*?"  ',
        fallback="NO_NUMBER",
    )

    assert result == "2455-1"


def test_sanitize_empty_filename_part() -> None:
    """Для пустого значения используется fallback."""

    result = sanitize_filename_part(
        value="   ",
        fallback="NO_NUMBER",
    )

    assert result == "NO_NUMBER"


def test_reserved_windows_filename() -> None:
    """Зарезервированное имя Windows получает префикс."""

    result = sanitize_filename_part(
        value="CON",
        fallback="DOC",
    )

    assert result == "_CON"


def test_calculate_control_code() -> None:
    """Контрольный код вычисляется из даты и времени."""

    result = calculate_control_code(
        date_part="20260706",
        time_part="153000",
    )

    assert result == "32"


def test_build_document_filename() -> None:
    """Формируется ожидаемое имя документа."""

    created_at = datetime(
        year=2026,
        month=7,
        day=6,
        hour=15,
        minute=30,
        second=0,
    )

    result = build_document_filename(
        document_type="upd",
        document_number="2455/1",
        user_code="iv",
        created_at=created_at,
    )

    assert result == (
        "UPD_20260706_153000_IV_2455-1_32.pdf"
    )


def test_calculate_sha256(
    tmp_path: Path,
) -> None:
    """SHA-256 файла вычисляется правильно."""

    file_path = tmp_path / "document.pdf"
    file_content = b"%PDF-1.4\nTest document"

    file_path.write_bytes(file_content)

    expected_hash = hashlib.sha256(
        file_content
    ).hexdigest()

    assert calculate_sha256(file_path) == expected_hash


def test_find_available_path(
    tmp_path: Path,
) -> None:
    """Существующий файл не перезаписывается."""

    existing_file = tmp_path / "document.pdf"
    existing_file.write_bytes(b"existing")

    result = find_available_path(
        folder=tmp_path,
        filename="document.pdf",
    )

    assert result == tmp_path / "document_01.pdf"


def test_archive_pdf(
    tmp_path: Path,
) -> None:
    """PDF перемещается в архив."""

    incoming_folder = tmp_path / "incoming"
    archive_folder = tmp_path / "archive"

    incoming_folder.mkdir()

    source_file = incoming_folder / "scan.pdf"
    source_content = b"%PDF-1.4\nTest document"

    source_file.write_bytes(source_content)

    result = archive_pdf(
        source_path=source_file,
        archive_root=archive_folder,
        document_type="UPD",
        document_number="2455/1",
        user_code="IV",
    )

    assert not source_file.exists()
    assert result.path.exists()
    assert result.path.is_file()
    assert result.filename == result.path.name
    assert result.path.parent.parent.parent == (
        archive_folder / "UPD"
    )

    expected_hash = hashlib.sha256(
        source_content
    ).hexdigest()

    assert result.sha256 == expected_hash
    assert result.path.read_bytes() == source_content   