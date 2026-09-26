from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from ytplan import benchmark, generate, ideas, net, report
from ytplan.sources import youtube
from ytplan.topics import DEFAULT_BANK, load_topics, select

NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)
UC_A = "UC" + "a" * 22
UC_B = "UC" + "b" * 22
UC_KBS = "UC" + "k" * 22
UC_SMALL = "UC" + "s" * 22

CHANNELS = {
    UC_A: {"title": "건강한 오십", "handle": "@healthy50", "subs": 200_000, "uploads": "UUa"},
    UC_B: {"title": "인생 2막 이야기", "handle": "@life2", "subs": 50_000, "uploads": "UUb"},
    UC_KBS: {"title": "KBS 건강", "handle": "@kbs", "subs": 1_000_000, "uploads": "UUk"},
    UC_SMALL: {"title": "작은 채널", "handle": "@small", "subs": 3_000, "uploads": "UUs"},
}

# id: (채널, 제목, 조회수, 길이(ISO), 공개일)
VIDEOS = {
    "a1": (UC_A, "50대 국민연금 조기수령 후회하는 3가지 이유", 100_000, "PT12M", "2026-06-01T00:00:00Z"),
    "a2": (UC_A, "아침 스트레칭 따라하기", 20_000, "PT9M", "2026-06-05T00:00:00Z"),
    "a3": (UC_A, "건강 정보 모음", 10_000, "PT10M", "2026-06-10T00:00:00Z"),
    "a4": (UC_A, "건강 정보 모음 2", 10_000, "PT10M", "2026-06-15T00:00:00Z"),
    "a5": (UC_A, "쇼츠 건강 팁", 5_000, "PT40S", "2026-06-20T00:00:00Z"),
    "a6": (UC_A, "방금 올린 영상", 1_000_000, "PT11M", "2026-09-20T00:00:00Z"),
    "b1": (UC_B, "\"퇴직한 남편이 달라졌어요\" 아내의 눈물", 300_000, "PT15M", "2026-05-01T00:00:00Z"),
    "b2": (UC_B, "노후 준비 체크", 30_000, "PT8M", "2026-05-10T00:00:00Z"),
    "b3": (UC_B, "갱년기 증상 총정리", 40_000, "PT10M", "2026-05-20T00:00:00Z"),
    "k1": (UC_KBS, "KBS 명의 특집", 2_000_000, "PT50M", "2026-04-01T00:00:00Z"),
    "s1": (UC_SMALL, "작은 채널 영상", 50_000, "PT10M", "2026-04-01T00:00:00Z"),
}
SEARCH = {"50대 건강": ["a1", "b1", "k1", "s1"], "노후 준비": ["a2", "b2"]}
UPLOADS = {"UUa": ["a1", "a2", "a3", "a4", "a5", "a6"], "UUb": ["b1", "b2", "b3"]}


def _channel_item(cid):
    c = CHANNELS[cid]
    return {
        "id": cid,
        "snippet": {"title": c["title"], "customUrl": c["handle"]},
        "statistics": {"subscriberCount": str(c["subs"]), "viewCount": "1", "videoCount": "10"},
        "contentDetails": {"relatedPlaylists": {"uploads": c["uploads"]}},
    }


def fake_get_json(url, params=None, headers=None, ttl=0):
    params = params or {}
    if url.endswith("/search"):
        return {"items": [{"id": {"videoId": v}} for v in SEARCH.get(params["q"], [])]}
    if url.endswith("/videos"):
        items = []
        for vid in params["id"].split(","):
            cid, title, views, dur, pub = VIDEOS[vid]
            items.append(
                {
                    "id": vid,
                    "snippet": {"title": title, "channelId": cid, "channelTitle": CHANNELS[cid]["title"], "publishedAt": pub},
                    "statistics": {"viewCount": str(views)},
                    "contentDetails": {"duration": dur},
                }
            )
        return {"items": items}
    if url.endswith("/channels"):
        if "forHandle" in params:
            ids = [cid for cid, c in CHANNELS.items() if c["handle"] == params["forHandle"]]
        else:
            ids = params["id"].split(",")
        return {"items": [_channel_item(cid) for cid in ids if cid in CHANNELS]}
    if url.endswith("/playlistItems"):
        vids = UPLOADS[params["playlistId"]]
        # 2개씩 페이지를 나눠 페이지 넘김을 흉내 낸다
        start = int(params.get("pageToken", 0))
        page = vids[start : start + 2]
        resp = {"items": [{"contentDetails": {"videoId": v}} for v in page]}
        if start + 2 < len(vids):
            resp["nextPageToken"] = str(start + 2)
        return resp
    raise AssertionError(url)


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setattr(net, "get_json", fake_get_json)


@pytest.fixture(scope="module")
def topics():
    return load_topics()


@pytest.mark.parametrize(
    "ref",
    ["@healthy50", "healthy50", "https://www.youtube.com/@healthy50/videos", UC_A, f"https://www.youtube.com/channel/{UC_A}"],
)
def test_resolve_channel(fake_api, ref):
    ch = youtube.resolve_channel("KEY", ref)
    assert ch["id"] == UC_A and ch["uploads"] == "UUa" and ch["subs"] == 200_000


