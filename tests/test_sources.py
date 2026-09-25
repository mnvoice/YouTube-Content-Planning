from datetime import date

import pytest

from ytplan import net, research
from ytplan.sources import naver, news, youtube


def test_parse_duration():
    assert youtube.parse_duration("PT1H2M3S") == 3723
    assert youtube.parse_duration("PT45S") == 45
    assert youtube.parse_duration("P1DT1S") == 86401
    assert youtube.parse_duration("") == 0


def _fake_youtube(url, params=None, headers=None, ttl=0):
    if url.endswith("/search"):
        return {"items": [{"id": {"videoId": v}} for v in ("a", "b", "c")]}
    if url.endswith("/videos"):
        return {
            "items": [
                {
                    "id": "a",
                    "snippet": {"title": "작은 채널 대박", "channelId": "small", "channelTitle": "S", "publishedAt": "2026-01-01T00:00:00Z"},
                    "statistics": {"viewCount": "500000"},
                    "contentDetails": {"duration": "PT12M"},
                },
                {
                    "id": "b",
                    "snippet": {"title": "큰 채널 평범", "channelId": "big", "channelTitle": "B", "publishedAt": "2026-01-01T00:00:00Z"},
                    "statistics": {"viewCount": "100000"},
                    "contentDetails": {"duration": "PT9M"},
                },
                {
                    "id": "c",
                    "snippet": {"title": "쇼츠", "channelId": "hidden", "channelTitle": "H", "publishedAt": "2026-01-01T00:00:00Z"},
                    "statistics": {"viewCount": "3000"},
                    "contentDetails": {"duration": "PT50S"},
                },
            ]
        }
    if url.endswith("/channels"):
        return {
            "items": [
                {"id": "small", "statistics": {"subscriberCount": "10000"}},
                {"id": "big", "statistics": {"subscriberCount": "1000000"}},
                {"id": "hidden", "statistics": {"hiddenSubscriberCount": True}},
            ]
        }
    if url.endswith("/commentThreads"):
        return {
            "items": [
                {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "저도 퇴직하고 건보료 고지서 보고 깜짝 놀랐어요", "likeCount": 30}}, "totalReplyCount": 2}},
                {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "임의계속가입은 어디서 신청하나요?", "likeCount": 5}}, "totalReplyCount": 0}},
                {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "좋은 영상 감사합니다", "likeCount": 100}}, "totalReplyCount": 0}},
            ]
        }
    raise AssertionError(url)


def test_youtube_analyze_finds_outliers(monkeypatch):
    monkeypatch.setattr(net, "get_json", _fake_youtube)
    result = youtube.analyze("KEY", "임의계속가입")
    assert result["video_count"] == 3
    top = result["videos"][0]
    assert top["id"] == "a" and top["outlier_ratio"] == 50.0  # 50만 / 1만
    shorts = [v for v in result["videos"] if v["is_short"]]
    assert shorts and shorts[0]["subs"] is None and shorts[0]["outlier_ratio"] == 3.0  # 하한 1,000명 적용
    assert result["median_views_long"] == 300000


def test_pick_voice_comments(monkeypatch):
    monkeypatch.setattr(net, "get_json", _fake_youtube)
    picked = youtube.pick_voice_comments(youtube.fetch_comments("KEY", "a"))
    kinds = {c["text"]: c["kind"] for c in picked}
    assert kinds["저도 퇴직하고 건보료 고지서 보고 깜짝 놀랐어요"] == "사연"
    assert kinds["임의계속가입은 어디서 신청하나요?"] == "질문"
    assert "좋은 영상 감사합니다" not in kinds  # 좋아요가 많아도 사연·질문이 아니면 제외


