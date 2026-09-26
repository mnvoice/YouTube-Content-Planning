"""잘 되는 채널을 역기획한다 (벤치마킹).

1. 채널 찾기: 40~50대 관심 키워드(시드)로 최근 1년 조회수 상위 영상을 검색해,
   여러 시드에 걸쳐 조회수를 내는 채널을 고른다. 직접 지정한 채널도 추가할 수 있다.
2. 채널 분석: 채널마다 최신 영상 150개를 모아 '그 채널 평소 조회수(중앙값)' 대비 몇 배 나왔는지 계산한다.
   큰 채널의 조회수는 채널의 힘이지만, 그 채널 안에서도 유난히 터진 영상은 '주제와 제목의 힘'이다.
3. 패턴 찾기: 터진 영상(히트)의 제목에 자주 나오는 구조와 단어를 전체 영상과 비교한다.
4. 아이템 뱅크와 비교: 히트가 어느 기둥에 몰리는지, 뱅크에 없는 주제는 무엇인지 찾는다.

수집 결과는 채널마다 성공·보류·실패·미실행과 그 사유를 남기고(collection),
분석에 쓴 영상 전체(videos)와 실행 정보(meta)를 함께 저장해 다른 사람이 다시 계산해 검증할 수 있게 한다.
할당량이 중간에 바닥나도 그때까지의 결과는 저장한다(meta.complete = false).

YouTube Data API 할당량(기본 1만 유닛/일): 시드 1개당 약 101 유닛, 채널 1개당 약 7 유닛, 댓글 확인 영상 1개당 1 유닛.
"""

from __future__ import annotations

import re
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import __version__, net
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
MIN_BASELINE = 10  # '평소 조회수'를 잡으려면 공개 14일이 지난 영상이 형식(롱폼/쇼츠)별로 최소 10개
AGE_EVIDENCE_HITS = 30  # 댓글에서 나이 언급을 확인할 히트 영상 수
QUOTA_UNITS = {"search": 100}  # 나머지 YouTube 엔드포인트는 1 유닛
YOUTUBE_ENDPOINTS = {"search", "videos", "channels", "playlistItems", "commentThreads", "i18nRegions"}
STATUSES = ("성공", "보류", "실패", "미실행")

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


class QuotaExceeded(RuntimeError):
    """YouTube 할당량 소진. 이후 호출도 모두 실패하므로 수집을 멈춘다."""


def _is_quota(e: Exception) -> bool:
    msg = str(e)
    return "quotaExceeded" in msg or "dailyLimitExceeded" in msg or "rateLimitExceeded" in msg


