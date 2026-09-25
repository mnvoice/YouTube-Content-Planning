"""아이템별 조사 결과(research/<id>.json)를 모으고 저장한다.

키가 있는 소스만 실행한다. 키가 없어도 뉴스 조사와 수동 점수만으로 순위를 낼 수 있다.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Callable

from .sources import naver, news, youtube
from .topics import Topic


def research_dir() -> Path:
    return Path(os.environ.get("YTPLAN_RESEARCH", "research"))


def load(topic_id: str) -> dict:
    path = research_dir() / f"{topic_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_all(topics: list[Topic]) -> dict[str, dict]:
    return {t.id: load(t.id) for t in topics}


def load_benchmark() -> dict:
    path = research_dir() / "benchmark.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_benchmark(data: dict) -> Path:
    path = research_dir() / "benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save(topic_id: str, data: dict) -> Path:
    path = research_dir() / f"{topic_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run(
    topics: list[Topic],
    *,
    youtube_key: str | None,
    naver_id: str | None,
    naver_secret: str | None,
    days: int = 365,
    comment_videos: int = 3,
    use_news: bool = True,
    log: Callable[[str], None] = print,
) -> dict[str, dict]:
    results = {t.id: load(t.id) for t in topics}

    if naver_id and naver_secret:
        log(f"[네이버 데이터랩] 40~50대 검색량 비교: {len(topics)}개 아이템")
        try:
            trend = naver.compare_topics(naver_id, naver_secret, {t.id: list(t.keywords) for t in topics})
            for tid, value in trend.items():
                results[tid]["naver"] = value
        except (RuntimeError, OSError) as e:
            log(f"  ! 네이버 조회 실패: {e}")
    else:
        log("[네이버 데이터랩] NAVER_CLIENT_ID/SECRET 없음 → 건너뜀")

    if not youtube_key:
        log("[YouTube] YOUTUBE_API_KEY 없음 → 건너뜀")

    for t in topics:
        data = results[t.id]
        if youtube_key:
            log(f"[YouTube] {t.id} '{t.main_keyword}' 인기 영상·아웃라이어 분석")
            try:
                yt = youtube.analyze(youtube_key, t.main_keyword, days=days)
                voices: list[dict] = []
                for v in yt["videos"][:comment_videos]:
                    for c in youtube.pick_voice_comments(youtube.fetch_comments(youtube_key, v["id"]), limit=10):
                        voices.append({**c, "video_title": v["title"]})
                voices.sort(key=lambda c: c["weight"], reverse=True)
                yt["voice_comments"] = voices[:20]
                data["youtube"] = yt
            except (RuntimeError, OSError) as e:
                log(f"  ! YouTube 조회 실패: {e}")
        if use_news:
            try:
                data["news"] = news.recent_news(t.main_keyword)
            except (RuntimeError, OSError, ValueError, ET.ParseError) as e:
                log(f"  ! 뉴스 조회 실패({t.id}): {e}")
        save(t.id, data)
    return results
