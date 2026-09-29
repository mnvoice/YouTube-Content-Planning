import json
import random
from types import SimpleNamespace

import pytest

from ytplan import cli, feedback, generate
from ytplan.topics import load_topics, select

T0 = "2026-10-01T00:00:00+00:00"
T1 = "2026-10-02T00:00:00+00:00"
T2 = "2026-10-20T00:00:00+00:00"

TITLES = [
    "퇴직 후 건보료, 합법적으로 줄이는 3가지 방법",  # 숫자 목록, 방법·비법
    "퇴직하고 건보료 신청 늦게 해서 후회한 이유",  # 후회·실수
    "퇴직 후 건보료, 정말 폭탄일까요?",  # 질문
]


def _decision(video="M03", picks=("1", "1"), winner_key="2", verdict="winner", tested=("1", "2", "3")):
    d = feedback.new_decision(video, "title", TITLES, now=T0)
    for agent, pick in zip(("claude", "codex"), picks):
        feedback.add_prediction(d, agent, pick, 0.6, "숫자와 이익이 분명", now=T1)
    shares = {k: (50.0 if k == winner_key else 25.0) for k in tested}
    feedback.record_result(d, "ab", shares, verdict, now=T2)
    return d


def test_auto_tags_use_benchmark_vocabulary():
    assert feedback.auto_tags(TITLES[0]) == ["숫자 목록", "나이·세대 호명", "방법·비법"]
    assert "후회·실수" in feedback.auto_tags(TITLES[1])
    assert "질문" in feedback.auto_tags(TITLES[2])


def test_new_decision_keys_tags_and_extra_tags():
    d = feedback.new_decision("M03", "hook", ["고지서 장면으로 시작", "통계로 시작"], {"1": ["구체 장면"]}, now=T0)
    assert d["id"] == "M03-hook"
    assert [o["key"] for o in d["options"]] == ["1", "2"]
    assert "구체 장면" in d["options"][0]["tags"]
    with pytest.raises(ValueError):
        feedback.new_decision("M03", "title", ["하나뿐"])


def test_options_from_plan():
    plan = {"titles": ["a", " ", "b"], "thumbnail_texts": ["x", "y"]}
    assert feedback.options_from_plan(plan, "title") == ["a", "b"]
    assert feedback.options_from_plan(plan, "thumbnail") == ["x", "y"]
    with pytest.raises(ValueError):
        feedback.options_from_plan(plan, "hook")


def test_prediction_rules():
    d = feedback.new_decision("M03", "title", TITLES, now=T0)
    with pytest.raises(ValueError):
        feedback.add_prediction(d, "claude", "9")
    with pytest.raises(ValueError):
        feedback.add_prediction(d, "claude", "1", confidence=1.5)
    feedback.add_prediction(d, "claude", "1", 0.6, now=T1)
    feedback.add_prediction(d, "claude", "2", 0.5, now=T1)  # 결과 전에는 고쳐 적을 수 있다
    assert [(p["agent"], p["pick"]) for p in d["predictions"]] == [("claude", "2")]
    feedback.record_result(d, "ab", {"1": 40, "2": 60}, "winner", now=T2)
    with pytest.raises(ValueError, match="결과를 본 뒤"):
        feedback.add_prediction(d, "codex", "2")


def test_consensus_majority_then_confidence():
    d = feedback.new_decision("M03", "title", TITLES, now=T0)
    assert feedback.consensus(d) == (None, 0.0)
    feedback.add_prediction(d, "a", "1", 0.4, now=T1)
    feedback.add_prediction(d, "b", "2", 0.8, now=T1)
    assert feedback.consensus(d) == ("2", 0.5)  # 1표씩이면 확신도가 높은 쪽
    feedback.add_prediction(d, "c", "1", 0.3, now=T1)
    assert feedback.consensus(d)[0] == "1"