def _reason(e: Exception) -> str:
    return net.redact(str(e))[:200]


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
) -> dict:
    """시드 키워드마다 조회수 상위 영상을 모아, 여러 시드에서 조회수를 내는 채널 순으로 고른다.

    반환: channels(선정), seeds(시드별 결과), excluded(제외 사유), not_selected(순위 밖 후보 수)
    할당량이 바닥나면 QuotaExceeded를 던지되, 그때까지의 시드 결과는 예외의 partial 속성에 담는다.
    """
    agg: dict[str, dict] = {}
    seed_rows: list[dict] = []
    for seed in seeds:
        log(f"  검색: '{seed}'")
        try:
            videos = youtube.get_videos(api_key, youtube.search_video_ids(api_key, seed, days=days, max_results=per_seed))
        except (RuntimeError, OSError) as e:
            seed_rows.append({"seed": seed, "status": "실패", "videos": 0, "reason": _reason(e)})
            if _is_quota(e):
                err = QuotaExceeded("시드 검색 중 할당량 소진")
                err.partial = {"seeds": seed_rows + [
                    {"seed": s, "status": "미실행", "videos": 0, "reason": "할당량 소진으로 중단"}
                    for s in seeds[len(seed_rows):]
                ]}
                raise err from None
            log(f"    ! 검색 실패: {_reason(e)}")
            continue
        seed_rows.append({"seed": seed, "status": "성공", "videos": len(videos), "reason": ""})
        for v in videos:
            a = agg.setdefault(v["channel_id"], {"seeds": set(), "matched_views": 0, "matched_videos": 0})
            a["seeds"].add(seed)
            a["matched_views"] += v["views"]
            a["matched_videos"] += 1

    info = youtube.get_channel_info(api_key, list(agg))
    candidates, excluded = [], []
    for cid, a in agg.items():
        ch = info.get(cid)
        base = {"id": cid, "seeds": sorted(a["seeds"]), "matched_views": a["matched_views"], "matched_videos": a["matched_videos"]}
        if not ch:
            excluded.append({**base, "title": "", "subs": None, "reason": "채널 정보 없음(삭제·비공개)"})
        elif not include_broadcasters and is_broadcaster(ch["title"]):
            excluded.append({**base, "title": ch["title"], "subs": ch["subs"], "reason": "방송사·뉴스 채널"})
        elif ch["subs"] is not None and ch["subs"] < min_subs:
            excluded.append({**base, "title": ch["title"], "subs": ch["subs"], "reason": f"구독자 {min_subs:,}명 미만"})
        else:
            candidates.append({**ch, **base})
    candidates.sort(key=lambda c: (len(c["seeds"]), c["matched_views"]), reverse=True)
    return {
        "channels": candidates[:top],
        "seeds": seed_rows,
        "excluded": sorted(excluded, key=lambda c: c["matched_views"], reverse=True),
        "candidates": len(candidates),
        "not_selected": max(len(candidates) - top, 0),
    }


