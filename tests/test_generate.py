from types import SimpleNamespace

import pytest

from ytplan import generate
from ytplan.topics import load_topics, select


@pytest.fixture
def topic():
    return select(load_topics(), ["M03"])[0]


def _plan():
    return generate.VideoPlan(
        titles=["퇴직 후 건보료, 이렇게 줄였습니다", "제목2"],
        thumbnail_texts=["건보료 폭탄 피하기"],
        viewer_persona="퇴직을 앞둔 50대 직장인",
        hook="퇴직 후 첫 고지서를 받고 놀라셨나요?",
        scenes=[
            generate.Scene(section="공감 오프닝", seconds=40, narration="가", on_screen_text="고지서 충격", visual_prompt="a"),
            generate.Scene(section="핵심 정보", seconds=80, narration="나다", on_screen_text="임의계속가입", visual_prompt="b"),
        ],
        comment_question="여러분은 퇴직 후 건보료가 얼마나 나오셨나요?",
        description="요약",
        hashtags=["건강보험", "#퇴직"],
        shorts=["쇼츠1"],
        fact_checks=[generate.FactCheck(claim="임의계속가입 최대 36개월", verify_at="국민건강보험공단")],
        production_notes=["차분한 여성 목소리"],
    )


def test_build_prompt_includes_topic_and_research(topic):
    research = {
        "youtube": {
            "videos": [{"title": "퇴직 후 건보료 폭탄", "views": 120000, "outlier_ratio": 12.0}],
            "voice_comments": [{"kind": "질문", "text": "임의계속가입 신청 기한이 있나요?"}],
        },
        "news": {"items": [{"title": "건보료 부과체계 개편"}]},
    }
    prompt = generate.build_prompt(topic, research, minutes=8)
    assert topic.empathy_hook in prompt
    assert "국민건강보험공단" in prompt
    assert f"{8 * generate.CHARS_PER_MINUTE}자" in prompt
    assert "퇴직 후 건보료 폭탄" in prompt and "임의계속가입 신청 기한" in prompt and "건보료 부과체계 개편" in prompt


def test_build_prompt_without_research(topic):
    assert "조사 자료" not in generate.build_prompt(topic)


def test_render_markdown(topic):
    md = generate.render_markdown(topic, _plan())
    assert md.startswith("# 퇴직 후 건보료, 이렇게 줄였습니다")
    assert "약 2분 0초" in md
    assert "#건강보험 #퇴직" in md
    assert "- [ ] 임의계속가입 최대 36개월 → 국민건강보험공단" in md
    assert "변경되거나 합성된 콘텐츠" in md


class _FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


def _fake_client(message, captured):
    def stream(**kwargs):
        captured.update(kwargs)
        return _FakeStream(message)

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


def test_generate_plan_request_shape(topic):
    captured = {}
    plan = _plan()
    client = _fake_client(SimpleNamespace(stop_reason="end_turn", parsed_output=plan), captured)
    assert generate.generate_plan(topic, None, 10, client=client) is plan
    assert captured["model"] == generate.MODEL
    assert captured["output_format"] is generate.VideoPlan
    assert captured["fallbacks"] == "default"
    assert captured["system"] == generate.SYSTEM_PROMPT


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_generate_plan_errors(topic, stop_reason):
    client = _fake_client(SimpleNamespace(stop_reason=stop_reason, parsed_output=None), {})
    with pytest.raises(RuntimeError):
        generate.generate_plan(topic, None, 10, client=client)
