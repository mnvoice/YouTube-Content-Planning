"""업로드 캘린더 생성.

규칙
1. 업로드 날짜의 '달'을 기준으로 점수를 다시 매긴다.
2. 제철인 시즌 아이템(연말정산·명절·건강검진 등)을 먼저 배치한다.
   연중 아이템은 언제든 올릴 수 있지만 시즌 아이템은 때를 놓치면 1년을 기다려야 하기 때문이다.
3. 같은 콘텐츠 기둥이 연달아 나오지 않게 한다 (최근 2회와 겹치지 않게, 불가능하면 1회로 완화).
4. 한 번 쓴 아이템은 다시 쓰지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .scoring import ScoreCard, score_all, season_fit
from .topics import Topic

WEEKDAYS_KO = "월화수목금토일"


@dataclass
class Slot:
    day: date
    card: ScoreCard


def _in_season(card: ScoreCard, month: int) -> bool:
    """연중 아이템이 아니고, 이번 달이 올리기 좋은 달인가."""
    return bool(card.topic.season) and season_fit(card.topic, month) == 100.0


def upload_dates(start: date, weeks: int, weekdays: list[int]) -> list[date]:
    """start부터 weeks주 동안 지정한 요일(0=월 … 6=일)의 날짜."""
    wanted = set(weekdays)
    return [d for i in range(weeks * 7) if (d := start + timedelta(days=i)).weekday() in wanted]


def build_calendar(
    topics: list[Topic],
    research: dict[str, dict],
    start: date,
    weeks: int = 8,
    weekdays: list[int] | None = None,
    avoid_repeat: int = 2,
) -> list[Slot]:
    weekdays = weekdays if weekdays is not None else [1, 4]  # 화·금
    used: set[str] = set()
    recent_pillars: list[str] = []
    slots: list[Slot] = []
    cache: dict[int, list[ScoreCard]] = {}
    for day in upload_dates(start, weeks, weekdays):
        if day.month not in cache:
            cards = score_all(topics, research, day.month)
            cache[day.month] = sorted(cards, key=lambda c, m=day.month: (not _in_season(c, m), -c.total))
        candidates = [c for c in cache[day.month] if c.topic.id not in used]
        if not candidates:
            break
        pick = None
        for window in range(avoid_repeat, -1, -1):
            blocked = set(recent_pillars[-window:]) if window else set()
            pick = next((c for c in candidates if c.topic.pillar not in blocked), None)
            if pick:
                break
        used.add(pick.topic.id)
        recent_pillars.append(pick.topic.pillar)
        slots.append(Slot(day=day, card=pick))
    return slots


def weekday_ko(d: date) -> str:
    return WEEKDAYS_KO[d.weekday()]