def test_pick_test_options_includes_favorite_and_contrarian():
    d = feedback.new_decision("M03", "title", TITLES + ["퇴직 1년 전이신 분 꼭 보세요"], now=T0)
    with pytest.raises(ValueError, match="예측을 먼저"):
        feedback.pick_test_options(d, {})
    feedback.add_prediction(d, "claude", "1", 0.6, now=T1)
    feedback.add_prediction(d, "codex", "2", 0.5, now=T1)
    for seed in range(20):
        chosen = feedback.pick_test_options(d, {}, 3, random.Random(seed))
        assert len(chosen) == 3 and len(set(chosen)) == 3
        assert chosen[0] == "1"  # 에이전트 합의 후보는 채점하려면 반드시 들어간다
        assert chosen[1] in {"3", "4"}  # 아무 에이전트도 고르지 않은 후보
    assert feedback.pick_test_options(d, {}, 2, random.Random(1)) == feedback.pick_test_options(d, {}, 2, random.Random(1))


def test_pick_test_options_follows_reader_model():
    d = feedback.new_decision("M03", "title", TITLES, now=T0)
    feedback.add_prediction(d, "claude", "1", 0.6, now=T1)
    model = {("title", "후회·실수"): (30, 0), ("title", "질문"): (0, 30)}
    assert feedback.pick_test_options(d, model, 2, random.Random(0)) == ["1", "2"]


def test_record_result_ab():
    d = feedback.new_decision("M03", "title", TITLES, now=T0)
    out = feedback.record_result(d, "ab", {"1": 31, "2": 45, "3": 24}, "winner", now=T2)
    assert out["winner"] == "2" and d["tested"] == ["1", "2", "3"]
    with pytest.raises(ValueError, match="이미 독자 결과"):
        feedback.record_result(d, "ab", {"1": 50, "2": 50}, "same")
    out = feedback.record_result(d, "ab", {"1": 50, "2": 50}, "same", replace=True)
    assert out["winner"] is None
    with pytest.raises(ValueError):
        feedback.record_result(d, "ab", {"1": 50, "2": 50}, "tie", replace=True)
    with pytest.raises(ValueError):
        feedback.record_result(d, "ab", {"1": 50, "9": 50}, "winner", replace=True)


def test_record_result_panel_needs_clear_gap():
    d = feedback.new_decision("M03", "hook", ["A", "B"], now=T0)
    out = feedback.record_result(d, "panel", {"1": (5, 5), "2": (0, 5)})
    assert out["winner"] == "1" and out["p_top_better"] >= feedback.RELIABLE_P
    out = feedback.record_result(d, "panel", {"1": (3, 5), "2": (2, 5)}, replace=True)
    assert out["winner"] is None and out["verdict"] == "inconclusive"
    with pytest.raises(ValueError):
        feedback.record_result(d, "panel", {"1": (6, 5), "2": (2, 5)}, replace=True)


def test_beta_p_above_half_exact():
    assert feedback.beta_p_above_half(0, 0) == 0.5
    assert feedback.beta_p_above_half(1, 0) == 0.75
    assert feedback.beta_p_above_half(3, 0) == pytest.approx(0.9375)
    assert feedback.beta_p_above_half(0, 3) == pytest.approx(0.0625)


def test_agent_scores_and_consensus_against_readers():
    ds = [_decision(winner_key="2") for _ in range(9)] + [_decision(winner_key="1")]
    ds.append(_decision(winner_key="1", verdict="same"))
    scores = {r["agent"]: r for r in feedback.agent_scores(ds)}
    assert scores["claude"]["n"] == 10 and scores["claude"]["hits"] == 1
    assert scores["claude"]["chance"] == pytest.approx(10 / 3)
    assert scores["claude"]["no_diff"] == 1
    assert scores["claude"]["verdict"] == "우연과 구별 안 됨"
    assert scores["claude"]["mean_conf"] == 0.6
    cons = feedback.consensus_scores(ds)
    assert cons == [{"bucket": "만장일치", "n": 10, "hits": 1, "chance": pytest.approx(10 / 3)}]


