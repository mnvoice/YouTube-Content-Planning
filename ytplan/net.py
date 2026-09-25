"""파일 캐시가 붙은 HTTP 도우미.

YouTube Data API는 하루 할당량(기본 10,000 유닛, 검색 1회 100 유닛)이 있고
네이버 데이터랩은 하루 1,000회 제한이 있다. 같은 요청을 반복하지 않도록
응답을 .cache/ 폴더에 저장해 두고 유효기간(기본 24시간) 동안 재사용한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

USER_AGENT = "ytplan/0.1 (+https://github.com/mnvoice/YouTube-Content-Planning)"
DEFAULT_TTL = 24 * 3600
# 캐시 키에서 제외할 파라미터 (API 키가 바뀌어도 같은 요청으로 취급)
_SECRET_PARAMS = {"key"}


def _cache_dir() -> Path:
    return Path(os.environ.get("YTPLAN_CACHE", ".cache"))


def _cache_path(method: str, url: str, params: dict | None, body: Any) -> Path:
    public = {k: v for k, v in (params or {}).items() if k not in _SECRET_PARAMS}
    raw = json.dumps([method, url, public, body], sort_keys=True, ensure_ascii=False)
    return _cache_dir() / (hashlib.sha256(raw.encode()).hexdigest()[:32] + ".json")


def _read_cache(path: Path, ttl: int) -> str | None:
    if ttl <= 0 or not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl:
        return None
    return path.read_text(encoding="utf-8")


def _write_cache(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    body: Any = None,
    ttl: int = DEFAULT_TTL,
) -> str:
    path = _cache_path(method, url, params, body)
    cached = _read_cache(path, ttl)
    if cached is not None:
        return cached
    resp = requests.request(
        method,
        url,
        params=params,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
        json=body,
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {url} 실패 ({resp.status_code}): {resp.text[:300]}")
    resp.encoding = resp.encoding or "utf-8"
    text = resp.text
    if ttl > 0:
        _write_cache(path, text)
    return text


def get_json(url: str, params: dict | None = None, headers: dict | None = None, ttl: int = DEFAULT_TTL) -> Any:
    return json.loads(_request("GET", url, params=params, headers=headers, ttl=ttl))


def post_json(url: str, body: Any, headers: dict | None = None, ttl: int = DEFAULT_TTL) -> Any:
    return json.loads(_request("POST", url, headers=headers, body=body, ttl=ttl))


def get_text(url: str, params: dict | None = None, headers: dict | None = None, ttl: int = DEFAULT_TTL) -> str:
    return _request("GET", url, params=params, headers=headers, ttl=ttl)
