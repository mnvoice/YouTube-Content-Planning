"""YouTube 데이터로 아이템을 검증한다.

핵심 아이디어: '구독자 수 대비 조회수가 비정상적으로 높은 영상(아웃라이어)'은
채널의 힘이 아니라 주제 자체의 힘으로 조회수가 난 영상이다.
즉, 작은 채널이 이 주제로 터졌다면 우리도 그 주제로 승부할 수 있다.

- 공식 API: YouTube Data API v3 (API 키 필요, 무료 할당량 하루 10,000 유닛)
  search.list 100 유닛 / videos·channels·playlistItems·commentThreads.list 각 1 유닛
- 자동완성: 키 없이 쓰는 비공식 엔드포인트. 과도하게 호출하지 말 것.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta, timezone

from .. import net

API = "https://www.googleapis.com/youtube/v3"
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
SHORTS_MAX_SEC = 180  # 쇼츠는 최대 3분
MIN_SUBS = 1000  # 구독자 수가 너무 작거나 비공개일 때 비율이 튀지 않도록 하한을 둔다

# 자동완성 확장에 붙일 말. 40~50대가 실제로 검색창에 치는 형태를 흉내 낸다.
EXPAND_MODIFIERS = ("", "방법", "후회", "현실", "나이", "조건", "비용", "50대", "40대", "주의")

# 댓글에서 '공감(사연)'과 '질문'을 골라내는 표지어
STORY_MARKERS = (
    "저도", "저희", "나도", "우리 남편", "우리 아내", "남편", "아내", "우리 엄마", "우리 아빠",
    "엄마", "아버지", "어머니", "시어머니", "친정", "아들", "딸", "눈물", "공감", "힘들", "위로",
    "40대", "50대", "60대", "퇴직", "은퇴",
)
QUESTION_MARKERS = ("?", "궁금", "어떻게", "어디서", "알려주", "되나요", "인가요", "할까요", "있나요", "맞나요")


def _published_after(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_duration(iso: str) -> int:
    """ISO 8601 길이(PT1H2M3S)를 초로 바꾼다."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def search_video_ids(api_key: str, query: str, days: int = 365, max_results: int = 25) -> list[str]:
    data = net.get_json(
        f"{API}/search",
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "regionCode": "KR",
            "relevanceLanguage": "ko",
            "order": "viewCount",
            "publishedAfter": _published_after(days),
            "maxResults": max_results,
            "key": api_key,
        },
    )
    return [item["id"]["videoId"] for item in data.get("items", []) if item.get("id", {}).get("videoId")]


