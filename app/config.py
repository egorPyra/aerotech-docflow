"""Конфигурация приложения."""

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """Настройки backend-сервиса."""

    scan_inbox: Path
    archive_root: Path
    database_path: Path

    scan_timeout_seconds: float
    scan_poll_interval_seconds: float
    scan_stable_checks: int

    api_key: str


settings = Settings(
    scan_inbox=Path(
        os.getenv(
            "SCAN_INBOX",
            str(PROJECT_ROOT / "data" / "incoming"),
        )
    ),
    archive_root=Path(
        os.getenv(
            "ARCHIVE_ROOT",
            str(PROJECT_ROOT / "data" / "archive"),
        )
    ),
    database_path=Path(
        os.getenv(
            "DATABASE_PATH",
            str(PROJECT_ROOT / "data" / "aerotech.db"),
        )
    ),
    scan_timeout_seconds=float(
        os.getenv(
            "SCAN_TIMEOUT_SECONDS",
            "120",
        )
    ),
    scan_poll_interval_seconds=float(
        os.getenv(
            "SCAN_POLL_INTERVAL_SECONDS",
            "1",
        )
    ),
    scan_stable_checks=int(
        os.getenv(
            "SCAN_STABLE_CHECKS",
            "3",
        )
    ),
    api_key=os.getenv(
        "API_KEY",
        "",
    ).strip(),
)