def test_agent_verdict_needs_enough_decisions():
    ds = [_decision(winner_key="1") for _ in range(3)]
    assert feedback.agent_scores(ds)[0]["verdict"] == "아직 이르다 (3/10)"
    ds = [_decision(winner_key="1") for _ in range(10)]
    assert feedback.agent_scores(ds)[0]["verdict"] == "우연보다 잘 맞힘"


def test_predictions_written_after_result_are_not_scored():
    d = _decision(winner_key="2")
    d["predictions"].append({"agent": "late", "pick": "2", "confidence": 0.9, "reason": "", "at": "2026-11-01T00:00:00+00:00"})
    assert "late" not in {r["agent"] for r in feedback.agent_scores([d])}


def test_untested_pick_is_counted_separately():
    d = _decision(picks=("3", "3"), winner_key="2", tested=("1", "2"))
    r = feedback.agent_scores([d])[0]
    assert r["n"] == 0 and r["untested"] == 1


def test_tag_table_confirms_and_flags_agent_reader_gap():
    ds = [_decision(winner_key="2") for _ in range(6)]
    rows = {r["tag"]: r for r in feedback.tag_table(ds)}
    regret = rows["후회·실수"]
    assert (regret["reader_wins"], regret["reader_losses"]) == (12, 0)
    assert regret["status"] == "독자 선호 (확인)"
    assert regret["agent_rate"] == 0.0 and regret["gap"]
    assert rows["숫자 목록"]["status"] == "독자 비선호 (확인)" and rows["숫자 목록"]["gap"]
    assert "나이·세대 호명" not in rows  # 모든 후보에 있는 유형은 비교에서 빠진다


def test_tag_needs_minimum_comparisons():
    rows = {r["tag"]: r for r in feedback.tag_table([_decision(winner_key="2")])}
    assert rows["후회·실수"]["status"] == "미확정 (비교 2/5)"


def test_tag_table_shows_benchmark_lift_for_titles():
    bench = {"patterns": [{"pattern": "후회·실수", "lift": 2.4}]}
    rows = {r["tag"]: r for r in feedback.tag_table([_decision()], bench)}
    assert rows["후회·실수"]["benchmark_lift"] == 2.4


def test_lessons_only_confirmed():
    assert feedback.lessons([_decision()]) == ""
    text = feedback.lessons([_decision(winner_key="2") for _ in range(6)])
    assert "제목 '후회·실수' 구조: 독자가 더 오래 봤음 (비교 12승 0패)" in text
    assert "제목 '숫자 목록' 구조: 독자 반응이 약했음" in text
    assert "확인 안 된 구조도 계속 섞는다" in text


def test_disagreements_and_report():
    ds = [_decision(winner_key="2"), _decision(video="H01", winner_key="1")]
    dis = feedback.disagreements(ds)
    assert [r["id"] for r in dis] == ["M03-title"]
    assert dis[0]["readers"] == TITLES[1]
    md = feedback.report_markdown(ds, today="2026-10-21")
    assert md.startswith("# 독자 채점 보고서 (2026-10-21)")
    assert "에이전트 합의 후보가 독자 승자였던 비율: 1/2" in md
    assert "| 만장일치 | 2 | 1 | 0.7 |" in md
    assert "**퇴직하고 건보료 신청 늦게 해서 후회한 이유**" in md


def test_build_predict_prompt_hides_order_and_other_agents():
    d = feedback.new_decision("M03", "title", TITLES, now=T0)
    feedback.add_prediction(d, "codex", "1", 0.9, "비밀", now=T1)
    prompt = feedback.build_predict_prompt(d, ["3", "1", "2"])
    assert prompt.index(TITLES[2]) < prompt.index(TITLES[0]) < prompt.index(TITLES[1])
    assert "가. " + TITLES[2] in prompt
    assert "codex" not in prompt and "비밀" not in prompt