def get_videos(api_key: str, ids: list[str]) -> list[dict]:
    videos = []
    for i in range(0, len(ids), 50):
        data = net.get_json(
            f"{API}/videos",
            {"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i : i + 50]), "key": api_key},
        )
        for item in data.get("items", []):
            snip, stats = item.get("snippet", {}), item.get("statistics", {})
            duration = parse_duration(item.get("contentDetails", {}).get("duration", ""))
            videos.append(
                {
                    "id": item["id"],
                    "title": snip.get("title", ""),
                    "channel_id": snip.get("channelId", ""),
                    "channel": snip.get("channelTitle", ""),
                    "published_at": snip.get("publishedAt", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "duration_sec": duration,
                    "is_short": 0 < duration <= SHORTS_MAX_SEC,
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
            )
    return videos


def get_subscribers(api_key: str, channel_ids: list[str]) -> dict[str, int | None]:
    subs: dict[str, int | None] = {}
    unique = list(dict.fromkeys(channel_ids))
    for i in range(0, len(unique), 50):
        data = net.get_json(
            f"{API}/channels",
            {"part": "statistics", "id": ",".join(unique[i : i + 50]), "key": api_key},
        )
        for item in data.get("items", []):
            stats = item.get("statistics", {})
            hidden = stats.get("hiddenSubscriberCount", False)
            subs[item["id"]] = None if hidden else int(stats.get("subscriberCount", 0))
    return subs


def _channel_record(item: dict) -> dict:
    snip, stats = item.get("snippet", {}), item.get("statistics", {})
    hidden = stats.get("hiddenSubscriberCount", False)
    return {
        "id": item["id"],
        "title": snip.get("title", ""),
        "handle": snip.get("customUrl", ""),
        "subs": None if hidden else int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "uploads": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
        "url": f"https://www.youtube.com/channel/{item['id']}",
    }


def get_channel_info(api_key: str, channel_ids: list[str]) -> dict[str, dict]:
    """채널 id → 이름·구독자·총조회수·업로드 재생목록."""
    info: dict[str, dict] = {}
    unique = list(dict.fromkeys(channel_ids))
    for i in range(0, len(unique), 50):
        data = net.get_json(
            f"{API}/channels",
            {"part": "snippet,statistics,contentDetails", "id": ",".join(unique[i : i + 50]), "key": api_key},
        )
        for item in data.get("items", []):
            info[item["id"]] = _channel_record(item)
    return info


def resolve_channel(api_key: str, ref: str) -> dict | None:
    """'@핸들', 채널 id(UC…), 채널 주소 중 무엇을 받아도 채널 정보로 바꾼다."""
    ref = ref.strip()
    m = re.search(r"youtube\.com/(?:channel/(UC[\w-]{22})|(@[^/?#]+))", ref)
    if m:
        ref = m.group(1) or m.group(2)
    if re.fullmatch(r"UC[\w-]{22}", ref):
        return get_channel_info(api_key, [ref]).get(ref)
    handle = ref if ref.startswith("@") else f"@{ref}"
    data = net.get_json(
        f"{API}/channels",
        {"part": "snippet,statistics,contentDetails", "forHandle": handle, "key": api_key},
    )
    items = data.get("items", [])
    return _channel_record(items[0]) if items else None


def uploads_video_ids(api_key: str, playlist_id: str, max_videos: int = 150) -> list[str]:
    """채널 업로드 재생목록에서 최신 영상 id를 가져온다 (50개당 1 유닛)."""
    ids: list[str] = []
    page_token = None
    while len(ids) < max_videos:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50, "key": api_key}
        if page_token:
            params["pageToken"] = page_token
        data = net.get_json(f"{API}/playlistItems", params)
        ids += [it["contentDetails"]["videoId"] for it in data.get("items", []) if it.get("contentDetails")]
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids[:max_videos]


def _days_since(published_at: str) -> float:
    try:
        dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return 1.0
    return max((datetime.now(timezone.utc) - dt).total_seconds() / 86400, 1.0)


def analyze(api_key: str, query: str, days: int = 365, max_results: int = 25) -> dict:
    """검색어로 최근 인기 영상을 모아 수요와 '아웃라이어' 정도를 계산한다."""
    ids = search_video_ids(api_key, query, days=days, max_results=max_results)
    videos = get_videos(api_key, ids)
    subs = get_subscribers(api_key, [v["channel_id"] for v in videos])
    for v in videos:
        v["subs"] = subs.get(v["channel_id"])
        v["outlier_ratio"] = round(v["views"] / max(v["subs"] or 0, MIN_SUBS), 2)
        v["views_per_day"] = round(v["views"] / _days_since(v["published_at"]), 1)

    longs = [v for v in videos if not v["is_short"]]
    ranked = sorted(videos, key=lambda v: v["outlier_ratio"], reverse=True)
    top5 = [v["outlier_ratio"] for v in ranked[:5]]
    return {
        "query": query,
        "days": days,
        "video_count": len(videos),
        "median_views": int(statistics.median([v["views"] for v in videos])) if videos else 0,
        "median_views_long": int(statistics.median([v["views"] for v in longs])) if longs else 0,
        "outlier_median_top5": round(statistics.median(top5), 2) if top5 else 0.0,
        "videos": ranked[:10],
    }


def fetch_comments(api_key: str, video_id: str, max_results: int = 100) -> list[dict]:
    """인기순 상위 댓글. 댓글이 막힌 영상이면 빈 목록."""
    try:
        data = net.get_json(
            f"{API}/commentThreads",
            {
                "part": "snippet",
                "videoId": video_id,
                "order": "relevance",
                "textFormat": "plainText",
                "maxResults": max_results,
                "key": api_key,
            },
        )
    except RuntimeError:
        return []
    comments = []
    for item in data.get("items", []):
        snip = item.get("snippet", {})
        top = snip.get("topLevelComment", {}).get("snippet", {})
        comments.append(
            {
                "text": top.get("textDisplay", "").strip(),
                "likes": int(top.get("likeCount", 0)),
                "replies": int(snip.get("totalReplyCount", 0)),
            }
        )
    return comments


def pick_voice_comments(comments: list[dict], limit: int = 15, min_len: int = 15) -> list[dict]:
    """시청자의 '사연'과 '질문' 댓글만 골라낸다. 다음 영상의 소재이자 공감 포인트가 된다."""
    picked = []
    for c in comments:
        text = c["text"]
        if len(text) < min_len:
            continue
        is_question = any(m in text for m in QUESTION_MARKERS)
        story_hits = sum(1 for m in STORY_MARKERS if m in text)
        if not is_question and story_hits == 0:
            continue
        kind = "질문" if is_question else "사연"
        # 좋아요·답글이 많을수록, 사연 표지어가 많을수록, 글이 길수록 우선
        weight = c["likes"] + 2 * c["replies"] + 5 * story_hits + min(len(text), 300) / 30
        picked.append({**c, "kind": kind, "weight": round(weight, 1)})
    picked.sort(key=lambda c: c["weight"], reverse=True)
    return picked[:limit]


def autocomplete(query: str) -> list[str]:
    """유튜브 검색창 자동완성 (비공식, API 키 불필요)."""
    data = net.get_json(
        SUGGEST_URL,
        {"client": "firefox", "ds": "yt", "hl": "ko", "gl": "kr", "ie": "utf-8", "oe": "utf-8", "q": query},
        ttl=7 * 24 * 3600,
    )
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [s for s in data[1] if isinstance(s, str)]
    return []


def expand(keyword: str, modifiers: tuple[str, ...] = EXPAND_MODIFIERS) -> list[str]:
    """키워드 + 수식어 조합으로 자동완성을 긁어 '사람들이 실제로 궁금해하는 말'을 모은다."""
    found: dict[str, None] = {}
    for mod in modifiers:
        query = f"{keyword} {mod}".strip()
        for s in autocomplete(query):
            found.setdefault(s.strip(), None)
    return [s for s in found if s and s != keyword]