def test_fetch_comments_handles_disabled_comments(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("commentsDisabled")

    monkeypatch.setattr(net, "get_json", boom)
    assert youtube.fetch_comments("KEY", "x") == []


def test_expand_dedupes(monkeypatch):
    monkeypatch.setattr(net, "get_json", lambda url, params=None, **k: [params["q"], ["국민연금 조기수령", "국민연금 조기수령 후회"]])
    result = youtube.expand("국민연금", modifiers=("", "후회"))
    assert result == ["국민연금 조기수령", "국민연금 조기수령 후회"]


def test_naver_momentum():
    assert naver.momentum([10] * 12 + [20] * 4) == 2.0
    assert naver.momentum([1, 2, 3]) is None


def test_naver_anchor_normalization(monkeypatch):
    calls = []

    def fake_post(url, body, headers=None, ttl=0):
        calls.append(body)
        assert body["ages"] == naver.AGES_40_50
        values = {"__anchor__": 50, "A": 25, "B": 100, "C": 50, "D": 10, "E": 5}
        return {
            "results": [
                {"title": g["groupName"], "data": [{"period": "p", "ratio": values[g["groupName"]]}]}
                for g in body["keywordGroups"]
            ]
        }

    monkeypatch.setattr(net, "post_json", fake_post)
    topics = {k: [k.lower()] for k in "ABCDE"}
    result = naver.compare_topics("id", "secret", topics, today=date(2026, 9, 25))
    assert len(calls) == 2  # 4개 + 1개로 나눠 요청, 매번 기준 키워드 포함
    assert all(c["keywordGroups"][0]["groupName"] == "__anchor__" for c in calls)
    assert result["A"]["demand"] == 0.5
    assert result["B"]["demand"] == 2.0
    assert result["E"]["demand"] == 0.1


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item><title>국민연금 개혁 내년부터 적용</title><link>https://news.example/1</link>
<pubDate>Mon, 21 Sep 2026 01:00:00 GMT</pubDate><source url="https://a">A일보</source></item>
<item><title>연금 수령 나이 정리</title><link>https://news.example/2</link>
<pubDate>Sun, 20 Sep 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss():
    parsed = news.parse_rss(RSS)
    assert parsed["count"] == 2
    assert parsed["items"][0] == {
        "title": "국민연금 개혁 내년부터 적용",
        "link": "https://news.example/1",
        "published": "Mon, 21 Sep 2026 01:00:00 GMT",
        "source": "A일보",
    }
    assert parsed["items"][1]["source"] == ""


def test_research_run_without_keys_saves_news(monkeypatch, tmp_path):
    from ytplan.topics import load_topics, select

    monkeypatch.setenv("YTPLAN_RESEARCH", str(tmp_path))
    monkeypatch.setattr(net, "get_text", lambda *a, **k: RSS)
    topics = select(load_topics(), ["M01"])
    results = research.run(topics, youtube_key=None, naver_id=None, naver_secret=None, log=lambda m: None)
    assert results["M01"]["news"]["count"] == 2
    assert "youtube" not in results["M01"]
    assert research.load("M01")["news"]["count"] == 2


def test_net_cache_skips_network(monkeypatch, tmp_path):
    monkeypatch.setenv("YTPLAN_CACHE", str(tmp_path))
    hits = []

    class Resp:
        status_code = 200
        encoding = "utf-8"
        text = '{"ok": 1}'

    def fake_request(*a, **k):
        hits.append(k.get("params"))
        return Resp()

    monkeypatch.setattr(net.requests, "request", fake_request)
    assert net.get_json("https://x", {"q": "a", "key": "SECRET1"}) == {"ok": 1}
    assert net.get_json("https://x", {"q": "a", "key": "SECRET2"}) == {"ok": 1}
    assert len(hits) == 1  # API 키만 다른 같은 요청은 캐시 재사용
    for f in tmp_path.iterdir():
        assert "SECRET" not in f.read_text() and "SECRET" not in f.name


def test_net_raises_on_http_error(monkeypatch, tmp_path):
    monkeypatch.setenv("YTPLAN_CACHE", str(tmp_path))

    class Resp:
        status_code = 403
        encoding = "utf-8"
        text = "quotaExceeded"

    monkeypatch.setattr(net.requests, "request", lambda *a, **k: Resp())
    with pytest.raises(RuntimeError, match="403"):
        net.get_json("https://x")
