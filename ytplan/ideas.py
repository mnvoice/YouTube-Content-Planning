"""벤치마크 결과(히트 영상)를 Claude로 역기획해 새 아이템을 만든다.

결과는 아이템 뱅크와 같은 형식의 행으로도 저장되어, `--append`로 뱅크에 바로 추가할 수 있다.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

from .generate import call_structured
from .topics import Topic

PILLAR_PREFIX = {"건강": "H", "돈·노후": "M", "일·인생2막": "W", "가족": "F", "마음": "P", "생활·디지털": "L", "추억·공감": "N"}
BANK_COLUMNS = ["id", "pillar", "title", "empathy_hook", "info_core", "sources", "keywords", "season", "empathy", "info", "ai_fit", "risk"]

Pillar = Literal["건강", "돈·노후", "일·인생2막", "가족", "마음", "생활·디지털", "추억·공감"]

SYSTEM_PROMPT = """\
당신은 40~50대 한국 시청자를 위한 '정보 + 공감' 유튜브 채널의 기획 PD입니다.
채널은 AI 내레이션과 일러스트로 제작하며, 공식 출처에 근거한 정확한 정보와 진심 어린 공감이 무기입니다.

비슷한 시청자층 채널에서 '그 채널 평소 조회수보다 몇 배 더 나온' 히트 영상 데이터를 받습니다. 이 데이터로 역기획하세요.

분석 원칙
- 조회수 절대값이 아니라 배수(채널 평소 대비)를 본다. 배수가 높은 영상은 채널의 힘이 아니라 주제와 제목의 힘으로 터진 것이다.
- 여러 채널에서 반복해 터진 주제와 구조를 우선한다. 한 채널에서만 터진 것은 우연일 수 있다.
- 자극적인 사연, 공포 마케팅, 검증되지 않은 건강 비법은 '이런 수요가 있다'는 신호로만 읽는다. 우리는 그 수요에 정확한 정보와 공감으로 답한다.

아이디어 원칙
- 히트 영상의 수요를 빌리되 각도(angle)를 바꾼다. 예: 오해 바로잡기, 숫자로 직접 계산해 보기, 두 선택지 비교, 먼저 겪은 사람의 후회, 체크리스트, 단계별 절차, 여러 사례를 재구성한 사연.
- 제목은 구체적이고 궁금하게 쓴다. 공포 조장·허위·과장은 쓰지 않고, 히트 제목을 그대로 베끼지 않는다.
- 기존 아이템 뱅크와 겹치는 주제는 확실히 더 날카로운 각도일 때만 제안하고, 되도록 뱅크에 없는 주제를 찾는다.
- AI 내레이션과 일러스트만으로 설득력 있게 만들 수 있어야 한다 (현장 촬영이나 실존 인물이 필요한 아이템은 제외).
- sources에는 실제로 존재하는 한국 공공기관·학회·통계 등 1차 출처만 적는다.
- inspired_by에는 근거가 된 히트 영상 제목을 데이터에서 그대로 옮겨 적는다.
- empathy·info·ai_fit는 1~5 정수. risk는 건강이면 대개 high, 돈·제도는 med, 그 밖은 low.
- season_months는 올리기 좋은 달(1~12). 연중 아이템이면 빈 목록.
"""


class Insight(BaseModel):
    finding: str
    evidence: list[str]
    how_to_use: str


class Idea(BaseModel):
    pillar: Pillar
    title: str
    thumbnail_text: str
    empathy_hook: str
    info_core: str
    angle: str
    inspired_by: list[str]
    why_it_works: str
    differentiation: str
    keywords: list[str]
    sources: list[str]
    season_months: list[int]
    empathy: int
    info: int
    ai_fit: int
    risk: Literal["low", "med", "high"]


class IdeaReport(BaseModel):
    insights: list[Insight]
    ideas: list[Idea]


def build_prompt(benchmark: dict, topics: list[Topic], count: int = 15, max_hits: int = 60) -> str:
    hits = benchmark.get("hits", [])[:max_hits]
    hit_lines = [
        f"- {v['channel_multiple']}x | {v['views']:,}회 | {'쇼츠' if v.get('is_short') else str(v.get('duration_sec', 0) // 60) + '분'}"
        f" | {v['channel']} | {v['title']}"
        for v in hits
    ]
    pattern_lines = [
        f"- {p['pattern']}({p['description']}): 히트 {p['hit_share'] * 100:.0f}% / 전체 {p['base_share'] * 100:.0f}%"
        for p in benchmark.get("patterns", [])
    ]
    term_line = ", ".join(f"{t['term']}({t['hits']})" for t in benchmark.get("terms", []))
    channel_lines = [
        f"- {c['title']}: 구독자 {c['subs']:,}, 롱폼 평소 조회수 {c.get('median_views_long', 0):,}" if c.get("subs") is not None
        else f"- {c['title']}: 롱폼 평소 조회수 {c.get('median_views_long', 0):,}"
        for c in benchmark.get("channels", [])
    ]
    bank_lines = [f"- {t.id} [{t.pillar}] {t.title}" for t in topics]
    return f"""\