def test_resolve_channel_not_found(fake_api):
    assert youtube.resolve_channel("KEY", "@nobody") is None


def test_uploads_pagination(fake_api):
    assert youtube.uploads_video_ids("KEY", "UUa") == ["a1", "a2", "a3", "a4", "a5", "a6"]
    assert youtube.uploads_video_ids("KEY", "UUa", max_videos=3) == ["a1", "a2", "a3"]


def test_discover_skips_broadcasters_and_small_channels(fake_api):
    chans = benchmark.discover_channels("KEY", ["50대 건강", "노후 준비"], log=lambda m: None)
    assert [c["id"] for c in chans] == [UC_B, UC_A]  # 두 시드 모두 걸리고, 조회수 합이 큰 순서
    assert chans[0]["seeds"] == ["50대 건강", "노후 준비"]
    with_kbs = benchmark.discover_channels("KEY", ["50대 건강"], include_broadcasters=True, log=lambda m: None)
    assert UC_KBS in [c["id"] for c in with_kbs]


def test_analyze_channel_multiples(fake_api):
    ch = youtube.resolve_channel("KEY", "@healthy50")
    result = benchmark.analyze_channel("KEY", ch, now=NOW)
    by_id = {v["id"]: v for v in result["videos"]}
    assert result["channel"]["median_views_long"] == 15_000  # 공개 14일 미만 a6 제외, 롱폼 중앙값
    assert by_id["a1"]["channel_multiple"] == pytest.approx(6.67)
    assert by_id["a5"]["channel_multiple"] == 1.0  # 쇼츠는 쇼츠끼리 비교
    assert by_id["a6"]["channel_multiple"] is None
    assert result["channel"]["shorts_share"] == pytest.approx(0.17)


def test_tokenize_strips_josa():
    assert benchmark.tokenize("노후를 준비하는 50대의 국민연금은?") == ["노후", "준비하", "50대", "국민연금"]


def test_patterns_and_terms():
    hits = [{"title": "50대 국민연금 후회하는 3가지"}, {"title": "퇴직 후 후회하는 5가지"}, {"title": "국민연금 후회 3가지"}]
    others = [{"title": "건강 정보"}, {"title": "오늘의 운동"}, {"title": "산책 브이로그"}]
    stats = {p["pattern"]: p for p in benchmark.pattern_stats(hits, hits + others)}
    assert stats["숫자 목록"]["hit_share"] == 1.0 and stats["숫자 목록"]["lift"] == 2.0
    assert stats["후회·실수"]["examples"][0] == "50대 국민연금 후회하는 3가지"
    terms = {t["term"] for t in benchmark.term_stats(hits, hits + others, min_hits=2)}
    assert {"국민연금", "3가지"} <= terms


def test_map_to_bank(topics):
    hits = [
        {"title": "국민연금 조기수령 하면 손해일까", "channel_multiple": 5.0},
        {"title": "퇴직한 남편이 달라졌어요", "channel_multiple": 7.5},
    ]
    result = benchmark.map_to_bank(hits, topics)
    assert result["matched"][0]["topic_id"] == "M01"  # 띄어쓰기가 달라도 키워드로 매칭
    assert result["pillars"] == {"돈·노후": 1}
    assert [g["title"] for g in result["gaps"]] == ["퇴직한 남편이 달라졌어요"]


def test_run_end_to_end_and_report(fake_api, topics):
    data = benchmark.run("KEY", topics, seeds=["50대 건강", "노후 준비"], channel_refs=["@nobody"], log=lambda m: None)
    assert {c["title"] for c in data["channels"]} == {"건강한 오십", "인생 2막 이야기"}
    hit_titles = [v["title"] for v in data["hits"]]
    assert "\"퇴직한 남편이 달라졌어요\" 아내의 눈물" in hit_titles and "50대 국민연금 조기수령 후회하는 3가지 이유" in hit_titles
    assert "방금 올린 영상" not in hit_titles
    md = report.benchmark_markdown(data)
    assert "건강한 오십" in md and "뱅크에 없는 히트 주제" in md and "퇴직한 남편이 달라졌어요" in md


def test_estimate_quota():
    assert benchmark.estimate_quota(10, 15, 150) == 10 * 101 + 1 + 15 * 7


def test_script_prompt_uses_benchmark_hits(topics):
    bench = {
        "hits": [
            {"title": "국민연금 조기수령 후회하는 3가지", "channel_multiple": 6.7, "views": 100_000},
            {"title": "퇴직한 남편이 달라졌어요", "channel_multiple": 7.5, "views": 300_000},
        ],
        "patterns": [{"pattern": "후회·실수", "hit_share": 0.4, "lift": 2.5}],
    }
    m01 = select(topics, ["M01"])[0]
    prompt = generate.build_prompt(m01, None, 10, bench)
    assert "국민연금 조기수령 후회하는 3가지" in prompt and "퇴직한 남편" not in prompt
    assert "후회·실수: 히트 제목의 40%" in prompt
    # 관련 히트가 없으면 전체 히트를 제목·구성 참고용으로 넣는다
    h05 = select(topics, ["H05"])[0]
    assert "주제는 다르지만" in generate.build_prompt(h05, None, 10, bench)


