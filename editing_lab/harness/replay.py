"""실제 사례 두 건을 하네스에 다시 넣어 기록 충실도를 잰다 (ACCEPTANCE.md의 C 기준).

사실 하나를 한 항목으로 세고, 다음 넷 중 하나로 분류한다.
  그대로   : 사실 그대로 넣었고 통과
  우회     : 사실과 다르게 바꿔 넣어야 통과 (그대로 넣었을 때의 결과를 함께 적음)
  자리없음 : 하네스에 넣을 칸이 없음
  보류     : 사실 그대로도, 바꿔서도 넣지 못함
따로 "사실 그대로 넣었을 때 거부된 항목 수"(C2)를 센다.

입력 사실은 고정한다(ACCEPTANCE.md 0-4). 하네스의 명령이 바뀌면 V1CLI 같은 어댑터만 새로 만든다.
책 원문은 임시 폴더에서만 쓰고, 출력에는 개수만 남긴다.

사용법: python editing_lab/harness/replay.py [--harness PATH] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
DEFAULT_HARNESS = Path(__file__).with_name("harness.py")
BOOK = LAB / "private/CASE-20261001-001/transcript.json"

# C4: 전용 기록 종류로 남아야 하는 8가지
DEDICATED = ("진행자 결정", "조정", "단계 생략", "반응 전 예상", "블라인드 배정", "판단 갱신", "창작 초고", "출처")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def prop(pid, target, reason="이유", ev="응용 판단"):
    return dict(proposal_id=pid, target=target, action="수정", reason=reason,
                expected_effect="[미검증 예상]", downside="반례", evidence_type=ev)


class V1CLI:
    """받은 판(v1)과 1단계 판(v1.1)의 명령줄 인터페이스."""

    def __init__(self, harness: Path, workdir: Path):
        self.harness = harness
        self.dir = workdir
        self.root = workdir / "case"
        self.n = 0

    def call(self, *args):
        r = subprocess.run([sys.executable, str(self.harness), "--case", str(self.root), *args],
                           capture_output=True, text=True)
        return r.returncode == 0, (r.stderr.strip().splitlines() or [""])[-1]

    def js(self, obj):
        self.n += 1
        p = self.dir / f"in_{self.n:03d}.json"
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return str(p)

    def file(self, data: bytes, name):
        p = self.dir / name
        p.write_bytes(data)
        return p


class Replay:
    def __init__(self, case_id, adapter):
        self.case_id = case_id
        self.a = adapter
        self.rows = []

    def no_slot(self, item, kind=None, note=""):
        self.rows.append(dict(case=self.case_id, item=item, kind=kind, status="자리없음",
                              truthful_rejected=False, note=note))

    def attempt(self, item, truthful, workaround=None, kind=None, note=""):
        """truthful: (명령 인자 목록,). workaround: (명령 인자 목록, 설명) 또는 None."""
        ok, msg = self.a.call(*truthful[0])
        if ok:
            self.rows.append(dict(case=self.case_id, item=item, kind=kind, status="그대로",
                                  truthful_rejected=False, note=note))
            return
        if workaround:
            args, how = workaround
            ok2, msg2 = self.a.call(*args)
            if ok2:
                self.rows.append(dict(case=self.case_id, item=item, kind=kind, status="우회",
                                      truthful_rejected=True, note=f"그대로 넣으면 거부({msg}). 우회: {how}"))
                return
            msg = f"{msg} / 우회도 거부({msg2})"
        self.rows.append(dict(case=self.case_id, item=item, kind=kind, status="보류",
                              truthful_rejected=True, note=msg))

    def forced(self, item, kind=None, note=""):
        """하네스가 사실과 다른 기록을 강제하는 경우(예: 하지 않은 단계를 빈 반론으로)."""
        self.rows.append(dict(case=self.case_id, item=item, kind=kind, status="우회",
                              truthful_rejected=False, note=note))


def case_a(harness: Path, tmp: Path) -> list[dict]:
    """CASE-20260930-001: 211자 장면, 배치와 공개 순서, 동일 내용 비교 (사실 21개)."""
    a = V1CLI(harness, tmp)
    R = Replay("CASE-20260930-001", a)
    v = json.loads((LAB / "handoff/2026-09-30_v2/variants.json").read_text(encoding="utf-8"))
    src = a.file((v["original"] + "\n").encode(), "original.md")
    R.attempt("원문(211자)과 목적", (["init", "--source", str(src), "--goal",
              "독자가 민서의 의심은 이해하되 배신 여부는 확신하지 못하게", "--scope", "same_content"], ))
    R.no_slot("필수 사실 10개", note="goal 문자열 하나뿐")
    R.no_slot("작업 단위 12와 변경 종류(배치·공개 순서)")
    R.attempt("독립 검토: 에이전트 1 (수정안 B)", (["review", "--role", "purpose", "--input", a.js(
        {"role": "purpose", "summary": "단위 1–2를 끝으로", "proposals": [prop("R1-1", "단위 1–2")]})], ))
    R.attempt("독립 검토: 에이전트 2 (수정안 B)", (["review", "--role", "structure", "--input", a.js(
        {"role": "structure", "summary": "선취", "proposals": [prop("R2-1", "단위 1–2")]})], ))
    R.attempt("독립 검토: 에이전트 3 (유지 의견, 9항목 판정)", (["review", "--role", "meaning", "--input", a.js(
        {"role": "meaning", "summary": "변화 0, 불확실 1", "proposals": []})], ))
    R.no_slot("진행자 결정: 목적 판정 기준 '읽는 동안'", kind="진행자 결정")
    R.attempt("상호 반론: 1→2 (두 위험의 무게)", (["object", "--role", "purpose", "--input", a.js(
        {"role": "purpose", "summary": "무게", "objections": [{"proposal_id": "R2-1", "reason": "같은 무게 아님"}]})], ))
    R.no_slot("상호 반론: 1→3 (제안이 없는 검토자에게 낸 보완)", note="반론 대상이 제안 번호뿐")
    R.forced("상호 반론의 '보완'(반대가 아닌 덧붙임)", note="반론 형식으로만 넣을 수 있음")
    R.attempt("상호 반론: 2→1", (["object", "--role", "structure", "--input", a.js(
        {"role": "structure", "summary": "과한 판정", "objections": [{"proposal_id": "R1-1", "reason": "미검증"}]})], ))
    R.attempt("상호 반론: 3→1, 3→2", (["object", "--role", "meaning", "--input", a.js(
        {"role": "meaning", "summary": "과장", "objections": [{"proposal_id": "R1-1", "reason": "미검증"},
                                                            {"proposal_id": "R2-1", "reason": "단위 수만 사실"}]})], ))
    R.no_slot("세 검토자의 진행자 결정에 대한 반론")
    R.no_slot("진행자 결정 수정 ('읽는 동안, 양방향')", kind="진행자 결정")
    R.no_slot("조정 1회 × 3", kind="조정")
    R.no_slot("남은 이견 2건")
    cand = a.file((v["B"] + "\n").encode(), "B.md")
    dec = {"selected_proposals": ["R1-1", "R2-1"], "reason": "세 검토 모두 B", "meaning_verdict": "uncertain",
           "meaning_review": "변화 0, 불확실 1", "reviewed_sha256": sha(cand.read_bytes())}
    dec2 = dict(dec, meaning_verdict="preserved")
    R.attempt("최종 후보 B (의미 판정: 불확실 1)",
              (["candidate", "--input", str(cand), "--decision", a.js(dec)], ),
              workaround=(["candidate", "--input", str(cand), "--decision", a.js(dec2)], "'불확실'을 'preserved'로 바꿈"))
    R.no_slot("반응 전 예상 (반응 전에 커밋)", kind="반응 전 예상")
    R.no_slot("블라인드 배정 (가=B, 무작위 1)", kind="블라인드 배정")
    fb = {"candidate": "candidate_001.md", "preference": "candidate", "verbatim": "가", "comment": None,
          "reading_order": None}
    fb2 = dict(fb, comment="답하지 않음", reading_order="답하지 않음")
    R.attempt("사용자 반응 '가' (나머지 미응답)", (["feedback", "--input", a.js(fb)], ),
              workaround=(["feedback", "--input", a.js(fb2)], "빈칸을 '답하지 않음' 글자로 채움"))
    R.no_slot("판단 갱신 표와 judgments.jsonl", kind="판단 갱신")
    return R.rows


def case_b(harness: Path, tmp: Path) -> list[dict]:
    """CASE-20261001-001: 책 5~9쪽을 이해한 뒤 새 글 창작 (사실 17개). 추출본이 없으면 건너뜀."""
    if not BOOK.exists():
        return []
    a = V1CLI(harness, tmp)
    R = Replay("CASE-20261001-001", a)
    t = json.loads(BOOK.read_text(encoding="utf-8"))
    src = a.file(("\n".join(u["text"] for u in t["units"]) + "\n").encode(), "book.md")
    R.attempt("원문(책 추출본)과 목적", (["init", "--source", str(src), "--goal", "판단받는 사람의 자리에서 묻기",
                                      "--scope", "creative"], ), note="책 본문이 사례 폴더로 복사됨")
    R.no_slot("책 사진 5장 해시와 추출 규칙", kind="출처")
    R.no_slot("U12 결정 (고쳐 쓰기 → 창작)", kind="진행자 결정")
    R.no_slot("원문 이해와 관점 선택")
    R.no_slot("진행자 사실 확인")
    R.no_slot("초고 v1 (검토 대상)", kind="창작 초고")
    R.no_slot("표현 겹침 점검")
    v1 = (LAB / "cases/CASE-20261001-001/new_piece_v1.md").read_text(encoding="utf-8")
    for role, pid, tgt in (("purpose", "R1-1", "기계가 판정하는 시대일수록 우리에게 필요한 것은 더 정확한 기계만이 아니다."),
                           ("structure", "R2-1", "선은 누가 그었나요?"),
                           ("meaning", "R3-F1", "자동화된 결정에 대해서는 기준과 처리 과정을 설명해 달라고 요구할 수도 있다.")):
        assert tgt in v1
        R.attempt(f"검토 {role} (대상은 초고 v1)", (["review", "--role", role, "--input", a.js(
            {"role": role, "summary": "초고 검토", "proposals": [prop(pid, tgt, ev="모델의 편집 판단")]})], ))
    for role in ("purpose", "structure", "meaning"):
        ok, _ = a.call("object", "--role", role, "--input", a.js({"role": role, "summary": "생략", "objections": []}))
        R.forced(f"상호 반론 생략({role}, 결정으로 생략)", kind="단계 생략",
                 note="하지 않은 단계를 빈 반론으로 기록" if ok else "빈 반론도 거부")
    v2 = (LAB / "cases/CASE-20261001-001/new_piece_v2.md").read_bytes()
    cand = a.file(v2, "v2.md")
    R.attempt("최종 후보 v2와 재검사 해시 연결", (["candidate", "--input", str(cand), "--decision", a.js(
        {"selected_proposals": ["R1-1", "R3-F1"], "reason": "반영 표", "meaning_verdict": "changed",
         "meaning_review": "재검사 통과", "reviewed_sha256": sha(v2)})], ))
    diff = a.root / "diff_001.txt"
    if diff.exists() and "original" in diff.read_text(encoding="utf-8")[:200]:
        R.forced("창작 대조 (초고 v1 → 최종 v2)", kind="창작 초고", note="책 원문 → 새 글 diff가 대신 만들어짐")
    else:
        R.no_slot("창작 대조 (초고 v1 → 최종 v2)", kind="창작 초고")
    R.no_slot("반응 전 예상 8관점", kind="반응 전 예상")
    R.rows.append(dict(case=R.case_id, item="사용자 반응 (아직 없음)", kind=None, status="그대로",
                       truthful_rejected=False, note="반응 대기 단계"))
    return R.rows


def measure(harness: Path = DEFAULT_HARNESS) -> dict:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        rows = case_a(harness, Path(d1)) + case_b(harness, Path(d2))
    c = Counter(r["status"] for r in rows)
    kinds = {}
    for k in DEDICATED:
        mine = [r for r in rows if r["kind"] == k]
        kinds[k] = bool(mine) and all(r["status"] == "그대로" for r in mine)
    return {
        "harness_sha256": sha(Path(harness).read_bytes()),
        "facts": len(rows),
        "case_b_included": BOOK.exists(),
        "counts": {k: c.get(k, 0) for k in ("그대로", "우회", "자리없음", "보류")},
        "truthful_rejected": sum(r["truthful_rejected"] for r in rows),
        "dedicated_kinds_ok": kinds,
        "rows": rows,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harness", default=str(DEFAULT_HARNESS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    m = measure(Path(args.harness))
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return 0
    print(f"사실 {m['facts']}개 (창작 사례 포함: {m['case_b_included']})")
    print("분류:", ", ".join(f"{k} {v}" for k, v in m["counts"].items()))
    print("사실 그대로 넣었을 때 거부:", m["truthful_rejected"])
    print("전용 기록 종류:", sum(m["dedicated_kinds_ok"].values()), "/", len(DEDICATED))
    for r in m["rows"]:
        if r["status"] != "그대로":
            print(f"  [{r['status']}] {r['case']} | {r['item']} | {r['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