def analyze_channel(
    api_key: str, channel: dict, max_videos: int = 150, now: datetime | None = None, min_baseline: int = MIN_BASELINE
) -> dict:
    """채널 최신 영상들의 '채널 중앙값 대비 배수'를 계산한다. 롱폼과 쇼츠는 따로 비교한다.

    공개 14일이 지난 영상이 형식별로 min_baseline개 미만이면 그 형식은 기준을 잡지 않는다(배수 없음).
    두 형식 모두 기준이 없으면 status는 '보류'.
    """
    now = now or datetime.now(timezone.utc)
    videos = youtube.get_videos(api_key, youtube.uploads_video_ids(api_key, channel["uploads"], max_videos))
    mature = [v for v in videos if _age_days(v, now) >= FRESH_DAYS]
    longs = [v["views"] for v in mature if not v["is_short"]]
    shorts = [v["views"] for v in mature if v["is_short"]]
    med_long = statistics.median(longs) if len(longs) >= min_baseline else None
    med_short = statistics.median(shorts) if len(shorts) >= min_baseline else None
    for v in videos:
        age = _age_days(v, now)
        base = med_short if v["is_short"] else med_long
        v["channel_multiple"] = round(v["views"] / base, 2) if base and age >= FRESH_DAYS else None
        v["age_days"] = round(age, 1)
        v["mature"] = age >= FRESH_DAYS
        v["views_per_day"] = round(v["views"] / max(age, 1.0), 1)
        v["channel"] = channel["title"]
    ages = [_age_days(v, now) for v in videos]
    span_weeks = max((max(ages) - min(ages)) / 7, 1) if ages else 1
    long_secs = [v["duration_sec"] for v in videos if not v["is_short"]]

    notes = []
    if med_long is None and med_short is None:
        status = "보류"
        notes.append(
            f"공개 14일 지난 영상이 롱폼 {len(longs)}개·쇼츠 {len(shorts)}개로 기준(형식별 {min_baseline}개) 미달"
        )
    else:
        status = "성공"
        if med_long is None and longs:
            notes.append(f"롱폼 {len(longs)}개로 기준 미달 → 롱폼은 비교 제외")
        if med_short is None and shorts:
            notes.append(f"쇼츠 {len(shorts)}개로 기준 미달 → 쇼츠는 비교 제외")
    summary = {
        **channel,
        "status": status,
        "note": " / ".join(notes),
        "analyzed_videos": len(videos),
        "mature_long": len(longs),
        "mature_short": len(shorts),
        "median_views_long": int(med_long) if med_long is not None else None,
        "median_views_short": int(med_short) if med_short is not None else None,
        "views_per_sub": round(med_long / channel["subs"], 3) if med_long and channel.get("subs") else None,
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
                "hit_n": hit_n,
                "base_n": base_n,
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
        rows.append({"term": term, "hits": n, "base": base_df[term], "hit_share": round(hit_share, 2),
                     "lift": round(hit_share / base_share, 2)})
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



# ---- 40~50대 근거: 댓글의 나이 언급 -------------------------------------------------
# YouTube는 다른 채널의 시청자 연령을 공개하지 않는다. 그래서 댓글에서 스스로 밝힌 나이를 센다.
# 이것은 '댓글을 단 사람' 기준의 간접 근거이지 시청자 연령 분포가 아니다.
_AGE_NUM = re.compile(r"(?<![0-9])([2-8])0\s*대|(?<![0-9])([2-8][0-9])\s*(?:살|세)(?![0-9])")
_AGE_WORD = re.compile(r"사십|오십(?!견)|육십|칠십|마흔|쉰(?!다|목)|예순|일흔")
_AGE_WORD_DECADE = {"사십": 40, "마흔": 40, "오십": 50, "쉰": 50, "육십": 60, "예순": 60, "칠십": 70, "일흔": 70}
_SELF = re.compile(r"저도|저는|제가|저희|나도|나는|내가|올해|제 나이|내 나이")
_LIFE_STAGE = re.compile(r"갱년기|폐경|오십견|노안|퇴직|은퇴|정년|손주|손자|손녀|며느리|사위|친정|시어머니|요양|자녀 결혼")


def age_decades(text: str) -> list[int]:
    """댓글에 나온 나이를 10년 단위로 (예: '저도 52살' → [50])."""
    decades = []
    for m in _AGE_NUM.finditer(text):
        decades.append(int(m.group(1)) * 10 if m.group(1) else int(m.group(2)) // 10 * 10)
    for m in _AGE_WORD.finditer(text):
        decades.append(_AGE_WORD_DECADE[m.group(0)])
    return sorted(set(decades))


def age_evidence(comments: list[dict]) -> dict:
    by_decade: Counter = Counter()
    self_by_decade: Counter = Counter()
    life_stage = 0
    samples = []
    for c in comments:
        text = c["text"]
        decades = age_decades(text)
        for d in decades:
            by_decade[d] += 1
            if _SELF.search(text):
                self_by_decade[d] += 1
        if _LIFE_STAGE.search(text):
            life_stage += 1
        if decades and _SELF.search(text) and len(samples) < 3:
            samples.append(text.replace("\n", " ")[:80])
    return {
        "comments_checked": len(comments),
        "age_mentions": {f"{d}대": n for d, n in sorted(by_decade.items())},
        "self_age_mentions": {f"{d}대": n for d, n in sorted(self_by_decade.items())},
        "life_stage_mentions": life_stage,
        "samples": samples,
    }


def summarize_age_evidence(rows: list[dict]) -> dict:
    total = sum(r["comments_checked"] for r in rows)
    self_counts: Counter = Counter()
    for r in rows:
        self_counts.update(r["self_age_mentions"])
    self_total = sum(self_counts.values())
    in_range = self_counts.get("40대", 0) + self_counts.get("50대", 0)
    return {
        "videos_checked": len(rows),
        "comments_checked": total,
        "self_age_mentions": dict(sorted(self_counts.items())),
        "self_age_total": self_total,
        "share_40_50_among_self_age": round(in_range / self_total, 2) if self_total else None,
        "life_stage_mentions": sum(r["life_stage_mentions"] for r in rows),
    }


def _git_commit() -> dict:
    root = Path(__file__).resolve().parent.parent
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root,
                               capture_output=True, text=True, timeout=5)
        if commit.returncode == 0:
            return {"commit": commit.stdout.strip(), "dirty": bool(dirty.stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        pass
    return {"commit": "unknown", "dirty": None}


def quota_used(calls: Counter) -> int:
    """네트워크로 나간 YouTube 호출만 센 할당량 추정치 (캐시 재사용은 0)."""
    total = 0
    for key, n in calls.items():
        source, endpoint = key.split(":", 1)
        if source == "network" and endpoint in YOUTUBE_ENDPOINTS:
            total += QUOTA_UNITS.get(endpoint, 1) * n
    return total


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
    min_baseline: int = MIN_BASELINE,
    age_hits: int = AGE_EVIDENCE_HITS,
    log: Callable[[str], None] = print,
    now: datetime | None = None,
) -> dict:
    started = datetime.now().isoformat(timespec="seconds")
    net.calls.clear()
    stop_reason = ""
    rows: list[dict] = []  # 분석 대상 채널별 상태
    channels: dict[str, dict] = {}
    discovery: dict = {"seeds": [], "excluded": [], "candidates": 0, "not_selected": 0}

    for ref in channel_refs or []:
        try:
            ch = youtube.resolve_channel(api_key, ref)
        except (RuntimeError, OSError) as e:
            rows.append({"ref": ref, "id": "", "title": "", "source": "직접 지정", "status": "실패", "reason": _reason(e)})
            log(f"  ! 채널 조회 실패: {ref} ({_reason(e)})")
            if _is_quota(e):
                stop_reason = "YouTube 할당량 소진"
                break
            continue
        if not ch:
            rows.append({"ref": ref, "id": "", "title": "", "source": "직접 지정", "status": "실패", "reason": "채널을 찾지 못함"})
            log(f"  ! 채널을 찾지 못함: {ref}")
            continue
        channels[ch["id"]] = {**ch, "ref": ref, "source": "직접 지정", "seeds": [], "matched_views": 0, "matched_videos": 0}
        log(f"  지정 채널: {ch['title']}")

    if discover and not stop_reason:
        log(f"[1/3] 채널 찾기: 시드 {len(seeds)}개")
        try:
            discovery = discover_channels(api_key, seeds, days, min_subs=min_subs, top=top,
                                          include_broadcasters=include_broadcasters, log=log)
            for ch in discovery["channels"]:
                channels.setdefault(ch["id"], {**ch, "ref": "", "source": "자동 발굴"})
        except QuotaExceeded as e:
            stop_reason = "YouTube 할당량 소진"
            discovery["seeds"] = e.partial["seeds"]
        except (RuntimeError, OSError) as e:
            stop_reason = f"채널 찾기 실패: {_reason(e)}"
            if _is_quota(e):
                stop_reason = "YouTube 할당량 소진"
        if stop_reason:
            log(f"  ! {stop_reason} → 여기까지의 결과만 저장합니다")

    log(f"[2/3] 채널 분석: {len(channels)}개 (채널당 최신 영상 {max_videos}개)")
    summaries, videos = [], []
    for ch in channels.values():
        row = {"ref": ch.get("ref", ""), "id": ch["id"], "title": ch["title"], "source": ch["source"],
               "seeds": ch.get("seeds", []), "matched_views": ch.get("matched_views", 0)}
        if stop_reason:
            rows.append({**row, "status": "미실행", "reason": stop_reason})
            continue
        log(f"  {ch['title']}")
        if not ch.get("uploads"):
            rows.append({**row, "status": "실패", "reason": "업로드 목록 없음"})
            log("    ! 업로드 목록이 없어 건너뜀")
            continue
        try:
            result = analyze_channel(api_key, ch, max_videos=max_videos, now=now, min_baseline=min_baseline)
        except (RuntimeError, OSError) as e:
            rows.append({**row, "status": "실패", "reason": _reason(e)})
            log(f"    ! 분석 실패, 건너뜀 ({_reason(e)})")
            if _is_quota(e):
                stop_reason = "YouTube 할당량 소진"
            continue
        summary = result["channel"]
        rows.append({**row, "status": summary["status"], "reason": summary["note"],
                     "analyzed_videos": summary["analyzed_videos"]})
        if summary["status"] == "보류":
            log(f"    - 보류: {summary['note']}")
        summaries.append(summary)
        videos += result["videos"]

    log("[3/3] 히트 영상·제목 패턴·아이템 뱅크 비교")
    hits = pick_hits(videos)

    evidence_rows = []
    if age_hits and hits and not stop_reason:
        log(f"  댓글 나이 언급 확인: 히트 상위 {min(age_hits, len(hits))}개")
        for v in hits[:age_hits]:
            try:
                ev = age_evidence(youtube.fetch_comments(api_key, v["id"]))
            except (RuntimeError, OSError) as e:
                if _is_quota(e):
                    stop_reason = "YouTube 할당량 소진 (댓글 확인 중)"
                    log(f"  ! {stop_reason} → 댓글 근거는 {len(evidence_rows)}개 영상까지만")
                    break
                continue
            v["age_evidence"] = ev
            evidence_rows.append(ev)

    counts = Counter(r["status"] for r in rows)
    missing = [r for r in rows if r["status"] != "성공"]
    selected_views = sum(r.get("matched_views", 0) for r in rows)
    missing_views = sum(r.get("matched_views", 0) for r in missing)
    ok_seeds = {s for r in rows if r["status"] == "성공" for s in r.get("seeds", [])}
    seed_names = [x["seed"] for x in discovery["seeds"]]
    return {
        "meta": {
            "tool_version": __version__,
            "code": _git_commit(),
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "complete": not stop_reason,
            "stop_reason": stop_reason,
            "params": {"seeds": list(seeds) if discover else [], "channel_refs": list(channel_refs or []),
                       "discover": discover, "top": top, "days": days, "min_subs": min_subs, "max_videos": max_videos,
                       "include_broadcasters": include_broadcasters},
            "thresholds": {"hit_multiple": HIT_MULTIPLE, "hit_min_views": HIT_MIN_VIEWS, "fresh_days": FRESH_DAYS,
                           "min_baseline": min_baseline, "shorts_max_sec": youtube.SHORTS_MAX_SEC},
            "api_calls": dict(sorted(net.calls.items())),
            "quota_used_estimate": quota_used(net.calls),
        },
        "collection": {
            "seeds": discovery["seeds"],
            "discovery": {"candidates": discovery["candidates"], "not_selected": discovery["not_selected"],
                          "excluded": discovery["excluded"]},
            "channels": rows,
            "counts": {"전체": len(rows), **{s: counts.get(s, 0) for s in STATUSES}},
            "impact": {
                "missing_channels": [f"{r['title'] or r['ref']} ({r['status']})" for r in missing],
                "missing_discovery_views_share": round(missing_views / selected_views, 3) if selected_views else 0.0,
                "seeds_without_analyzed_channel": [s for s in seed_names if s not in ok_seeds],
            },
        },
        "channels": sorted(summaries, key=lambda c: c.get("median_views_long") or 0, reverse=True),
        "video_count": len(videos),
        "videos": [_compact(v) for v in videos],
        "hits": hits[:200],
        "patterns": pattern_stats(hits, videos),
        "terms": term_stats(hits, videos),
        "age_evidence": summarize_age_evidence(evidence_rows),
        "bank": map_to_bank(hits, topics),
    }


_VIDEO_FIELDS = ("id", "title", "channel_id", "channel", "published_at", "views", "likes", "comments", "duration_sec",
                 "is_short", "age_days", "mature", "views_per_day", "channel_multiple", "url")


def _compact(v: dict) -> dict:
    return {k: v.get(k) for k in _VIDEO_FIELDS}


def estimate_quota(seeds: int, channels: int, max_videos: int) -> int:
    pages = -(-max_videos // 50)
    return seeds * 101 + 1 + channels * (2 * pages + 1)


def hits_for_topic(benchmark: dict, topic: Topic, limit: int = 8) -> list[dict]:
    """대본 작성 때 참고할, 이 아이템과 관련된 히트 영상."""
    return [v for v in benchmark.get("hits", []) if match_topic(v["title"], [topic])][:limit]