def _idea(pillar="가족", title="퇴직한 남편과 24시간, 부부가 먼저 정할 5가지"):
    return ideas.Idea(
        pillar=pillar,
        title=title,
        thumbnail_text="삼식이 되기 전에",
        empathy_hook="남편이 퇴직하고 하루 종일 집에 있어요",
        info_core="부부 역할 재조정 / 각자의 시간 / 부부상담 이용법",
        angle="체크리스트",
        inspired_by=["퇴직한 남편이 달라졌어요"],
        why_it_works="여러 채널에서 퇴직 후 부부 갈등 사연이 7배 이상 터짐",
        differentiation="사연 대신 실제로 합의할 목록을 준다",
        keywords=["퇴직 남편", "은퇴 부부 갈등"],
        sources=["가족센터"],
        season_months=[],
        empathy=9,
        info=3,
        ai_fit=0,
        risk="low",
    )


def test_ideas_to_bank_rows_and_append(tmp_path, topics):
    report_ = ideas.IdeaReport(insights=[], ideas=[_idea(), _idea("건강", "갱년기 불면, 수면제보다 먼저 할 3가지")])
    rows = ideas.to_bank_rows(report_, topics)
    assert rows[0]["id"] == "F10" and rows[1]["id"] == "H10"  # 기둥별로 기존 번호 다음
    assert rows[0]["empathy"] == 5 and rows[0]["ai_fit"] == 1 and rows[0]["season"] == "all"

    bank = tmp_path / "bank.csv"
    src = DEFAULT_BANK.read_bytes().rstrip(b"\n")  # 마지막 줄바꿈이 빠진 파일도 처리
    bank.write_bytes(src)
    ideas.write_rows(rows, bank, append=True)
    merged = load_topics(bank)
    assert len(merged) == len(topics) + 2
    assert merged[-2].id == "F10" and merged[-2].keywords == ("퇴직 남편", "은퇴 부부 갈등")


def test_ideas_prompt_and_generation(topics):
    bench = {
        "channels": [{"title": "인생 2막 이야기", "subs": 50_000, "median_views_long": 40_000}],
        "hits": [{"title": "퇴직한 남편이 달라졌어요", "channel": "인생 2막 이야기", "channel_multiple": 7.5,
                  "views": 300_000, "duration_sec": 900, "is_short": False}],
        "patterns": [{"pattern": "감정", "description": "d", "hit_share": 1.0, "base_share": 0.2}],
        "terms": [{"term": "남편", "hits": 3}],
    }
    prompt = ideas.build_prompt(bench, topics, count=5)
    assert "7.5x | 300,000회 | 15분 | 인생 2막 이야기 | 퇴직한 남편이 달라졌어요" in prompt
    assert "M03 [돈·노후] 은퇴 후 건강보험료 폭탄 피하는 법" in prompt
    assert "ideas 5개" in prompt

    captured = {}
    result = ideas.IdeaReport(insights=[ideas.Insight(finding="f", evidence=["e"], how_to_use="h")], ideas=[_idea()])

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return SimpleNamespace(stop_reason="end_turn", parsed_output=result)

    def stream(**kwargs):
        captured.update(kwargs)
        return Stream()

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    assert ideas.generate_ideas(bench, topics, 5, client=client) is result
    assert captured["output_format"] is ideas.IdeaReport and captured["system"] == ideas.SYSTEM_PROMPT
    md = ideas.render_markdown(result, ideas.to_bank_rows(result, topics))
    assert "### F10 [가족] 퇴직한 남편과 24시간" in md


def test_run_skips_broken_channel(monkeypatch, topics):
    def flaky(url, params=None, headers=None, ttl=0):
        if url.endswith("/playlistItems") and params["playlistId"] == "UUb":
            raise RuntimeError("GET playlistItems 실패 (404): playlistNotFound")
        return fake_get_json(url, params, headers, ttl)

    monkeypatch.setattr(net, "get_json", flaky)
    logs = []
    data = benchmark.run("KEY", topics, seeds=["50대 건강", "노후 준비"], log=logs.append)
    assert [c["title"] for c in data["channels"]] == ["건강한 오십"]
    assert any("분석 실패, 건너뜀" in line for line in logs)


def test_run_stops_on_quota_exceeded(monkeypatch, topics):
    def quota(url, params=None, headers=None, ttl=0):
        if url.endswith("/playlistItems"):
            raise RuntimeError('GET playlistItems 실패 (403): {"reason": "quotaExceeded"}')
        return fake_get_json(url, params, headers, ttl)

    monkeypatch.setattr(net, "get_json", quota)
    with pytest.raises(RuntimeError, match="quotaExceeded"):
        benchmark.run("KEY", topics, seeds=["50대 건강"], log=lambda m: None)
