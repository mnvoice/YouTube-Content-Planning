"""API 키 등 설정. 프로젝트 루트의 .env 파일을 읽어 환경변수로 등록한다."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """KEY=VALUE 형식의 .env 파일을 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None
