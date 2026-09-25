"""API 키 등 설정. 프로젝트 루트의 .env 파일을 읽어 환경변수로 등록한다."""

from __future__ import annotations

import os
from pathlib import Path


def parse_env(text: str) -> dict[str, str]:
    """KEY=VALUE 줄을 읽는다. 빈 줄과 # 주석은 건너뛴다."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_env(path: str | Path = ".env") -> dict[str, str]:
    path = Path(path)
    # utf-8-sig: 윈도우 메모장이 붙이는 BOM이 있어도 첫 키 이름이 깨지지 않게
    return parse_env(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


# .env에서 읽어 등록한 이름. 여기 없는데 환경변수에 값이 있으면 터미널에서 직접 설정한 값이다.
loaded_from_file: set[str] = set()


def load_dotenv(path: str | Path = ".env") -> None:
    """.env 값을 환경변수로 등록한다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    for key, value in read_env(path).items():
        if key not in os.environ:
            os.environ[key] = value
            loaded_from_file.add(key)


def get(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None