def test_auto_predict_asks_blind_and_maps_back():
    d = feedback.new_decision("M03", "title", TITLES, now=T0)
    feedback.add_prediction(d, "codex", "1", 0.9, "숫자형이 이김", now=T1)
    captured = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            answer = SimpleNamespace(pick="가", confidence=1.4, reason="후회형이 끝까지 보게 함")
            return SimpleNamespace(stop_reason="end_turn", parsed_output=answer)

    def stream(**kwargs):
        captured.update(kwargs)
        return Stream()

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    rng = random.Random(0)
    order = ["1", "2", "3"]
    random.Random(0).shuffle(order)
    p = feedback.auto_predict(d, "claude", rng, client)
    assert p["pick"] == order[0]  # '가'는 섞은 순서의 첫 후보
    assert p["confidence"] == 1.0
    prompt = captured["messages"][0]["content"]
    assert "codex" not in prompt and "숫자형이 이김" not in prompt
    assert captured["system"] == feedback.PREDICT_SYSTEM


def test_label_to_key_maps_back_through_shuffle():
    assert feedback.label_to_key("나", ["3", "1", "2"]) == "1"
    assert feedback.label_to_key(" 다. 후회형", ["3", "1", "2"]) == "2"
    for bad in ("", "  ", "라", "B"):
        with pytest.raises(RuntimeError):
            feedback.label_to_key(bad, ["3", "1", "2"])


def test_pick_refused_after_result_and_bad_names_refused():
    d = _decision()
    with pytest.raises(ValueError, match="이미 독자 결과"):
        feedback.pick_test_options(d, {})
    with pytest.raises(ValueError):
        feedback.new_decision("M03", "../x", ["a", "b"])


def test_parsers():
    assert feedback.parse_ab("1=41,3=35%, 5=24") == {"1": 41.0, "3": 35.0, "5": 24.0}
    assert feedback.parse_panel("1=4/5, 2=1/5") == {"1": (4, 5), "2": (1, 5)}
    assert feedback.parse_tags(["1=구체 장면;감정", "1=질문"]) == {"1": ["구체 장면", "감정", "질문"]}
    with pytest.raises(ValueError):
        feedback.parse_ab("1=많음")
    with pytest.raises(ValueError):
        feedback.parse_panel("1=4")


def test_build_prompt_includes_only_given_lessons():
    topic = select(load_topics(), ["M03"])[0]
    assert "독자 실험" not in generate.build_prompt(topic)
    prompt = generate.build_prompt(topic, lessons="- 제목 '후회·실수' 구조: 독자가 더 오래 봤음")
    assert "우리 채널 독자 실험에서 확인된 것" in prompt and "후회·실수" in prompt


def test_cli_flow(tmp_path, capsys):
    base = ["--ledger", str(tmp_path / "fb"), "--out", str(tmp_path / "out"), "--env-file", str(tmp_path / ".env")]
    scripts = tmp_path / "out" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "M03.json").write_text(json.dumps({"titles": TITLES}, ensure_ascii=False), encoding="utf-8")

    cli.main(base + ["feedback", "new", "M03"])
    with pytest.raises(SystemExit):  # 같은 선택을 실수로 덮어쓰지 않는다
        cli.main(base + ["feedback", "new", "M03"])
    cli.main(base + ["feedback", "predict", "M03-title", "--agent", "claude", "--pick", "1", "--confidence", "0.6"])
    cli.main(base + ["feedback", "pick", "M03-title", "--seed", "3"])
    cli.main(base + ["feedback", "result", "M03-title", "--ab", "1=30,2=50,3=20", "--verdict", "winner"])
    with pytest.raises(SystemExit):
        cli.main(base + ["feedback", "predict", "M03-title", "--agent", "codex", "--pick", "2"])
    cli.main(base + ["feedback", "report"])

    saved = json.loads((tmp_path / "fb" / "M03-title.json").read_text(encoding="utf-8"))
    assert saved["outcome"]["winner"] == "2"
    assert [p["agent"] for p in saved["predictions"]] == ["claude"]
    assert "독자 채점 보고서" in (tmp_path / "out" / "feedback_report.md").read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "(에이전트 합의)" in out and "반대 후보" in out
