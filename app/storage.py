"""Сохранение PDF в архиве."""

import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class StorageError(RuntimeError):
    """Ошибка сохранения документа."""


@dataclass(frozen=True)
class ArchivedDocument:
    """Результат сохранения документа в архив."""

    path: Path
    filename: str
    sha256: str


_INVALID_FILENAME_CHARS = re.compile(
    r'[<>:"/\\|?*\x00-\x1f]'
)

_MULTIPLE_SPACES = re.compile(r"\s+")

_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def sanitize_filename_part(
    value: str,
    fallback: str,
    max_length: int = 80,
) -> str:
    """Подготовить часть имени файла для Windows."""

    cleaned = value.strip()

    cleaned = _INVALID_FILENAME_CHARS.sub(
        "-",
        cleaned,
    )

    cleaned = _MULTIPLE_SPACES.sub(
        "_",
        cleaned,
    )

    cleaned = cleaned.strip(" ._-")

    if not cleaned:
        cleaned = fallback

    if cleaned.upper() in _RESERVED_WINDOWS_NAMES:
        cleaned = f"_{cleaned}"

    return cleaned[:max_length]


def calculate_control_code(
    date_part: str,
    time_part: str,
) -> str:
    """
    Вычислить короткий контрольный код.

    Складываются все цифры даты и времени.
    Из результата берутся первая и последняя цифры.
    """

    digits = date_part + time_part

    total = sum(
        int(character)
        for character in digits
        if character.isdigit()
    )

    total_text = str(total)

    if len(total_text) == 1:
        return total_text * 2

    return (
        total_text[0]
        + total_text[-1]
    )


def build_document_filename(
    document_type: str,
    document_number: str,
    user_code: str,
    created_at: datetime,
) -> str:
    """Сформировать итоговое имя PDF."""

    safe_document_type = sanitize_filename_part(
        document_type,
        fallback="DOC",
    ).upper()

    safe_document_number = sanitize_filename_part(
        document_number,
        fallback="NO_NUMBER",
    )

    safe_user_code = sanitize_filename_part(
        user_code,
        fallback="SYSTEM",
    ).upper()

    date_part = created_at.strftime("%Y%m%d")
    time_part = created_at.strftime("%H%M%S")

    control_code = calculate_control_code(
        date_part=date_part,
        time_part=time_part,
    )

    return (
        f"{safe_document_type}_"
        f"{date_part}_"
        f"{time_part}_"
        f"{safe_user_code}_"
        f"{safe_document_number}_"
        f"{control_code}.pdf"
    )


def calculate_sha256(file_path: Path) -> str:
    """Вычислить SHA-256 файла."""

    digest = hashlib.sha256()

    try:
        with file_path.open("rb") as source_file:
            while chunk := source_file.read(1024 * 1024):
                digest.update(chunk)

    except OSError as error:
        raise StorageError(
            f"Не удалось прочитать файл для вычисления SHA-256: "
            f"{file_path}"
        ) from error

    return digest.hexdigest()


def find_available_path(
    folder: Path,
    filename: str,
) -> Path:
    """Найти имя, которое ещё не занято."""

    candidate = folder / filename

    if not candidate.exists():
        return candidate

    original_path = Path(filename)
    stem = original_path.stem
    suffix = original_path.suffix

    counter = 1

    while True:
        candidate = folder / (
            f"{stem}_{counter:02d}{suffix}"
        )

        if not candidate.exists():
            return candidate

        counter += 1


def move_file_safely(
    source_path: Path,
    target_path: Path,
) -> None:
    """
    Переместить файл без перезаписи существующего документа.

    Если исходная и целевая папки находятся на разных дисках,
    сначала выполняется копирование во временный файл.
    """

    if target_path.exists():
        raise StorageError(
            f"Целевой файл уже существует: {target_path}"
        )

    try:
        source_path.rename(target_path)
        return

    except OSError:
        temporary_path = target_path.with_name(
            f"{target_path.name}.part"
        )

    try:
        if temporary_path.exists():
            temporary_path.unlink()

        shutil.copy2(
            source_path,
            temporary_path,
        )

        temporary_path.rename(target_path)
        source_path.unlink()

    except OSError as error:
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass

        raise StorageError(
            f"Не удалось переместить файл "
            f"{source_path} в {target_path}"
        ) from error


def archive_pdf(
    source_path: Path,
    archive_root: Path,
    document_type: str,
    document_number: str,
    user_code: str,
) -> ArchivedDocument:
    """Переместить PDF в архив и вернуть результат."""

    source_path = source_path.resolve()

    if not source_path.exists():
        raise StorageError(
            f"Исходный файл не найден: {source_path}"
        )

    if not source_path.is_file():
        raise StorageError(
            f"Указанный путь не является файлом: {source_path}"
        )

    if source_path.suffix.lower() != ".pdf":
        raise StorageError(
            f"Ожидался PDF-файл: {source_path}"
        )

    created_at = datetime.now().astimezone()

    safe_document_type = sanitize_filename_part(
        document_type,
        fallback="DOC",
    ).upper()

    archive_folder = (
        archive_root
        / safe_document_type
        / created_at.strftime("%Y")
        / created_at.strftime("%m")
    )

    try:
        archive_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    except OSError as error:
        raise StorageError(
            f"Не удалось создать папку архива: "
            f"{archive_folder}"
        ) from error

    filename = build_document_filename(
        document_type=document_type,
        document_number=document_number,
        user_code=user_code,
        created_at=created_at,
    )

    target_path = find_available_path(
        folder=archive_folder,
        filename=filename,
    )

    sha256 = calculate_sha256(source_path)

    move_file_safely(
        source_path=source_path,
        target_path=target_path,
    )

    return ArchivedDocument(
        path=target_path.resolve(),
        filename=target_path.name,
        sha256=sha256,
    )