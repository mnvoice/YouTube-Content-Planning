"""순위표·캘린더·조사 결과를 마크다운/CSV로 저장한다."""

from __future__ import annotations

import csv
from pathlib import Path

from .planner import Slot, weekday_ko
from .scoring import LABELS, WEIGHTS, ScoreCard


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.0f}"


def ranking_markdown(cards: list[ScoreCard], month: int) -> str:
    lines = [
        f"# 아이템 순위 ({month}월 기준)",
        "",
        "점수 가중치: " + ", ".join(f"{LABELS[k]} {int(w * 100)}%" for k, w in WEIGHTS.items()),
        "",
        "'반영도'는 실제 데이터가 들어간 가중치 비율입니다. 100%가 아니면 API 키를 넣고 `research`를 실행해 보세요.",
        "",
        "| 순위 | ID | 기둥 | 아이템 | 총점 | " + " | ".join(LABELS[k] for k in WEIGHTS) + " | 반영도 | 메모 |",
        "|---|---|---|---|---|" + "---|" * len(WEIGHTS) + "---|---|",
    ]
    for i, c in enumerate(cards, 1):
        comps = " | ".join(_fmt(c.components.get(k)) for k in WEIGHTS)
        lines.append(
            f"| {i} | {c.topic.id} | {c.topic.pillar} | {c.topic.title} | **{c.total:.0f}** | {comps} "
            f"| {c.coverage * 100:.0f}% | {'; '.join(c.notes)} |"
        )
    return "\n".join(lines) + "\n"


def ranking_csv(cards: list[ScoreCard], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "id", "pillar", "title", "total", *WEIGHTS, "coverage", "notes"])
        for i, c in enumerate(cards, 1):
            w.writerow(
                [i, c.topic.id, c.topic.pillar, c.topic.title, c.total]
                + [c.components.get(k) if c.components.get(k) is not None else "" for k in WEIGHTS]
                + [c.coverage, " / ".join(c.notes)]
            )


