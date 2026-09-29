"""독자 채점 장부: 에이전트가 고른 표현이 실제 독자(시청자)에게 도움이 됐는지 배운다.

에이전트끼리 '좋다'고 합의한 결과만 쌓으면 독자가 아니라 에이전트 취향에 맞춰진다.
그래서 이 장부는 에이전트 판단과 독자 결과를 따로 적고, 둘이 얼마나 맞는지를 잰다.

원칙
1. 에이전트 판단은 '예측'으로만 적는다. 정답은 독자 결과(YouTube A/B 테스트, 독자 패널)에서만 나온다.
2. 예측은 결과를 보기 전에 적는다. 결과가 들어온 선택에는 예측을 더 받지 않는다.
3. 에이전트는 서로의 예측을 보지 않고 따로 적는다. (합의가 서로 따라 하기가 되지 않게)
4. 시험에는 에이전트가 아무도 고르지 않은 후보를 하나 넣는다. 에이전트가 틀렸는지 알 방법은 그것뿐이다.
5. 확실하지 않은 결과는 '미확정'으로 둔다. 비교의 상당수는 '차이 없음'으로 끝난다.

흐름
  script → feedback new(후보 등록·표현 유형 태그) → feedback predict(에이전트별 예측)
  → feedback pick(A/B에 올릴 후보) → YouTube A/B 테스트 또는 독자 패널
  → feedback result(독자 결과) → feedback report(에이전트 보정·표현 유형별 학습)
  → 다음 script 프롬프트에는 독자가 확인해 준 것만 넣는다 (lessons)
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .benchmark import TITLE_PATTERNS

DEFAULT_LEDGER = "feedback"
SLOTS = {"title": "제목", "thumbnail": "썸네일 문구", "hook": "첫 문장", "scene": "장면 표현"}
AB_VERDICTS = {"winner": "승자 있음", "same": "차이 없음", "inconclusive": "판정 불가"}
RELIABLE_P = 0.9  # 이 확률 이상일 때만 '확인'으로 본다
MIN_TAG_N = 5  # 표현 유형은 비교가 이만큼 쌓여야 '확인'을 붙인다 (3승 0패로 결론 내지 않게)
MIN_AGENT_N = 10  # 채점된 선택이 이보다 적으면 에이전트 적중률 판단을 미룬다
LABELS = "가나다라마바사아자차"


def now_iso() -> str:
    # 예측과 결과의 선후를 문자열로 비교하므로 어느 컴퓨터에서 적든 UTC로 통일한다
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slot_name(slot: str) -> str:
    return SLOTS.get(slot, slot)


# ---------------------------------------------------------------- 후보 등록


def auto_tags(text: str) -> list[str]:
    """벤치마크와 같은 제목 구조 이름으로 태그를 붙인다. 그래야 경쟁 채널·에이전트·우리 독자를 같은 말로 비교할 수 있다."""
    return [name for name, regex, _ in TITLE_PATTERNS if re.search(regex, text)]


def options_from_plan(plan: dict, slot: str) -> list[str]:
    """script가 저장한 기획안 JSON에서 후보를 꺼낸다."""
    field = {"title": "titles", "thumbnail": "thumbnail_texts"}.get(slot)
    if not field:
        raise ValueError(f"기획안에서 자동으로 꺼낼 수 있는 것은 제목(title)과 썸네일(thumbnail)뿐입니다: {slot}")
    return [t for t in plan.get(field, []) if t.strip()]


def new_decision(
    video: str, slot: str, texts: list[str], extra_tags: dict[str, list[str]] | None = None, now: str | None = None
) -> dict:
    if len(texts) < 2:
        raise ValueError("비교하려면 후보가 2개 이상 있어야 합니다.")
    if not re.fullmatch(r"\w+", video) or not re.fullmatch(r"\w+", slot):
        raise ValueError(f"아이템 id와 슬롯 이름은 글자·숫자·_만 쓸 수 있습니다: {video}, {slot}")
    extra_tags = extra_tags or {}
    options = []
    for i, text in enumerate(texts, 1):
        key = str(i)
        tags = auto_tags(text) + [t for t in extra_tags.get(key, []) if t]
        options.append({"key": key, "text": text, "tags": list(dict.fromkeys(tags))})
    return {
        "id": f"{video}-{slot}",
        "video": video,
        "slot": slot,
        "created_at": now or now_iso(),
        "options": options,
        "predictions": [],
        "tested": [],
        "outcome": None,
    }


def _path(ledger: Path, decision_id: str) -> Path:
    return Path(ledger) / f"{decision_id}.json"


def save(decision: dict, ledger: Path) -> Path:
    path = _path(ledger, decision["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load(decision_id: str, ledger: Path) -> dict:
    path = _path(ledger, decision_id)
    if not path.exists():
        raise ValueError(f"장부에 없는 선택입니다: {decision_id} ({path})")
    return json.loads(path.read_text(encoding="utf-8"))


def load_all(ledger: Path) -> list[dict]:
    ledger = Path(ledger)
    if not ledger.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ledger.glob("*.json"))]


def _keys(decision: dict) -> list[str]:
    return [o["key"] for o in decision["options"]]


def option(decision: dict, key: str) -> dict:
    return next(o for o in decision["options"] if o["key"] == key)


# ---------------------------------------------------------------- 에이전트 예측


def add_prediction(
    decision: dict, agent: str, pick: str, confidence: float | None = None, reason: str = "", now: str | None = None
) -> None:
    """에이전트 예측을 적는다. 독자 결과가 이미 있으면 거부한다 (결과를 본 뒤의 예측은 예측이 아니다)."""
    if decision.get("outcome"):
        raise ValueError(f"{decision['id']}에는 이미 독자 결과가 있습니다. 결과를 본 뒤의 예측은 받지 않습니다.")
    if pick not in _keys(decision):
        raise ValueError(f"후보 번호가 아닙니다: {pick} (가능: {', '.join(_keys(decision))})")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("확신도는 0~1 사이로 적어 주세요 (예: 0.6)")
    decision["predictions"] = [p for p in decision["predictions"] if p["agent"] != agent]
    decision["predictions"].append(
        {"agent": agent, "pick": pick, "confidence": confidence, "reason": reason, "at": now or now_iso()}
    )


def consensus(decision: dict) -> tuple[str | None, float]:
    """(에이전트가 가장 많이 고른 후보, 그 후보를 고른 비율). 동률이면 평균 확신도가 높은 쪽."""
    preds = decision.get("predictions") or []
    if not preds:
        return None, 0.0
    votes = Counter(p["pick"] for p in preds)

    def rank(key: str) -> tuple[int, float]:
        confs = [p["confidence"] for p in preds if p["pick"] == key and p["confidence"] is not None]
        return votes[key], sum(confs) / len(confs) if confs else 0.0

    top = max(votes, key=rank)
    return top, votes[top] / len(preds)


PREDICT_SYSTEM = """\
당신은 한국 유튜브 채널의 표현 후보가 실제 시청자에게 어떤 반응을 얻을지 예측합니다.
시청자는 40~50대 한국인 전체입니다. 특정 인물을 연기하지 말고, 이 연령대 시청자 전체의 평균적인 반응을 예측하세요.

