"""Claude로 영상 기획안(제목·썸네일·대본·장면별 이미지 프롬프트·사실확인 목록)을 만든다.

- API 키가 없으면 `--prompt-only`로 프롬프트만 파일로 뽑아 claude.ai 대화창에 붙여 넣어도 된다.
- 결과는 JSON 스키마로 강제(structured outputs)해서 매번 같은 형식의 마크다운으로 저장한다.
"""

from __future__ import annotations

import json

import anthropic
from pydantic import BaseModel

from .topics import Topic

MODEL = "claude-opus-5"
CHARS_PER_MINUTE = 280  # 40~50대 대상의 차분한 내레이션 속도 기준 (공백 포함 글자 수)

SYSTEM_PROMPT = """\
당신은 40~50대 한국 시청자를 위한 '정보 + 공감' 유튜브 채널의 기획 작가입니다.
영상은 AI 내레이션(TTS)과 AI 생성 이미지로 제작됩니다.

시청자
- 부모 부양과 자녀 뒷바라지를 함께 짊어진 세대. 건강·노후·가족 문제로 불안하지만 털어놓을 곳이 적다.
- 과장과 낚시에 지쳐 있고, "내 얘기 같다"는 공감과 "바로 써먹을 수 있는 정확한 정보"를 원한다.
- 휴대폰과 TV로 보며, 작은 글씨와 빠른 말을 불편해한다.

대본 구조 (공감 → 정보 → 행동 → 위로)
1. 공감 오프닝: 시청자가 속으로 하던 말이나 구체적인 장면 하나로 시작한다. 첫 30초 안에 이 영상이 무엇을 해결해 주는지 약속한다.
2. 나만 그런 게 아니다: 통계나 흔한 사례로 불안을 덜어 준다.
3. 핵심 정보 3~5개: 어려운 용어는 쉬운 말로 풀고, 중요한 내용은 한 번 더 요약한다.
4. 오늘 할 수 있는 한 가지: 체크리스트나 구체적인 다음 행동.
5. 위로와 질문: 따뜻한 한마디로 마무리하고, 댓글로 경험을 나누도록 질문한다.

지켜야 할 원칙
- 존댓말, 차분하고 따뜻한 톤. 한 문장은 되도록 50자 이내. 괄호·기호·영어 약어는 줄이고 소리 내어 읽기 좋게 쓴다.
- 사연은 실존 인물처럼 꾸미지 않는다. "이런 고민을 하시는 분들이 많습니다", "여러 사례를 바탕으로 재구성한 이야기입니다"처럼 밝힌다.
- 수치·제도·기준은 기준 연도를 밝힌다. 확실하지 않은 수치는 단정하지 말고 대본에 [확인 필요]로 표시한 뒤 fact_checks에 넣는다. 확인할 공식 출처(기관명)를 함께 적는다.
- 건강: 진단·처방을 하지 않는다. 증상이 있으면 전문의 상담을 권한다.
- 돈: 특정 금융상품 가입 권유, 수익 보장, 투자 종목 추천을 하지 않는다.
- 공포를 조장하는 제목("이거 모르면 큰일 납니다")을 쓰지 않는다. 시청자가 얻을 구체적인 이익을 약속하는 제목을 쓴다.
- 화면 자막(on_screen_text)은 15자 이내의 핵심 단어로, 큰 글씨로 보여 줄 것을 전제로 쓴다.
- visual_prompt는 이미지 생성 AI용 영어 프롬프트다. 실존 인물·유명인·브랜드·로고·글자를 넣지 않고, 한국 중년의 일상 장면을 따뜻한 일러스트 스타일로 일관되게 묘사한다.
- 참고 영상 제목은 시청자 반응을 이해하는 용도로만 쓰고 그대로 베끼지 않는다.
"""


class Scene(BaseModel):
    section: str
    seconds: int
    narration: str
    on_screen_text: str
    visual_prompt: str


class FactCheck(BaseModel):
    claim: str
    verify_at: str


class VideoPlan(BaseModel):
    titles: list[str]
    thumbnail_texts: list[str]
    viewer_persona: str
    hook: str
    scenes: list[Scene]
    comment_question: str
    description: str
    hashtags: list[str]
    shorts: list[str]
    fact_checks: list[FactCheck]
    production_notes: list[str]


def _research_context(research: dict, max_items: int = 8) -> str:
    parts = []
    yt = research.get("youtube") or {}
    if yt.get("videos"):
        titles = [f"- {v['title']} (조회수 {v['views']:,}, 구독자 대비 {v['outlier_ratio']}배)" for v in yt["videos"][:max_items]]
        parts.append("반응이 좋았던 기존 영상 (참고용, 베끼지 말 것):\n" + "\n".join(titles))
    voices = yt.get("voice_comments") or []
    if voices:
        lines = [f"- [{c['kind']}] {c['text'][:200]}" for c in voices[:max_items]]
        parts.append("시청자 댓글에서 나온 실제 고민과 질문:\n" + "\n".join(lines))
    nw = research.get("news") or {}
    if nw.get("items"):
        lines = [f"- {i['title']}" for i in nw["items"][:max_items]]
        parts.append("최근 뉴스 헤드라인 (시의성 참고, 수치는 1차 출처로 재확인):\n" + "\n".join(lines))
    return "\n\n".join(parts)


