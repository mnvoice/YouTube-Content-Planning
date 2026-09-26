"""잘 되는 채널을 역기획한다 (벤치마킹).

1. 채널 찾기: 40~50대 관심 키워드(시드)로 최근 1년 조회수 상위 영상을 검색해,
   여러 시드에 걸쳐 조회수를 내는 채널을 고른다. 직접 지정한 채널도 추가할 수 있다.
2. 채널 분석: 채널마다 최신 영상 150개를 모아 '그 채널 평소 조회수(중앙값)' 대비 몇 배 나왔는지 계산한다.
   큰 채널의 조회수는 채널의 힘이지만, 그 채널 안에서도 유난히 터진 영상은 '주제와 제목의 힘'이다.
3. 패턴 찾기: 터진 영상(히트)의 제목에 자주 나오는 구조와 단어를 전체 영상과 비교한다.
4. 아이템 뱅크와 비교: 히트가 어느 기둥에 몰리는지, 뱅크에 없는 주제는 무엇인지 찾는다.

YouTube Data API 할당량(기본 1만 유닛/일): 시드 1개당 약 101 유닛, 채널 1개당 약 7 유닛.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

from .sources import youtube
from .topics import Topic

DEFAULT_SEEDS = (
    "50대 건강",
    "중년 건강 습관",
    "노후 준비",
    "국민연금",
    "퇴직 후 생활",
    "갱년기",
    "부모님 요양",
    "50대 인생",
    "중년 부부",
    "노후 사연",
)
# 방송사·뉴스 채널은 제작 규모가 달라 따라 할 수 없으므로 기본적으로 뺀다
BROADCASTER_MARKERS = ("KBS", "MBC", "SBS", "EBS", "YTN", "JTBC", "MBN", "채널A", "TV조선", "연합뉴스", "뉴스", "NEWS", "News")
FRESH_DAYS = 14  # 아직 조회수가 쌓이는 중인 영상은 비교에서 뺀다
HIT_MULTIPLE = 2.0  # 채널 중앙값의 2배 이상이면 히트
HIT_MIN_VIEWS = 10_000

# 제목 구조 패턴: (이름, 정규식, 설명)
TITLE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("숫자 목록", r"\d+\s*(가지|개|단계|위|순위|번)", "3가지·5단계처럼 개수를 약속"),
    ("구체 숫자·금액", r"\d[\d,.]*\s*(만\s*원|억|원|%|퍼센트|세|살|년|개월|분)", "금액·나이·기간 같은 구체적 숫자"),
    ("나이·세대 호명", r"[4-7]0대|중년|노후|은퇴|퇴직|시니어|갱년기|노년", "시청자 나이·처지를 직접 부름"),
    ("대상 지정", r"하신\s*분|계신\s*분|분들|분이라면|꼭\s*보세요|필수", "'~하신 분 꼭 보세요'"),
    ("질문", r"\?|까요|나요|인가요|일까|을까", "궁금증을 질문으로"),
    ("속마음 인용", r"[\"“”‘’'「」]", "따옴표로 누군가의 말을 인용"),
    ("경고·금지", r"하지\s*마|절대|금지|주의|위험|조심|끊으세요|피하세요|멈추세요|큰일", "하지 말라·위험하다"),
    ("후회·실수", r"후회|실수|몰랐|늦게|깨달|뒤늦", "먼저 겪은 사람의 후회"),
    ("방법·비법", r"방법|하는\s*법|비법|꿀팁|노하우|비결|정리", "해결책을 약속"),
    ("비교", r"vs|VS|차이|비교|어느\s*쪽|뭐가\s*나", "A와 B 비교"),
    ("감정", r"눈물|충격|소름|감동|울컥|서럽|외로|행복|허무|무너", "감정을 앞세움"),
    ("사연·가족", r"사연|이야기|실화|아들|딸|며느리|시어머니|남편|아내|엄마|아버지|부모", "가족·사연"),
    ("반전·의외", r"사실은|알고\s*보니|의외|반전|진짜\s*이유|진실|아무도", "모르던 사실·반전"),
)

_JOSA = ("에서는", "으로는", "에게서", "까지는", "에서", "으로", "에게", "까지", "부터", "처럼", "보다",
         "은", "는", "이", "가", "을", "를", "에", "의", "도", "로", "와", "과", "만", "요")
_STOPWORDS = {"그리고", "하는", "있는", "없는", "이런", "저런", "그냥", "정말", "진짜", "무조건", "모든", "이것", "그것",
              "하면", "해야", "합니다", "입니다", "있습니다", "없습니다", "하세요", "보세요", "shorts", "Shorts"}


def is_broadcaster(title: str) -> bool:
    return any(m in title for m in BROADCASTER_MARKERS)


def _age_days(v: dict, now: datetime) -> float:
    try:
        dt = datetime.strptime(v["published_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return 0.0
    return (now - dt).total_seconds() / 86400


def discover_channels(
    api_key: str,
    seeds: tuple[str, ...] | list[str] = DEFAULT_SEEDS,
    days: int = 365,
    per_seed: int = 50,
    min_subs: int = 10_000,
    top: int = 15,
    include_broadcasters: bool = False,
    log: Callable[[str], None] = print,
) -> list[dict]:
    """시드 키워드마다 조회수 상위 영상을 모아, 여러 시드에서 조회수를 내는 채널 순으로 고른다."""
    agg: dict[str, dict] = {}
    for seed in seeds:
        log(f"  검색: '{seed}'")
        for v in youtube.get_videos(api_key, youtube.search_video_ids(api_key, seed, days=days, max_results=per_seed)):
            a = agg.setdefault(v["channel_id"], {"seeds": set(), "matched_views": 0, "matched_videos": 0})
            a["seeds"].add(seed)
            a["matched_views"] += v["views"]
            a["matched_videos"] += 1
    info = youtube.get_channel_info(api_key, list(agg))
    channels = []
    for cid, a in agg.items():
        ch = info.get(cid)
        if not ch or (not include_broadcasters and is_broadcaster(ch["title"])):
            continue
        if ch["subs"] is not None and ch["subs"] < min_subs:
            continue
        channels.append(
            {**ch, "seeds": sorted(a["seeds"]), "matched_views": a["matched_views"], "matched_videos": a["matched_videos"]}
        )
    channels.sort(key=lambda c: (len(c["seeds"]), c["matched_views"]), reverse=True)
    return channels[:top]


def analyze_channel(api_key: str, channel: dict, max_videos: int = 150, now: datetime | None = None) -> dict:
    """채널 최신 영상들의 '채널 중앙값 대비 배수'를 계산한다. 롱폼과 쇼츠는 따로 비교한다."""
    now = now or datetime.now(timezone.utc)
    videos = youtube.get_videos(api_key, youtube.uploads_video_ids(api_key, channel["uploads"], max_videos))
    mature = [v for v in videos if _age_days(v, now) >= FRESH_DAYS]
    longs = [v["views"] for v in mature if not v["is_short"]]
    shorts = [v["views"] for v in mature if v["is_short"]]
    med_long = statistics.median(longs) if longs else 0
    med_short = statistics.median(shorts) if shorts else 0
    for v in videos:
        base = med_short if v["is_short"] else med_long
        mature_video = _age_days(v, now) >= FRESH_DAYS
        v["channel_multiple"] = round(v["views"] / base, 2) if base and mature_video else None
        v["channel"] = channel["title"]
    ages = [_age_days(v, now) for v in videos]
    span_weeks = max((max(ages) - min(ages)) / 7, 1) if ages else 1
    long_secs = [v["duration_sec"] for v in videos if not v["is_short"]]
    summary = {
        **channel,
        "analyzed_videos": len(videos),
        "median_views_long": int(med_long),
        "median_views_short": int(med_short),
        "views_per_sub": round(med_long / channel["subs"], 3) if channel.get("subs") else None,
        "uploads_per_week": round(len(videos) / span_weeks, 1),
        "avg_long_minutes": round(statistics.mean(long_secs) / 60, 1) if long_secs else 0,
        "shorts_share": round(sum(v["is_short"] for v in videos) / len(videos), 2) if videos else 0,
    }
    return {"channel": summary, "videos": videos}


def pick_hits(videos: list[dict], min_multiple: float = HIT_MULTIPLE, min_views: int = HIT_MIN_VIEWS) -> list[dict]:
    hits = [
        v for v in videos
        if v.get("channel_multiple") is not None and v["channel_multiple"] >= min_multiple and v["views"] >= min_views
    ]
    return sorted(hits, key=lambda v: v["channel_multiple"], reverse=True)


def pattern_stats(hits: list[dict], videos: list[dict]) -> list[dict]:
    """패턴별로 '히트 제목 중 비율'과 '전체 제목 중 비율'을 비교한다. lift가 1보다 크면 히트에 더 자주 나온다."""
    stats = []
    for name, regex, desc in TITLE_PATTERNS:
        rx = re.compile(regex)
        hit_n = sum(1 for v in hits if rx.search(v["title"]))
        base_n = sum(1 for v in videos if rx.search(v["title"]))
        hit_share = hit_n / len(hits) if hits else 0
        base_share = base_n / len(videos) if videos else 0
        stats.append(
            {
                "pattern": name,
                "description": desc,
                "hit_share": round(hit_share, 2),
                "base_share": round(base_share, 2),
                "lift": round(hit_share / base_share, 2) if base_share else None,
                "examples": [v["title"] for v in hits if rx.search(v["title"])][:3],
            }
        )
    stats.sort(key=lambda s: (s["lift"] or 0, s["hit_share"]), reverse=True)
    return stats


def tokenize(title: str) -> list[str]:
    tokens = []
    for raw in re.findall(r"[0-9A-Za-z가-힣]+", title):
        tok = raw
        for josa in _JOSA:
            if len(tok) > len(josa) + 1 and tok.endswith(josa):
                tok = tok[: -len(josa)]
                break
        if len(tok) >= 2 and tok not in _STOPWORDS and not tok.isdigit():
            tokens.append(tok)
    return tokens


def term_stats(hits: list[dict], videos: list[dict], min_hits: int = 3, top: int = 25) -> list[dict]:
    """히트 제목에 자주 나오는 단어. 한 제목에 여러 번 나와도 1번으로 센다."""
    hit_df = Counter(t for v in hits for t in set(tokenize(v["title"])))
    base_df = Counter(t for v in videos for t in set(tokenize(v["title"])))
    rows = []
    for term, n in hit_df.items():
        if n < min_hits:
            continue
        hit_share = n / len(hits)
        base_share = base_df[term] / len(videos)
        rows.append({"term": term, "hits": n, "hit_share": round(hit_share, 2), "lift": round(hit_share / base_share, 2)})
    rows.sort(key=lambda r: (r["hits"] * r["lift"]), reverse=True)
    return rows[:top]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def match_topic(title: str, topics: list[Topic]) -> Topic | None:
    """제목에 아이템 키워드(띄어쓰기 무시)가 들어 있으면 그 아이템으로 본다."""
    squashed = _squash(title)
    for t in topics:
        if any(_squash(k) in squashed for k in t.keywords):
            return t
    return None


def map_to_bank(hits: list[dict], topics: list[Topic]) -> dict:
    pillars: Counter = Counter()
    matched, gaps = [], []
    for v in hits:
        t = match_topic(v["title"], topics)
        if t:
            pillars[t.pillar] += 1
            matched.append({"title": v["title"], "topic_id": t.id, "channel_multiple": v["channel_multiple"]})
        else:
            gaps.append(v)
    return {"pillars": dict(pillars.most_common()), "matched": matched, "gaps": gaps}


def run(
    api_key: str,
    topics: list[Topic],
    seeds: tuple[str, ...] | list[str] = DEFAULT_SEEDS,
    channel_refs: list[str] | None = None,
    discover: bool = True,
    top: int = 15,
    days: int = 365,
    min_subs: int = 10_000,
    max_videos: int = 150,
    include_broadcasters: bool = False,
    log: Callable[[str], None] = print,
) -> dict:
    channels: dict[str, dict] = {}
    for ref in channel_refs or []:
        try:
            ch = youtube.resolve_channel(api_key, ref)
        except RuntimeError as e:
            log(f"  ! 채널 조회 실패: {ref} ({str(e)[:120]})")
            continue
        if ch:
            channels[ch["id"]] = {**ch, "seeds": ["직접 지정"], "matched_views": 0, "matched_videos": 0}
            log(f"  지정 채널: {ch['title']}")
        else:
            log(f"  ! 채널을 찾지 못함: {ref}")
    if discover:
        log(f"[1/3] 채널 찾기: 시드 {len(seeds)}개")
        for ch in discover_channels(api_key, seeds, days, min_subs=min_subs, top=top,
                                    include_broadcasters=include_broadcasters, log=log):
            channels.setdefault(ch["id"], ch)

    log(f"[2/3] 채널 분석: {len(channels)}개 (채널당 최신 영상 {max_videos}개)")
    summaries, videos = [], []
    for ch in channels.values():
        log(f"  {ch['title']}")
        if not ch.get("uploads"):
            log("    ! 업로드 목록이 없어 건너뜀")
            continue
        try:
            result = analyze_channel(api_key, ch, max_videos=max_videos)
        except RuntimeError as e:
            # 한 채널이 막혀도 나머지 분석은 계속한다 (할당량 소진은 다음 채널도 실패하므로 중단)
            if "quotaExceeded" in str(e):
                raise
            log(f"    ! 분석 실패, 건너뜀 ({str(e)[:120]})")
            continue
        summaries.append(result["channel"])
        videos += result["videos"]

    log("[3/3] 히트 영상·제목 패턴·아이템 뱅크 비교")
    hits = pick_hits(videos)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seeds": list(seeds) if discover else [],
        "channels": sorted(summaries, key=lambda c: c.get("median_views_long", 0), reverse=True),
        "video_count": len(videos),
        "hits": hits[:200],
        "patterns": pattern_stats(hits, videos),
        "terms": term_stats(hits, videos),
        "bank": map_to_bank(hits, topics),
    }


def estimate_quota(seeds: int, channels: int, max_videos: int) -> int:
    pages = -(-max_videos // 50)
    return seeds * 101 + 1 + channels * (2 * pages + 1)


def hits_for_topic(benchmark: dict, topic: Topic, limit: int = 8) -> list[dict]:
    """대본 작성 때 참고할, 이 아이템과 관련된 히트 영상."""
    return [v for v in benchmark.get("hits", []) if match_topic(v["title"], [topic])][:limit]