- 판정 기준은 '좋은 글'이 아니라 독자 행동입니다. 제목·썸네일은 YouTube A/B 테스트가 클릭 수가 아니라
  노출당 시청 시간(시청 시간 점유율)으로 승자를 정합니다. 클릭만 부르고 금방 떠나게 하는 표현은 집니다.
- 첫 문장·장면 표현은 끝까지 보게 하는지, 내용을 이해하고 써먹게 하는지로 판단합니다.
- 실제 비교의 상당수는 '차이 없음'으로 끝납니다. 확신도는 당신이 고른 후보가 실제로 이길 확률입니다.
  후보가 k개면 아무렇게나 골라도 1/k입니다. 근거가 약하면 1/k에 가깝게 적으세요.
"""


def build_predict_prompt(decision: dict, order: list[str]) -> str:
    """후보를 섞은 순서(order)로 가·나·다 이름을 붙여 보여 준다. 원래 순서와 다른 에이전트 예측은 보여 주지 않는다."""
    lines = [f"{LABELS[i]}. {option(decision, key)['text']}" for i, key in enumerate(order)]
    return (
        f"다음은 같은 영상의 {_slot_name(decision['slot'])} 후보 {len(order)}개입니다.\n\n"
        + "\n".join(lines)
        + f"\n\n40~50대 시청자에게 가장 좋은 반응을 얻을 후보 하나를 고르세요. pick에는 {LABELS[0]}~{LABELS[len(order) - 1]} 중 하나를,"
        " confidence에는 그 후보가 실제로 이길 확률(0~1)을, reason에는 한두 문장 근거를 적으세요."
    )


def auto_predict(decision: dict, agent: str = "claude", rng: random.Random | None = None, client=None) -> dict:
    """Claude에게 따로(다른 에이전트 예측 없이), 후보 순서를 섞어서(위치 편향 방지) 예측을 받는다."""
    from pydantic import BaseModel

    from .generate import call_structured

    class Prediction(BaseModel):
        pick: str
        confidence: float
        reason: str

    order = _keys(decision)
    (rng or random.Random()).shuffle(order)
    result = call_structured(PREDICT_SYSTEM, build_predict_prompt(decision, order), Prediction, client)
    pick = label_to_key(result.pick, order)
    add_prediction(decision, agent, pick, max(0.0, min(1.0, result.confidence)), result.reason)
    return decision["predictions"][-1]


def label_to_key(label: str, order: list[str]) -> str:
    """모델이 답한 '나' 또는 '나.' 같은 이름을 섞기 전 후보 번호로 되돌린다."""
    first = label.strip()[:1]
    if not first or first not in LABELS[: len(order)]:
        raise RuntimeError(f"예측 결과를 해석하지 못했습니다: {label!r}")
    return order[LABELS.index(first)]


# ---------------------------------------------------------------- 시험 후보 고르기


def _beta_draw(rng: random.Random, wins: int, losses: int) -> float:
    return rng.betavariate(1 + wins, 1 + losses)


def _sample_score(opt: dict, slot: str, model: dict, rng: random.Random) -> float:
    """독자 결과로 배운 표현 유형 모델에서 이 후보의 '독자 선호도'를 한 번 뽑는다 (톰슨 샘플링)."""
    tags = opt.get("tags") or []
    if not tags:
        return _beta_draw(rng, 0, 0)
    draws = [_beta_draw(rng, *model.get((slot, t), (0, 0))) for t in tags]
    return sum(draws) / len(draws)


def pick_test_options(decision: dict, model: dict, max_n: int = 3, rng: random.Random | None = None) -> list[str]:
    """YouTube A/B 테스트(최대 3개)나 독자 패널에 올릴 후보를 고른다.

    1자리: 에이전트 합의 후보 (에이전트가 맞는지 채점하려면 반드시 들어가야 한다)
    2자리: 에이전트가 아무도 고르지 않은 후보 중 독자 모델이 뽑은 것 (반대 후보)
    나머지: 독자 모델 톰슨 샘플링 순서 (아직 모르는 표현 유형도 가끔 뽑힌다)
    """
    if decision.get("outcome"):
        raise ValueError(f"{decision['id']}에는 이미 독자 결과가 있습니다. 다시 시험하려면 feedback new로 새 선택을 만드세요.")
    if not decision.get("predictions"):
        raise ValueError(f"{decision['id']}: 시험 전에 에이전트 예측을 먼저 적으세요 (feedback predict).")
    if max_n < 2:
        raise ValueError("시험 후보는 2개 이상이어야 합니다.")
    rng = rng or random.Random()
    favorite, _ = consensus(decision)
    voted = {p["pick"] for p in decision["predictions"]}
    scores = {o["key"]: _sample_score(o, decision["slot"], model, rng) for o in decision["options"]}
    by_score = sorted(scores, key=scores.get, reverse=True)
    chosen = [favorite]
    contrarian = [k for k in by_score if k not in voted]
    if contrarian:
        chosen.append(contrarian[0])
    chosen += [k for k in by_score if k not in chosen]
    return chosen[:max_n]


# ---------------------------------------------------------------- 독자 결과


def prob_better(a: tuple[int, int], b: tuple[int, int], draws: int = 4000, seed: int = 0) -> float:
    """(성공, 시도) a의 실제 비율이 b보다 높을 확률. 베타 사후분포에서 뽑아 센다 (결과가 매번 같도록 seed 고정)."""
    rng = random.Random(seed)
    (sa, na), (sb, nb) = a, b
    wins = sum(rng.betavariate(1 + sa, 1 + na - sa) > rng.betavariate(1 + sb, 1 + nb - sb) for _ in range(draws))
    return wins / draws


def beta_p_above_half(wins: int, losses: int) -> float:
    """Beta(1+wins, 1+losses)가 0.5보다 클 확률 (정확한 값). = P(Binomial(wins+losses+1, 0.5) ≤ wins)."""
    n = wins + losses + 1
    return sum(math.comb(n, i) for i in range(wins + 1)) / 2**n


def record_result(
    decision: dict,
    source: str,
    values: dict,
    verdict: str | None = None,
    note: str = "",
    now: str | None = None,
    replace: bool = False,
) -> dict:
    """독자 결과를 적는다.

    source="ab":    values = {후보: 시청 시간 점유율(%)}, verdict = YouTube 판정 (winner/same/inconclusive)
    source="panel": values = {후보: (고른 사람 또는 맞힌 사람, 전체 인원)}. 1·2위 차이가 확실할 때만 승자로 본다.
    """
    if decision.get("outcome") and not replace:
        raise ValueError(f"{decision['id']}에는 이미 독자 결과가 있습니다. 바꾸려면 --replace.")
    keys = list(values)
    if len(keys) < 2:
        raise ValueError("독자 결과는 후보 2개 이상에 대해 적어야 합니다.")
    unknown = [k for k in keys if k not in _keys(decision)]
    if unknown:
        raise ValueError(f"후보 번호가 아닙니다: {', '.join(unknown)}")

    outcome = {"source": source, "tested": keys, "values": values, "note": note, "at": now or now_iso()}
    if source == "ab":
        if verdict not in AB_VERDICTS:
            raise ValueError(f"YouTube 판정은 {', '.join(AB_VERDICTS)} 중 하나로 적어 주세요.")
        outcome["verdict"] = verdict
        outcome["winner"] = max(keys, key=lambda k: values[k]) if verdict == "winner" else None
    elif source == "panel":
        for k, (s, n) in values.items():
            if not 0 <= s <= n or n <= 0:
                raise ValueError(f"패널 결과는 '맞힌(고른) 수/전체 인원'으로 적어 주세요: {k}={s}/{n}")
        rate = {k: s / n for k, (s, n) in values.items()}
        top, second = sorted(keys, key=lambda k: rate[k], reverse=True)[:2]
        p = prob_better(tuple(values[top]), tuple(values[second]))
        outcome["p_top_better"] = round(p, 3)
        outcome["verdict"] = "winner" if p >= RELIABLE_P else "inconclusive"
        outcome["winner"] = top if p >= RELIABLE_P else None
    else:
        raise ValueError(f"결과 출처는 ab 또는 panel 입니다: {source}")
    decision["outcome"] = outcome
    decision["tested"] = keys
    return outcome


# ---------------------------------------------------------------- 채점과 학습


def _valid_predictions(decision: dict) -> list[dict]:
    """결과가 적히기 전에 적힌 예측만. (파일을 직접 고쳐 결과 뒤에 넣은 예측은 채점에서 뺀다)"""
    out = decision.get("outcome")
    preds = decision.get("predictions") or []
    return [p for p in preds if not out or p["at"] <= out["at"]]


def _z(hits: float, chance: float, var: float) -> float:
    return (hits - chance) / math.sqrt(var) if var > 0 else 0.0


def _verdict(n: int, z: float) -> str:
    if n < MIN_AGENT_N:
        return f"아직 이르다 ({n}/{MIN_AGENT_N})"
    if z >= 1.64:
        return "우연보다 잘 맞힘"
    if z <= -1.64:
        return "우연보다 못 맞힘"
    return "우연과 구별 안 됨"


def agent_scores(decisions: list[dict]) -> list[dict]:
    """에이전트별로 '독자 승자를 맞힌 비율'을 우연(1/후보 수)과 비교한다."""
    rows: dict[str, dict] = {}
    for d in decisions:
        out = d.get("outcome")
        if not out:
            continue
        tested = out["tested"]
        for p in _valid_predictions(d):
            r = rows.setdefault(
                p["agent"], {"agent": p["agent"], "n": 0, "hits": 0, "chance": 0.0, "var": 0.0, "confs": [], "no_diff": 0, "untested": 0}
            )
            if p["pick"] not in tested:
                r["untested"] += 1
            elif out["winner"]:
                q = 1 / len(tested)
                r["n"] += 1
                r["hits"] += p["pick"] == out["winner"]
                r["chance"] += q
                r["var"] += q * (1 - q)
                if p["confidence"] is not None:
                    r["confs"].append(p["confidence"])
            elif out["verdict"] == "same":
                r["no_diff"] += 1
    result = []
    for r in rows.values():
        z = _z(r["hits"], r["chance"], r["var"])
        confs = r.pop("confs")
        r["mean_conf"] = round(sum(confs) / len(confs), 2) if confs else None
        r["verdict"] = _verdict(r["n"], z)
        r.pop("var")
        result.append(r)
    return sorted(result, key=lambda r: r["agent"])


def consensus_scores(decisions: list[dict]) -> list[dict]:
    """합의 강도별로 '합의 후보가 독자 승자였던 비율'. 만장일치도 우연 수준이면 합의는 확신일 뿐 독자 예측력이 아니다."""
    buckets: dict[str, dict] = {}
    for d in decisions:
        out = d.get("outcome")
        preds = _valid_predictions(d)
        if not out or not out["winner"] or not preds:
            continue
        fav, strength = consensus({"predictions": preds})
        if fav not in out["tested"]:
            continue
        name = "에이전트 1개" if len(preds) == 1 else ("만장일치" if strength == 1 else "의견 갈림")
        b = buckets.setdefault(name, {"bucket": name, "n": 0, "hits": 0, "chance": 0.0})
        b["n"] += 1
        b["hits"] += fav == out["winner"]
        b["chance"] += 1 / len(out["tested"])
    order = ["만장일치", "의견 갈림", "에이전트 1개"]
    return [buckets[k] for k in order if k in buckets]


def _pairwise(decision: dict, winner: str, others: list[str], model: dict) -> None:
    """승자 후보와 진 후보를 짝지어, 한쪽에만 있는 표현 유형에 승·패를 준다."""
    slot = decision["slot"]
    win_tags = set(option(decision, winner)["tags"])
    for k in others:
        lose_tags = set(option(decision, k)["tags"])
        for t in win_tags - lose_tags:
            w, l = model.get((slot, t), (0, 0))
            model[(slot, t)] = (w + 1, l)
        for t in lose_tags - win_tags:
            w, l = model.get((slot, t), (0, 0))
            model[(slot, t)] = (w, l + 1)


def reader_model(decisions: list[dict]) -> dict[tuple[str, str], tuple[int, int]]:
    """(슬롯, 표현 유형) → 독자 결과에서의 (승, 패). 승자가 확실한 결과만 쓴다."""
    model: dict = {}
    for d in decisions:
        out = d.get("outcome")
        if out and out["winner"]:
            _pairwise(d, out["winner"], [k for k in out["tested"] if k != out["winner"]], model)
    return model


def agent_model(decisions: list[dict]) -> dict[tuple[str, str], tuple[int, int]]:
    """(슬롯, 표현 유형) → 에이전트 예측에서의 (승, 패). 에이전트 '취향'을 독자와 같은 방식으로 잰다."""
    model: dict = {}
    for d in decisions:
        for p in _valid_predictions(d):
            _pairwise(d, p["pick"], [k for k in _keys(d) if k != p["pick"]], model)
    return model


def tag_table(decisions: list[dict], benchmark: dict | None = None) -> list[dict]:
    """표현 유형별로 독자·에이전트·경쟁 채널 히트를 나란히 놓는다."""
    readers, agents = reader_model(decisions), agent_model(decisions)
    lifts = {p["pattern"]: p.get("lift") for p in (benchmark or {}).get("patterns", [])}
    rows = []
    for slot, tag in sorted(set(readers) | set(agents)):
        rw, rl = readers.get((slot, tag), (0, 0))
        aw, al = agents.get((slot, tag), (0, 0))
        p = beta_p_above_half(rw, rl) if rw + rl else None
        agent_rate = aw / (aw + al) if aw + al else None
        if p is None:
            status = "독자 결과 없음"
        elif rw + rl < MIN_TAG_N:
            status = f"미확정 (비교 {rw + rl}/{MIN_TAG_N})"
        elif p >= RELIABLE_P:
            status = "독자 선호 (확인)"
        elif p <= 1 - RELIABLE_P:
            status = "독자 비선호 (확인)"
        else:
            status = "미확정"
        gap = (
            status.endswith("(확인)")
            and agent_rate is not None
            and ((p >= RELIABLE_P and agent_rate < 0.5) or (p <= 1 - RELIABLE_P and agent_rate > 0.5))
        )
        rows.append(
            {
                "slot": slot,
                "tag": tag,
                "reader_wins": rw,
                "reader_losses": rl,
                "reader_p": None if p is None else round(p, 2),
                "agent_rate": None if agent_rate is None else round(agent_rate, 2),
                "benchmark_lift": lifts.get(tag) if slot == "title" else None,
                "status": status,
                "gap": gap,
            }
        )
    return rows


def disagreements(decisions: list[dict]) -> list[dict]:
    """에이전트 합의 후보와 독자 승자가 다른 선택. 가장 배울 게 많은 사례다."""
    rows = []
    for d in decisions:
        out = d.get("outcome")
        preds = _valid_predictions(d)
        if not out or not out["winner"] or not preds:
            continue
        fav, strength = consensus({"predictions": preds})
        if fav != out["winner"] and fav in out["tested"]:
            rows.append(
                {
                    "id": d["id"],
                    "slot": d["slot"],
                    "agents": option(d, fav)["text"],
                    "readers": option(d, out["winner"])["text"],
                    "strength": strength,
                    "reasons": [f"{p['agent']}: {p['reason']}" for p in preds if p["pick"] == fav and p["reason"]],
                }
            )
    return rows


def lessons(decisions: list[dict]) -> str:
    """다음 기획안 프롬프트에 넣을 '독자가 확인해 준 것'. 확인되지 않은 것은 넣지 않는다."""
    rows = [r for r in tag_table(decisions) if r["status"] in ("독자 선호 (확인)", "독자 비선호 (확인)")]
    if not rows:
        return ""
    lines = []
    for r in rows:
        tone = "독자가 더 오래 봤음" if r["status"].startswith("독자 선호") else "독자 반응이 약했음"
        lines.append(f"- {_slot_name(r['slot'])} '{r['tag']}' 구조: {tone} (비교 {r['reader_wins']}승 {r['reader_losses']}패)")
    lines.append(
        "- 위 목록은 우리 채널 독자 실험에서 확실하게 나온 것뿐이다. 나머지는 아직 모른다."
        " 후보를 만들 때 확인된 구조만 쓰지 말고, 확인 안 된 구조도 계속 섞는다."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------- 보고서


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def status_lines(decisions: list[dict]) -> list[str]:
    lines = []
    for d in decisions:
        agents = ", ".join(p["agent"] for p in d.get("predictions") or []) or "예측 없음"
        out = d.get("outcome")
        if out:
            state = f"결과 {AB_VERDICTS.get(out['verdict'], out['verdict'])}"
            if out["winner"]:
                state += f" (승자 {out['winner']}번)"
        elif d.get("tested"):
            state = f"시험 중 ({', '.join(d['tested'])}번)"
        else:
            state = "시험 전"
        lines.append(f"{d['id']:<16} 후보 {len(d['options'])}개 | 예측: {agents} | {state}")
    return lines


def report_markdown(decisions: list[dict], benchmark: dict | None = None, today: str | None = None) -> str:
    today = today or datetime.now().date().isoformat()
    outs = [d["outcome"] for d in decisions if d.get("outcome")]
    verdicts = Counter(o["verdict"] for o in outs)
    cons = consensus_scores(decisions)
    all_n = sum(b["n"] for b in cons)
    all_hits = sum(b["hits"] for b in cons)
    all_chance = sum(b["chance"] for b in cons)
    lines = [
        f"# 독자 채점 보고서 ({today})",
        "",
        "에이전트 판단은 예측으로만 적고, 정답은 독자 결과에서만 가져왔습니다.",
        f"'확인'은 비교가 {MIN_TAG_N}번 이상 쌓이고 확률이 {RELIABLE_P * 100:.0f}% 이상일 때만 붙입니다.",
        "",
        "## 0. 한눈에",
        "",
        f"- 장부의 선택: {len(decisions)}개 / 독자 결과: {len(outs)}개"
        f" (승자 있음 {verdicts['winner']}, 차이 없음 {verdicts['same']}, 판정 불가 {verdicts['inconclusive']})",
        f"- 에이전트 합의 후보가 독자 승자였던 비율: {all_hits}/{all_n}"
        + (f" (우연이면 약 {all_chance:.1f}개)" if all_n else ""),
        "",
        "## 1. 에이전트 예측 vs 독자 결과",
        "",
        "| 에이전트 | 채점된 선택 | 맞힘 | 우연 기대 | 평균 확신도 | 독자는 차이 없음 | 시험에서 빠짐 | 판단 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in agent_scores(decisions):
        lines.append(
            f"| {r['agent']} | {r['n']} | {r['hits']} | {r['chance']:.1f} | {_pct(r['mean_conf'])}"
            f" | {r['no_diff']} | {r['untested']} | {r['verdict']} |"
        )
    lines += [
        "",
        "- '평균 확신도'가 실제 맞힌 비율보다 훨씬 높으면 그 에이전트는 과신하고 있습니다.",
        "- '독자는 차이 없음'이 많으면 에이전트가 중요하다고 본 차이를 독자는 느끼지 못한 것입니다.",
        "",
        "## 2. 합의 강도별 적중",
        "",
        "| 합의 | 채점된 선택 | 합의 후보가 승자 | 우연 기대 |",
        "|---|---|---|---|",
        *[f"| {b['bucket']} | {b['n']} | {b['hits']} | {b['chance']:.1f} |" for b in cons],
        "",
        "만장일치의 적중이 우연 기대와 비슷하다면, 합의는 에이전트끼리의 확신일 뿐 독자를 예측하는 힘이 아닙니다.",
        "",
        "## 3. 표현 유형별: 우리 독자 · 에이전트 · 경쟁 채널",
        "",
        "| 슬롯 | 표현 유형 | 독자 승-패 | 독자 선호 확률 | 에이전트 선호율 | 경쟁 채널 히트 배수 | 판정 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in tag_table(decisions, benchmark):
        lift = "-" if r["benchmark_lift"] is None else f"{r['benchmark_lift']}배"
        flag = " ⚠ 에이전트와 반대" if r["gap"] else ""
        lines.append(
            f"| {_slot_name(r['slot'])} | {r['tag']} | {r['reader_wins']}-{r['reader_losses']} | {_pct(r['reader_p'])}"
            f" | {_pct(r['agent_rate'])} | {lift} | {r['status']}{flag} |"
        )
    lines += [
        "",
        "- 독자 선호 확률: 이 유형이 들어간 후보가 안 들어간 후보를 이길 확률 (50%면 모름).",
        "- 에이전트 선호율: 에이전트가 이 유형이 들어간 후보를 고른 비율 (같은 짝 비교 기준).",
        "",
        "## 4. 에이전트와 독자가 갈린 선택",
        "",
    ]
    dis = disagreements(decisions)
    if not dis:
        lines.append("아직 없습니다.")
    for r in dis:
        lines += [
            f"### {r['id']} ({_slot_name(r['slot'])}, 합의 {r['strength'] * 100:.0f}%)",
            "",
            f"- 에이전트가 고른 것: {r['agents']}",
            f"- 독자가 고른 것: **{r['readers']}**",
            *[f"- 근거였던 말: {x}" for x in r["reasons"]],
            "",
        ]
    lines += ["", "## 5. 장부 상태", "", "```", *status_lines(decisions), "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- 명령줄 입력 해석


def parse_ab(text: str) -> dict[str, float]:
    """'1=41,3=35,5=24' → {'1': 41.0, ...} (시청 시간 점유율 %)."""
    values = {}
    for part in text.split(","):
        if not part.strip():
            continue
        key, _, value = part.partition("=")
        try:
            values[key.strip()] = float(value.strip().rstrip("%"))
        except ValueError:
            raise ValueError(f"A/B 결과는 '후보=점유율' 형식입니다 (예: 1=41,3=35): {part}") from None
    return values


def parse_panel(text: str) -> dict[str, tuple[int, int]]:
    """'1=4/5,2=1/5' → {'1': (4, 5), '2': (1, 5)}."""
    values = {}
    for part in text.split(","):
        if not part.strip():
            continue
        key, _, value = part.partition("=")
        m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", value)
        if not m:
            raise ValueError(f"패널 결과는 '후보=맞힌수/인원' 형식입니다 (예: 1=4/5,2=1/5): {part}")
        values[key.strip()] = (int(m.group(1)), int(m.group(2)))
    return values


def parse_tags(items: list[str] | None) -> dict[str, list[str]]:
    """['1=감정;질문', '2=숫자 목록'] → {'1': ['감정', '질문'], '2': ['숫자 목록']}."""
    tags: dict[str, list[str]] = {}
    for item in items or []:
        key, _, value = item.partition("=")
        tags.setdefault(key.strip(), []).extend(t.strip() for t in value.split(";") if t.strip())
    return tags
