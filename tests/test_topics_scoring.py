from dataclasses import replace
from datetime import date

import pytest

from ytplan.planner import build_calendar, upload_dates
from ytplan.scoring import (
    WEIGHTS,
    momentum_score,
    news_score,
    percentile_ranks,
    proven_score,
    score_all,
    score_topic,
    season_fit,
)
from ytplan.topics import load_topics, select


@pytest.fixture(scope="module")
def topics():
    return load_topics()


def test_bank_is_valid(topics):
    assert len(topics) >= 40
    assert len({t.id for t in topics}) == len(topics)
    pillars = {t.pillar for t in topics}
    assert {"건강", "돈·노후", "가족", "마음"} <= pillars
    for t in topics:
        assert t.keywords and t.sources and t.empathy_hook and t.info_core


def test_select_by_id_and_pillar(topics):
    assert [t.id for t in select(topics, ["M03", "H02"])] == ["M03", "H02"]
    assert all("건강" in t.pillar for t in select(topics, pillar="건강"))
    with pytest.raises(KeyError):
        select(topics, ["ZZZ"])


def test_bank_rejects_bad_rows(tmp_path):
    bad = tmp_path / "bank.csv"
    bad.write_text(
        "id,pillar,title,empathy_hook,info_core,sources,keywords,season,empathy,info,ai_fit,risk\n"
        "X1,건강,t,h,i,s,k,all,9,3,3,low\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_topics(bad)


def test_season_fit(topics):
    m08 = select(topics, ["M08"])[0]  # 1월·12월 아이템
    assert season_fit(m08, 12) == 100
    assert season_fit(m08, 1) == 100
    assert season_fit(m08, 6) == 15
    assert season_fit(select(topics, ["M03"])[0], 6) == 50  # 연중 아이템


def test_scale_functions():
    assert proven_score(1) == 40
    assert proven_score(4) == 80
    assert proven_score(100) == 100
    assert proven_score(0) is None
    assert news_score(10) == 50
    assert news_score(0) == 0
    assert momentum_score(1) == 50
    assert momentum_score(2) == 100


def test_percentile_ranks():
    assert percentile_ranks({"a": 1.0}) == {"a": 50.0}
    r = percentile_ranks({"a": 1.0, "b": 2.0, "c": 3.0})
    assert r == {"a": 0.0, "b": 50.0, "c": 100.0}


def test_score_without_research_uses_manual_components_only(topics):
    card = score_topic(select(topics, ["M03"])[0], None, month=6)
    assert card.components["demand"] is None and card.components["proven"] is None
    assert card.coverage == pytest.approx(WEIGHTS["empathy"] + WEIGHTS["info"] + WEIGHTS["ai_fit"] + WEIGHTS["timely"])
    assert 0 <= card.total <= 100


def test_research_data_moves_the_score(topics):
    t = select(topics, ["M03"])[0]
    strong = {"youtube": {"outlier_median_top5": 8}, "news": {"count": 100}, "naver": {"momentum": 1.5}}
    weak = {"youtube": {"outlier_median_top5": 0.5}, "news": {"count": 1}, "naver": {"momentum": 0.6}}
    hi = score_topic(t, strong, month=6, demand_pct=100)
    lo = score_topic(t, weak, month=6, demand_pct=0)
    assert hi.total > lo.total
    assert hi.coverage == pytest.approx(1.0)


def test_risk_penalty(topics):
    base = select(topics, ["M03"])[0]
    low = score_topic(replace(base, risk="low"), None, 6).total
    high = score_topic(replace(base, risk="high"), None, 6).total
    assert low - high == pytest.approx(6.0)


def test_score_all_sorted(topics):
    cards = score_all(topics, {}, month=11)
    totals = [c.total for c in cards]
    assert totals == sorted(totals, reverse=True)


def test_upload_dates():
    days = upload_dates(date(2026, 10, 1), weeks=2, weekdays=[1, 4])  # 화·금
    assert [d.isoformat() for d in days] == ["2026-10-02", "2026-10-06", "2026-10-09", "2026-10-13"]


def test_calendar_rotates_pillars_and_never_repeats(topics):
    slots = build_calendar(topics, {}, date(2026, 10, 1), weeks=8, weekdays=[1, 4])
    assert len(slots) == 16
    ids = [s.card.topic.id for s in slots]
    assert len(ids) == len(set(ids))
    pillars = [s.card.topic.pillar for s in slots]
    for a, b in zip(pillars, pillars[1:]):
        assert a != b


def test_calendar_prefers_seasonal_topics(topics):
    slots = build_calendar(topics, {}, date(2026, 12, 1), weeks=2, weekdays=[1, 4])
    assert "M08" in [s.card.topic.id for s in slots]  # 12월엔 '올해 달라진 제도'
