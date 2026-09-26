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


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def benchmark_markdown(data: dict, hits_per_channel: int = 5, top_hits: int = 30) -> str:
    """벤치마크 보고서. 이 보고서의 숫자는 모두 수집 데이터에서 계산한 '사실'이고,
    해석은 넣지 않는다. 40~50대 적합성은 근거 수준을 표시한다."""
    meta, col = data.get("meta", {}), data.get("collection", {})
    channels, hits = data.get("channels", []), data.get("hits", [])
    counts = col.get("counts", {})
    code = meta.get("code", {})
    lines = [
        "# 벤치마크: 잘 되는 채널 역기획",
        "",
        "> 이 보고서의 숫자는 모두 수집한 데이터에서 계산한 **사실**입니다. 왜 그런지에 대한 해석은 들어 있지 않습니다.",
        "> 40~50대 적합성은 YouTube가 다른 채널의 시청자 연령을 공개하지 않으므로 **간접 근거** 또는 **가설**로만 표시합니다.",
        "",
        "## 0. 실행 정보",
        "",
        f"- 실행: {meta.get('started_at')} ~ {meta.get('finished_at')}",
        f"- 코드: `{code.get('commit')}`" + (" (수정된 파일 있음)" if code.get("dirty") else ""),
        f"- 완료 여부: {'완료' if meta.get('complete') else '중단 — ' + meta.get('stop_reason', '')}",
        f"- 시드 키워드: {', '.join(meta.get('params', {}).get('seeds', [])) or '(직접 지정한 채널만)'}",
        f"- 기준: 채널 평소(공개 {meta.get('thresholds', {}).get('fresh_days')}일 지난 영상 중앙값, 형식별 최소 "
        f"{meta.get('thresholds', {}).get('min_baseline')}개) 대비 {meta.get('thresholds', {}).get('hit_multiple')}배 이상"
        f" + 조회수 {meta.get('thresholds', {}).get('hit_min_views', 0):,} 이상 = 히트",
        f"- YouTube 할당량 사용 추정: {meta.get('quota_used_estimate', 0):,} 유닛",
        "",
        "## 1. 수집 결과",
        "",
        f"**전체 {counts.get('전체', 0)} · 성공 {counts.get('성공', 0)} · 보류 {counts.get('보류', 0)} · "
        f"실패 {counts.get('실패', 0)} · 미실행 {counts.get('미실행', 0)}**",
        "",
        "- 성공: 평소 조회수 기준을 잡아 히트 계산에 포함 / 보류: 수집은 됐지만 기준을 잡을 영상이 부족해 계산에서 제외",
        "- 실패: 수집 중 오류 / 미실행: 할당량 소진 등으로 순서가 오기 전에 멈춤",
        "",
        "| 채널 | 경로 | 상태 | 사유·메모 |",
        "|---|---|---|---|",
    ]
    for r in col.get("channels", []):
        lines.append(f"| {r.get('title') or r.get('ref')} | {r.get('source')} | {r['status']} | {r.get('reason') or ''} |")

    impact = col.get("impact", {})
    lines += ["", "### 빠진 채널과 영향", ""]
    if impact.get("missing_channels"):
        lines += [
            f"- 계산에서 빠진 채널: {', '.join(impact['missing_channels'])}",
            f"- 이 채널들이 채널 찾기 단계 조회수에서 차지한 비중: {_pct(impact.get('missing_discovery_views_share'))}",
            f"- 분석된 채널이 하나도 없는 시드: {', '.join(impact.get('seeds_without_analyzed_channel') or []) or '없음'}",
            "- 영향: 위 시드 주제의 히트가 과소 대표될 수 있습니다. 비중이 20%를 넘으면 재실행을 권합니다.",
        ]
        manual = [r.get("title") or r.get("ref") for r in col.get("channels", [])
                  if r.get("source") == "직접 지정" and r["status"] != "성공"]
        if manual:
            lines.append(f"- 직접 지정했지만 빠진 채널: {', '.join(manual)} → 이 채널의 히트는 결과에 없습니다 (위 비중에는 포함되지 않음)")
    else:
        lines.append("- 없음 (선정된 채널이 모두 계산에 포함됨)")

    seeds = col.get("seeds", [])
    if seeds:
        lines += ["", "### 시드 검색", "", "| 시드 | 상태 | 찾은 영상 | 사유 |", "|---|---|---|---|"]
        lines += [f"| {x['seed']} | {x['status']} | {x['videos']} | {x.get('reason', '')} |" for x in seeds]
    disc = col.get("discovery", {})
    excluded = disc.get("excluded", [])
    if disc.get("candidates") or excluded:
        reasons = {}
        for e in excluded:
            reasons[e["reason"]] = reasons.get(e["reason"], 0) + 1
        lines += [
            "",
            f"채널 찾기: 후보 {disc.get('candidates', 0)}개 중 상위 선정, 순위 밖 {disc.get('not_selected', 0)}개, "
            f"기준 제외 {len(excluded)}개 ({', '.join(f'{k} {v}' for k, v in reasons.items()) or '-'})",
        ]
        if excluded:
            lines.append("제외된 채널 중 조회수 상위: " + ", ".join(
                f"{e['title'] or e['id']}({e['reason']})" for e in excluded[:5]))

    lines += [
        "",
        "## 2. 벤치마크 채널 [사실]",
        "",
        "| 채널 | 구독자 | 롱폼 평소 조회수 | 쇼츠 평소 조회수 | 조회수/구독자 | 주당 업로드 | 롱폼 평균 길이 | 쇼츠 비중 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in channels:
        vps = "-" if c.get("views_per_sub") is None else f"{c['views_per_sub']:.2f}"
        mlong = "-" if c.get("median_views_long") is None else f"{c['median_views_long']:,}"
        mshort = "-" if c.get("median_views_short") is None else f"{c['median_views_short']:,}"
        lines.append(
            f"| [{c['title']}]({c['url']}) | {_num(c.get('subs'))} | {mlong} | {mshort} | {vps} "
            f"| {c.get('uploads_per_week')} | {c.get('avg_long_minutes')}분 | {c.get('shorts_share', 0) * 100:.0f}% |"
        )

    lines += [
        "",
        f"## 3. 히트 영상 TOP {top_hits} [사실] (전체 히트 {len(hits)}개, 분석 영상 {data.get('video_count', 0):,}개)",
        "",
        "| 배수 | 조회수 | 일평균 | 길이 | 제목 | 채널 |",
        "|---|---|---|---|---|---|",
    ]
    for v in hits[:top_hits]:
        vpd = f"{v['views_per_day']:,.0f}" if v.get("views_per_day") is not None else "-"
        lines.append(
            f"| {v['channel_multiple']}x | {v['views']:,} | {vpd} | {_length(v)} | [{v['title']}]({v['url']}) | {v['channel']} |"
        )

    lines += [
        "",
        "## 4. 히트 제목 구조 [사실]",
        "",
        "lift = 히트 제목 중 비율 ÷ 전체 제목 중 비율. **히트 건수가 5개 미만이면 우연일 수 있어 참고만** 하세요.",
        "",
        "| 구조 | 설명 | 히트 (건) | 전체 (건) | lift | 예시 |",
        "|---|---|---|---|---|---|",
    ]
    for p in data.get("patterns", []):
        lift = "-" if p["lift"] is None else f"{p['lift']:.2f}"
        example = p["examples"][0] if p["examples"] else ""
        lines.append(
            f"| {p['pattern']} | {p['description']} | {_pct(p['hit_share'])} ({p.get('hit_n', '-')}) "
            f"| {_pct(p['base_share'])} ({p.get('base_n', '-')}) | {lift} | {example} |"
        )

    terms = data.get("terms", [])
    if terms:
        lines += ["", "## 5. 히트 제목 핵심어 [사실]", "",
                  " · ".join(f"**{t['term']}**(히트 {t['hits']}건, x{t['lift']})" for t in terms)]

    ev = data.get("age_evidence", {})
    lines += ["", "## 6. 40~50대 적합성 근거 [간접 근거]", ""]
    if ev.get("videos_checked"):
        lines += [
            f"- 히트 상위 {ev['videos_checked']}개 영상의 인기 댓글 {ev['comments_checked']:,}개를 확인했습니다.",
            f"- 댓글에서 **스스로 나이를 밝힌** 경우(추정): {ev.get('self_age_total', 0)}건 "
            f"({', '.join(f'{k} {v}' for k, v in ev.get('self_age_mentions', {}).items()) or '없음'})",
            f"- 그중 40~50대 비율: **{_pct(ev.get('share_40_50_among_self_age'))}**",
            f"- 갱년기·퇴직·손주 등 생활 단계 단서가 있는 댓글: {ev.get('life_stage_mentions', 0)}건",
            "- 한계: 댓글을 쓴 사람 기준이며 시청자 전체의 연령 분포가 아닙니다. 나이를 밝힌 댓글이 30건 미만이면 가설로 취급하세요.",
        ]
    else:
        lines.append("- 댓글 근거를 수집하지 못했습니다. 이 경우 40~50대 적합성은 **가설**입니다.")
    lines.append("- 다른 간접 근거: 채널 찾기 시드가 40~50대 관심 키워드, 제목의 연령 호명(4장 '나이·세대 호명')")

    bank = data.get("bank", {})
    lines += ["", "## 7. 우리 아이템 뱅크와 비교 [사실]", ""]
    if bank.get("pillars"):
        lines.append("히트 영상이 뱅크 아이템과 겹친 기둥: " + ", ".join(f"{k} {v}개" for k, v in bank["pillars"].items()))
    gaps = bank.get("gaps", [])
    lines += ["", f"### 뱅크에 없는 히트 주제 ({len(gaps)}개) → 새 아이템 후보", ""]
    for v in gaps[:30]:
        lines.append(f"- {v['channel_multiple']}x · {v['views']:,}회 · [{v['title']}]({v['url']}) ({v['channel']})")

    lines += ["", "## 8. 채널별 히트 [사실]", ""]
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
    return "\n".join(lines) + "\n"


def channels_csv(data: dict, path: Path) -> None:
    """채널별 수집 상태표 (검증용)."""
    summaries = {c["id"]: c for c in data.get("channels", [])}
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "ref", "source", "status", "reason", "channel_id", "subs", "analyzed_videos",
                    "mature_long", "mature_short", "median_views_long", "median_views_short", "matched_views"])
        for r in data.get("collection", {}).get("channels", []):
            c = summaries.get(r.get("id"), {})
            w.writerow([r.get("title"), r.get("ref"), r.get("source"), r["status"], r.get("reason"), r.get("id"),
                        c.get("subs"), c.get("analyzed_videos"), c.get("mature_long"), c.get("mature_short"),
                        c.get("median_views_long"), c.get("median_views_short"), r.get("matched_views")])