def calendar_markdown(slots: list[Slot]) -> str:
    lines = [
        "# 업로드 캘린더",
        "",
        "각 영상은 공개 2~3일 전 쇼츠 1~2개로 예고하고, 공개 후 댓글에서 다음 소재를 수집합니다.",
        "",
        "| 날짜 | 요일 | 기둥 | ID | 아이템 | 공감 훅 (오프닝 한 줄) | 점수 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in slots:
        t = s.card.topic
        lines.append(
            f"| {s.day.isoformat()} | {weekday_ko(s.day)} | {t.pillar} | {t.id} | {t.title} "
            f"| \"{t.empathy_hook}\" | {s.card.total:.0f} |"
        )
    return "\n".join(lines) + "\n"


def research_markdown(topic_id: str, title: str, data: dict) -> str:
    lines = [f"# 조사 결과: {topic_id} {title}", ""]
    nv = data.get("naver")
    if nv:
        lines += [
            "## 네이버 데이터랩 (40~59세)",
            f"- 기준 키워드({nv.get('anchor')}) 대비 검색량: **{nv.get('demand')}배**",
            f"- 최근 4주 / 이전 12주 추세: **{nv.get('momentum')}**",
            "",
        ]
    yt = data.get("youtube")
    if yt:
        lines += [
            f"## YouTube 최근 {yt.get('days')}일 인기 영상 ('{yt.get('query')}')",
            f"- 영상 {yt.get('video_count')}개, 조회수 중앙값 {yt.get('median_views'):,}"
            f" (롱폼 {yt.get('median_views_long'):,})",
            f"- 상위 5개 아웃라이어 배수 중앙값: **{yt.get('outlier_median_top5')}배**",
            "",
            "| 배수 | 조회수 | 구독자 | 길이 | 제목 | 채널 |",
            "|---|---|---|---|---|---|",
        ]
        for v in yt.get("videos", []):
            subs = "비공개" if v.get("subs") is None else f"{v['subs']:,}"
            length = "쇼츠" if v.get("is_short") else f"{v.get('duration_sec', 0) // 60}분"
            lines.append(
                f"| {v['outlier_ratio']} | {v['views']:,} | {subs} | {length} "
                f"| [{v['title']}]({v['url']}) | {v['channel']} |"
            )
        voices = yt.get("voice_comments") or []
        if voices:
            lines += ["", "### 시청자 목소리 (사연·질문 댓글)", ""]
            for c in voices:
                text = c["text"].replace("\n", " ")
                lines.append(f"- [{c['kind']}] {text} (좋아요 {c['likes']})")
        lines.append("")
    nw = data.get("news")
    if nw:
        lines += [f"## 최근 {nw.get('days')}일 뉴스 ({nw.get('count')}건)", ""]
        for item in nw.get("items", []):
            lines.append(f"- [{item['title']}]({item['link']}) {item.get('source', '')}")
        lines.append("")
    if len(lines) == 2:
        lines.append("아직 조사 데이터가 없습니다. `python -m ytplan research --topic " + topic_id + "`를 실행하세요.")
    return "\n".join(lines) + "\n"


def _length(v: dict) -> str:
    return "쇼츠" if v.get("is_short") else f"{v.get('duration_sec', 0) // 60}분"


def _num(n: int | None) -> str:
    return "비공개" if n is None else f"{n:,}"


def benchmark_markdown(data: dict, hits_per_channel: int = 5, top_hits: int = 30) -> str:
    channels, hits = data.get("channels", []), data.get("hits", [])
    lines = [
        "# 벤치마크: 잘 되는 채널 역기획",
        "",
        f"- 생성: {data.get('generated_at')}",
        f"- 시드 키워드: {', '.join(data.get('seeds', [])) or '(직접 지정한 채널만)'}",
        f"- 분석: 채널 {len(channels)}개, 영상 {data.get('video_count', 0):,}개, 히트 {len(hits)}개",
        "",
        "**배수** = 그 채널의 평소 조회수(최근 영상 중앙값) 대비 몇 배 나왔는지. 큰 채널의 조회수가 아니라",
        "'그 채널 안에서도 유난히 터진' 영상을 봐야 주제와 제목의 힘을 알 수 있습니다. (롱폼·쇼츠 따로 비교, 공개 14일 미만 제외)",
        "",
        "## 1. 벤치마크 채널",
        "",
        "| 채널 | 구독자 | 롱폼 평소 조회수 | 조회수/구독자 | 주당 업로드 | 롱폼 평균 길이 | 쇼츠 비중 | 찾은 경로 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in channels:
        vps = "-" if c.get("views_per_sub") is None else f"{c['views_per_sub']:.2f}"
        lines.append(
            f"| [{c['title']}]({c['url']}) | {_num(c.get('subs'))} | {c.get('median_views_long', 0):,} | {vps} "
            f"| {c.get('uploads_per_week')} | {c.get('avg_long_minutes')}분 | {c.get('shorts_share', 0) * 100:.0f}% "
            f"| {', '.join(c.get('seeds', []))} |"
        )

    lines += ["", f"## 2. 전체 히트 영상 TOP {top_hits}", "", "| 배수 | 조회수 | 길이 | 제목 | 채널 |", "|---|---|---|---|---|"]
    for v in hits[:top_hits]:
        lines.append(f"| {v['channel_multiple']}x | {v['views']:,} | {_length(v)} | [{v['title']}]({v['url']}) | {v['channel']} |")

    lines += ["", "## 3. 히트 제목에 많은 구조", "",
              "lift가 1보다 크면 평소 제목보다 히트 제목에 더 자주 쓰인 구조입니다.", "",
              "| 구조 | 설명 | 히트 중 | 전체 중 | lift | 예시 |", "|---|---|---|---|---|---|"]
    for p in data.get("patterns", []):
        lift = "-" if p["lift"] is None else f"{p['lift']:.2f}"
        example = p["examples"][0] if p["examples"] else ""
        lines.append(
            f"| {p['pattern']} | {p['description']} | {p['hit_share'] * 100:.0f}% | {p['base_share'] * 100:.0f}% | {lift} | {example} |"
        )

    terms = data.get("terms", [])
    if terms:
        lines += ["", "## 4. 히트 제목 핵심어", "", " · ".join(f"**{t['term']}**({t['hits']}회, x{t['lift']})" for t in terms)]

    bank = data.get("bank", {})
    lines += ["", "## 5. 우리 아이템 뱅크와 비교", ""]
    if bank.get("pillars"):
        lines.append("히트 영상이 뱅크 아이템과 겹친 기둥: " + ", ".join(f"{k} {v}개" for k, v in bank["pillars"].items()))
    gaps = bank.get("gaps", [])
    lines += ["", f"### 뱅크에 없는 히트 주제 ({len(gaps)}개) → 새 아이템 후보", ""]
    for v in gaps[:30]:
        lines.append(f"- {v['channel_multiple']}x · {v['views']:,}회 · [{v['title']}]({v['url']}) ({v['channel']})")

    lines += ["", "## 6. 채널별 히트", ""]
    by_channel: dict[str, list[dict]] = {}
    for v in hits:
        by_channel.setdefault(v["channel"], []).append(v)
    for c in channels:
        top = by_channel.get(c["title"], [])[:hits_per_channel]
        if not top:
            continue
        lines += [f"### {c['title']}", ""]
        for v in top:
            lines.append(f"- {v['channel_multiple']}x · {v['views']:,}회 · {_length(v)} · [{v['title']}]({v['url']})")
        lines.append("")

    lines += ["", "다음 단계: `python -m ytplan ideas`로 이 결과를 바탕으로 새 아이템을 만드세요."]
    return "\n".join(lines) + "\n"