아래 데이터를 분석해서 insights 5~8개와 새 아이템 ideas {count}개를 만들어 주세요.
ideas는 7개 기둥에 고르게 나누되, 히트가 많이 나온 기둥에 더 많이 배정하세요.

## 벤치마크 채널
{chr(10).join(channel_lines)}

## 히트 영상 (배수 | 조회수 | 길이 | 채널 | 제목)
{chr(10).join(hit_lines)}

## 히트 제목 구조 (히트 제목 중 비율 / 전체 제목 중 비율)
{chr(10).join(pattern_lines)}

## 히트 제목 핵심어 (등장 횟수)
{term_line}

## 이미 가진 아이템 뱅크 (겹치지 않게)
{chr(10).join(bank_lines)}
"""


def generate_ideas(
    benchmark: dict, topics: list[Topic], count: int = 15, client: anthropic.Anthropic | None = None
) -> IdeaReport:
    return call_structured(SYSTEM_PROMPT, build_prompt(benchmark, topics, count), IdeaReport, client)


def _clamp_score(v: int) -> int:
    return max(1, min(5, int(v)))


def to_bank_rows(report: IdeaReport, topics: list[Topic]) -> list[dict]:
    """아이디어를 아이템 뱅크 행으로 바꾸고, 기둥별로 이어지는 새 id를 붙인다."""
    next_no: dict[str, int] = {}
    for t in topics:
        m = re.fullmatch(r"([A-Z]+)(\d+)", t.id)
        if m:
            next_no[m.group(1)] = max(next_no.get(m.group(1), 0), int(m.group(2)))
    rows = []
    for idea in report.ideas:
        prefix = PILLAR_PREFIX[idea.pillar]
        next_no[prefix] = next_no.get(prefix, 0) + 1
        months = sorted({m for m in idea.season_months if 1 <= m <= 12})
        clean = [k.replace(";", " ").strip() for k in idea.keywords if k.strip()]
        rows.append(
            {
                "id": f"{prefix}{next_no[prefix]:02d}",
                "pillar": idea.pillar,
                "title": idea.title.replace(",", " "),
                "empathy_hook": idea.empathy_hook.replace(",", " "),
                "info_core": idea.info_core.replace(",", " "),
                "sources": ";".join(s.replace(";", " ").strip() for s in idea.sources if s.strip()),
                "keywords": ";".join(clean) or idea.title,
                "season": ";".join(map(str, months)) or "all",
                "empathy": _clamp_score(idea.empathy),
                "info": _clamp_score(idea.info),
                "ai_fit": _clamp_score(idea.ai_fit),
                "risk": idea.risk,
            }
        )
    return rows


def write_rows(rows: list[dict], path: Path, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if append:
        # 엑셀에서 저장하며 마지막 줄바꿈이 빠졌으면 새 행이 붙어 버리지 않게 채운다
        if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n"):
            with open(path, "a", encoding="utf-8", newline="") as f:
                f.write("\r\n")
        with open(path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=BANK_COLUMNS).writerows(rows)
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BANK_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def render_markdown(report: IdeaReport, rows: list[dict]) -> str:
    lines = ["# 벤치마크 기반 새 아이템", "", "## 히트 영상에서 찾은 것", ""]
    for i, ins in enumerate(report.insights, 1):
        lines += [f"### {i}. {ins.finding}", "", f"- 활용법: {ins.how_to_use}"]
        lines += [f"- 근거: {e}" for e in ins.evidence]
        lines.append("")
    lines += ["## 새 아이템", ""]
    for idea, row in zip(report.ideas, rows):
        lines += [
            f"### {row['id']} [{idea.pillar}] {idea.title}",
            "",
            f"- 썸네일: **{idea.thumbnail_text}**",
            f"- 공감 훅: \"{idea.empathy_hook}\"",
            f"- 각도: {idea.angle}",
            f"- 핵심 정보: {idea.info_core}",
            f"- 왜 먹히나: {idea.why_it_works}",
            f"- 차별화: {idea.differentiation}",
            f"- 근거 영상: {' / '.join(idea.inspired_by)}",
            f"- 출처: {', '.join(idea.sources)} · 위험도 {idea.risk} · 공감{row['empathy']} 정보{row['info']} AI{row['ai_fit']}",
            "",
        ]
    return "\n".join(lines)
