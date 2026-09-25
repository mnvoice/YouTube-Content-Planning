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
