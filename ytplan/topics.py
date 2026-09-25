"""아이템 뱅크(topic_bank.csv) 로딩.

CSV는 엑셀/구글시트에서 바로 열어 행을 추가·수정할 수 있도록 설계했다.
여러 값이 들어가는 칸(sources, keywords, season)은 세미콜론(;)으로 구분한다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BANK = Path(__file__).parent / "data" / "topic_bank.csv"
RISK_LEVELS = ("low", "med", "high")


@dataclass(frozen=True)
class Topic:
    id: str
    pillar: str
    title: str
    empathy_hook: str  # 시청자가 속으로 하는 말 (공감 포인트)
    info_core: str  # 영상이 전달할 핵심 정보
    sources: tuple[str, ...]  # 사실 확인에 쓸 공식 출처
    keywords: tuple[str, ...]  # 검색·트렌드 조회용 키워드 (첫 번째가 대표 키워드)
    season: tuple[int, ...]  # 잘 맞는 월. 비어 있으면 연중
    empathy: int  # 1~5
    info: int  # 1~5
    ai_fit: int  # 1~5, AI 이미지·내레이션만으로 설득력 있게 만들 수 있는 정도
    risk: str  # low / med / high (건강·금융 등 YMYL 위험도)

    @property
    def main_keyword(self) -> str:
        return self.keywords[0]


def _split(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(";") if v.strip())


def _parse_season(value: str) -> tuple[int, ...]:
    value = value.strip().lower()
    if value in ("", "all"):
        return ()
    months = tuple(int(m) for m in _split(value))
    for m in months:
        if not 1 <= m <= 12:
            raise ValueError(f"season 값은 1~12월이어야 합니다: {value}")
    return months


def _parse_score(value: str, field: str, topic_id: str) -> int:
    score = int(value)
    if not 1 <= score <= 5:
        raise ValueError(f"{topic_id}의 {field} 점수는 1~5여야 합니다: {value}")
    return score


def load_topics(path: str | Path | None = None) -> list[Topic]:
    path = Path(path) if path else DEFAULT_BANK
    topics: list[Topic] = []
    seen: set[str] = set()
    # utf-8-sig: 엑셀에서 저장한 BOM 포함 CSV도 그대로 읽는다
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            topic_id = row["id"].strip()
            if topic_id in seen:
                raise ValueError(f"중복된 아이템 id: {topic_id}")
            seen.add(topic_id)
            risk = row["risk"].strip().lower()
            if risk not in RISK_LEVELS:
                raise ValueError(f"{topic_id}의 risk는 {RISK_LEVELS} 중 하나여야 합니다: {risk}")
            keywords = _split(row["keywords"])
            if not keywords:
                raise ValueError(f"{topic_id}에 키워드가 없습니다")
            topics.append(
                Topic(
                    id=topic_id,
                    pillar=row["pillar"].strip(),
                    title=row["title"].strip(),
                    empathy_hook=row["empathy_hook"].strip(),
                    info_core=row["info_core"].strip(),
                    sources=_split(row["sources"]),
                    keywords=keywords,
                    season=_parse_season(row["season"]),
                    empathy=_parse_score(row["empathy"], "empathy", topic_id),
                    info=_parse_score(row["info"], "info", topic_id),
                    ai_fit=_parse_score(row["ai_fit"], "ai_fit", topic_id),
                    risk=risk,
                )
            )
    return topics


def select(
    topics: list[Topic], ids: list[str] | None = None, pillar: str | None = None
) -> list[Topic]:
    """id 목록 또는 콘텐츠 기둥(pillar)으로 아이템을 고른다. 둘 다 없으면 전체."""
    if ids:
        by_id = {t.id: t for t in topics}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise KeyError(f"아이템 뱅크에 없는 id: {', '.join(missing)}")
        return [by_id[i] for i in ids]
    if pillar:
        return [t for t in topics if pillar in t.pillar]
    return list(topics)
