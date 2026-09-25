"""아이템 점수 모델.

    총점 = Σ(가중치 × 항목 점수) / Σ(데이터가 있는 항목의 가중치) − 위험도 감점

| 항목     | 의미                                        | 출처                      |
|----------|---------------------------------------------|---------------------------|
| demand   | 40~50대가 실제로 검색하는 양 (아이템 간 백분위) | 네이버 데이터랩           |
| proven   | 작은 채널도 터진 주제인가 (아웃라이어 배수)     | YouTube Data API          |
| empathy  | '내 얘기다' 싶은 정도                         | 아이템 뱅크 수동 점수     |
| info     | 보고 나면 실제로 써먹을 정보가 있는가          | 아이템 뱅크 수동 점수     |
| ai_fit   | AI 이미지·내레이션만으로 설득력 있게 만들 수 있나 | 아이템 뱅크 수동 점수   |
| timely   | 지금 올릴 이유가 있는가 (시즌·뉴스·검색 상승세) | 시즌 + 뉴스 + 데이터랩    |

데이터가 없는 항목은 빼고 나머지 가중치로 다시 나눈다. 그래서 API 키 없이도 순위를 낼 수 있고,
'coverage'(반영된 가중치 합)로 순위를 얼마나 믿을 수 있는지 함께 보여 준다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .topics import Topic

WEIGHTS = {"demand": 0.25, "proven": 0.20, "empathy": 0.20, "info": 0.15, "ai_fit": 0.10, "timely": 0.10}
RISK_PENALTY = {"low": 0.0, "med": 3.0, "high": 6.0}
LABELS = {
    "demand": "검색수요",
    "proven": "검증(아웃라이어)",
    "empathy": "공감",
    "info": "정보",
    "ai_fit": "AI제작",
    "timely": "시의성",
}


@dataclass
class ScoreCard:
    topic: Topic
    total: float
    components: dict[str, float | None]
    coverage: float  # 0~1, 실제 데이터가 반영된 가중치 비율
    notes: list[str] = field(default_factory=list)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def likert(v: int) -> float:
    """1~5점 → 0~100점."""
    return (v - 1) / 4 * 100


def season_fit(topic: Topic, month: int) -> float:
    """season에 적힌 '올리기 좋은 달'이면 100, 연중 아이템은 50, 아니면 15."""
    if not topic.season:
        return 50.0
    return 100.0 if month in topic.season else 15.0


def proven_score(outlier_median: float) -> float | None:
    """구독자 대비 조회수 배수 → 점수. 1배=40, 2배=60, 4배=80, 8배 이상=100."""
    if not outlier_median or outlier_median <= 0:
        return None
    return _clamp(40 + 20 * math.log2(outlier_median))


def news_score(count: int) -> float:
    """최근 30일 기사 수 → 점수. 1건=0, 10건=50, 100건=100."""
    return _clamp(50 * math.log10(count)) if count > 0 else 0.0


def momentum_score(m: float) -> float:
    """최근 4주 ÷ 이전 12주 검색량. 1배=50, 2배=100, 0.5배=0."""
    return _clamp(50 + 50 * math.log2(m)) if m > 0 else 0.0


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """값들을 0~100 백분위로. 하나뿐이면 50."""
    if not values:
        return {}
    if len(values) == 1:
        return {k: 50.0 for k in values}
    ordered = sorted(values.values())
    n = len(ordered)
    ranks = {}
    for k, v in values.items():
        below = sum(1 for x in ordered if x < v)
        equal = sum(1 for x in ordered if x == v)
        ranks[k] = round((below + (equal - 1) / 2) / (n - 1) * 100, 1)
    return ranks


def score_topic(topic: Topic, research: dict | None, month: int, demand_pct: float | None = None) -> ScoreCard:
    research = research or {}
    notes: list[str] = []
    comp: dict[str, float | None] = {
        "demand": demand_pct,
        "proven": None,
        "empathy": likert(topic.empathy),
        "info": likert(topic.info),
        "ai_fit": likert(topic.ai_fit),
    }

    yt = research.get("youtube")
    if yt:
        comp["proven"] = proven_score(yt.get("outlier_median_top5", 0))
        if yt.get("outlier_median_top5", 0) >= 3:
            notes.append(f"작은 채널도 터진 주제 (상위 아웃라이어 {yt['outlier_median_top5']}배)")

    timely_parts = [season_fit(topic, month)]
    if topic.season and timely_parts[0] == 100.0:
        notes.append("지금이 제철")
    nw = research.get("news")
    if nw:
        timely_parts.append(news_score(nw.get("count", 0)))
    nv = research.get("naver") or {}
    if nv.get("momentum"):
        timely_parts.append(momentum_score(nv["momentum"]))
        if nv["momentum"] >= 1.3:
            notes.append(f"40~50대 검색 상승 중 (x{nv['momentum']})")
    comp["timely"] = sum(timely_parts) / len(timely_parts)

    used = {k: v for k, v in comp.items() if v is not None}
    weight_sum = sum(WEIGHTS[k] for k in used)
    total = sum(WEIGHTS[k] * v for k, v in used.items()) / weight_sum
    penalty = RISK_PENALTY[topic.risk]
    if penalty:
        notes.append(f"YMYL 위험도 {topic.risk}: 전문가 검수·출처 표기 필수")
    return ScoreCard(
        topic=topic,
        total=round(_clamp(total - penalty), 1),
        components={k: (round(v, 1) if v is not None else None) for k, v in comp.items()},
        coverage=round(weight_sum, 2),
        notes=notes,
    )


def score_all(topics: list[Topic], research: dict[str, dict], month: int) -> list[ScoreCard]:
    demands = {
        t.id: research[t.id]["naver"]["demand"]
        for t in topics
        if (research.get(t.id) or {}).get("naver", {}).get("demand") is not None
    }
    pct = percentile_ranks(demands)
    cards = [score_topic(t, research.get(t.id), month, pct.get(t.id)) for t in topics]
    cards.sort(key=lambda c: c.total, reverse=True)
    return cards