def build_prompt(topic: Topic, research: dict | None = None, minutes: int = 10) -> str:
    context = _research_context(research or {})
    prompt = f"""\
다음 아이템으로 약 {minutes}분짜리 롱폼 영상 기획안을 만들어 주세요.

아이템: {topic.title}
콘텐츠 기둥: {topic.pillar}
시청자가 속으로 하는 말(공감 훅): "{topic.empathy_hook}"
전달할 핵심 정보: {topic.info_core}
사실 확인에 쓸 공식 출처: {', '.join(topic.sources)}
검색 키워드: {', '.join(topic.keywords)}
YMYL 위험도: {topic.risk}

요구 사항
- 내레이션 전체 분량은 공백 포함 약 {minutes * CHARS_PER_MINUTE}자 (분당 약 {CHARS_PER_MINUTE}자).
- scenes는 6~12개. 각 장면의 seconds 합이 약 {minutes * 60}초가 되게.
- titles 5개, thumbnail_texts 3개 (썸네일 문구는 10자 안팎).
- shorts는 이 영상에서 잘라낼 쇼츠 아이디어 3개 (각 한두 문장).
- description에는 영상 요약, 목차(타임스탬프 자리), 참고한 공식 출처, AI 활용 제작 안내 문구를 넣는다.
- production_notes에는 TTS 목소리·속도, 이미지 스타일, 전문가 검수 필요 여부 등 제작 메모를 적는다.
"""
    if context:
        prompt += "\n조사 자료\n" + context + "\n"
    return prompt


def generate_plan(
    topic: Topic,
    research: dict | None = None,
    minutes: int = 10,
    client: anthropic.Anthropic | None = None,
) -> VideoPlan:
    client = client or anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        # 안전 분류기가 요청을 거절하면 서버가 권장 모델로 자동 재시도한다
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(topic, research, minutes)}],
        output_format=VideoPlan,
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("모델이 이 요청을 거절했습니다. 주제 표현을 바꿔 다시 시도해 보세요.")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("출력이 길이 제한에 걸려 잘렸습니다. --minutes 값을 줄여 보세요.")
    if message.parsed_output is None:
        raise RuntimeError("응답을 기획안 형식으로 해석하지 못했습니다.")
    return message.parsed_output


PRE_UPLOAD_CHECKLIST = [
    "fact_checks의 모든 수치·제도를 공식 출처에서 최신 기준으로 확인했다",
    "건강·금융 아이템은 전문가(의사·세무사·재무설계사 등) 검수를 받았거나, 대본에 일반 정보임을 밝혔다",
    "실제 사람·사건처럼 보이는 AI 이미지/영상을 썼다면 YouTube Studio에서 '변경되거나 합성된 콘텐츠'를 '예'로 설정했다",
    "배경음악·폰트·이미지의 상업적 이용 라이선스를 확인했다",
    "설명란에 참고 출처와 AI 활용 제작 안내를 넣었다",
    "고정 댓글로 시청자 경험을 묻는 질문을 달았다 (다음 소재 수집)",
]


def render_markdown(topic: Topic, plan: VideoPlan) -> str:
    total_sec = sum(s.seconds for s in plan.scenes)
    total_chars = sum(len(s.narration) for s in plan.scenes)
    lines = [
        f"# {plan.titles[0] if plan.titles else topic.title}",
        "",
        f"- 아이템: {topic.id} {topic.title} ({topic.pillar})",
        f"- 대상 시청자: {plan.viewer_persona}",
        f"- 예상 길이: 약 {total_sec // 60}분 {total_sec % 60}초 / 내레이션 {total_chars:,}자",
        "",
        "## 제목 후보",
        *[f"{i}. {t}" for i, t in enumerate(plan.titles, 1)],
        "",
        "## 썸네일 문구",
        *[f"- {t}" for t in plan.thumbnail_texts],
        "",
        "## 오프닝 훅 (첫 30초)",
        plan.hook,
        "",
        "## 대본",
    ]
    for i, s in enumerate(plan.scenes, 1):
        lines += [
            "",
            f"### {i}. {s.section} (약 {s.seconds}초)",
            "",
            s.narration,
            "",
            f"- 화면 자막: **{s.on_screen_text}**",
            f"- 이미지 프롬프트: `{s.visual_prompt}`",
        ]
    lines += [
        "",
        "## 고정 댓글 질문",
        plan.comment_question,
        "",
        "## 설명란",
        plan.description,
        "",
        "## 해시태그",
        " ".join(h if h.startswith("#") else f"#{h}" for h in plan.hashtags),
        "",
        "## 쇼츠로 잘라낼 아이디어",
        *[f"- {s}" for s in plan.shorts],
        "",
        "## 사실 확인 체크리스트 (업로드 전 필수)",
        *[f"- [ ] {f.claim} → {f.verify_at}" for f in plan.fact_checks],
        "",
        "## 제작 메모",
        *[f"- {n}" for n in plan.production_notes],
        "",
        "## 업로드 전 점검",
        *[f"- [ ] {c}" for c in PRE_UPLOAD_CHECKLIST],
    ]
    return "\n".join(lines) + "\n"


def plan_to_json(plan: VideoPlan) -> str:
    return json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)
