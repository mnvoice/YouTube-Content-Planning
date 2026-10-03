"""ACCEPTANCE.md의 완료 기준을 하네스에 대고 잰다.

사용법:
    python editing_lab/harness/acceptance.py [--harness PATH] [--label 이름] [--save]

--save를 주면 결과를 harness/results/<날짜>_<label>.json으로 새로 쓴다(덮어쓰지 않음).
각 기준은 PASS / FAIL / N/A(잴 수 없음) 중 하나로 판정한다.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
REPO = LAB.parent
sys.path.insert(0, str(HERE))
import replay  # noqa: E402

ROLES = ("purpose", "structure", "meaning")
VARIANTS = {
    "LF": "가. 나.\n다.\n".encode(),
    "CRLF": "가. 나.\r\n다.\r\n".encode(),
    "CR": "가. 나.\r다.\r".encode(),
    "BOM": "﻿가. 나.\n".encode(),
    "줄끝공백": "가.  \n나.\t\n".encode(),
}

# 기준 ID → 목표 단계 (ACCEPTANCE.md 2절). "유지"는 처음부터 통과해야 하고 후퇴하면 안 됨
TARGET = {
    "A1": 1, "A2": 1, "D1": 1, "D2": 1, "D3": 1,
    "B1": "유지", "B2": "유지", "B3": "유지", "B4": "유지", "B5": "유지", "B6": "유지", "B7": "유지", "B8": "유지",
    "B9": 2, "C1": 2, "C2": "2–3", "C3": 2, "C3b": "유지", "C4": 2, "C5": 3, "C6": 2,
    "E1": "항상", "F1": 2, "F2": 2, "F3": 2, "G1": "유지",
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Case:
    def __init__(self, harness: Path, tmp: Path, scope="same_content", max_candidates=None):
        self.harness, self.tmp, self.scope, self.max = harness, tmp, scope, max_candidates
        self.root = tmp / "case"
        self.n = 0

    def run(self, *args, root=None):
        return subprocess.run([sys.executable, str(self.harness), "--case", str(root or self.root), *args],
                              capture_output=True, text=True)

    def js(self, obj):
        self.n += 1
        p = self.tmp / f"in_{self.n:03d}.json"
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return str(p)

    def init(self, source: bytes = "가. 나. 다.\n".encode()):
        src = self.tmp / "source.md"
        src.write_bytes(source)
        extra = ["--max-candidates", str(self.max)] if self.max else []
        return self.run("init", "--source", str(src), "--goal", "목표", "--scope", self.scope, *extra)

    def review(self, role, pid=None, proposals=None):
        props = proposals if proposals is not None else [dict(
            proposal_id=pid or f"{role}-1", target="가.", action="이동", reason="이유",
            expected_effect="효과", downside="반례", evidence_type="응용 판단")]
        return self.run("review", "--role", role, "--input", self.js({"role": role, "summary": "요약", "proposals": props}))

    def obj(self, role, objections=None):
        return self.run("object", "--role", role, "--input",
                        self.js({"role": role, "summary": "요약", "objections": objections or []}))

    def through_objections(self):
        assert self.init().returncode == 0
        for r in ROLES:
            assert self.review(r).returncode == 0
        for r in ROLES:
            assert self.obj(r).returncode == 0

    def candidate(self, data: bytes, verdict="preserved", reviewed=None):
        self.n += 1
        p = self.tmp / f"cand_{self.n:03d}.md"
        p.write_bytes(data)
        d = self.js({"selected_proposals": ["purpose-1"], "reason": "이유", "meaning_verdict": verdict,
                     "meaning_review": "검토", "reviewed_sha256": reviewed or sha(data)})
        return self.run("candidate", "--input", str(p), "--decision", d)

    def feedback(self, obj):
        return self.run("feedback", "--input", self.js(obj))

    def state(self, root=None):
        return json.loads(sorted((root or self.root).glob("state_*.json"))[-1].read_text(encoding="utf-8"))

    def held(self, root=None):
        p = (root or self.root) / "held.jsonl"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def tmpcase(harness, **kw):
    d = tempfile.TemporaryDirectory()
    return d, Case(harness, Path(d.name), **kw)


# ---------- A ----------
def check_A1(h):
    bad = []
    for name, data in VARIANTS.items():
        d, c = tmpcase(h)
        with d:
            r = c.init(data)
            if r.returncode != 0:
                bad.append(f"{name}: init 거부")
                continue
            ev = json.loads((c.root / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
            same = (c.root / "original.md").read_bytes() == data
            fp = ev["details"].get("source_sha256") == c.state()["files"]["original.md"]
            if not (same and fp):
                bad.append(f"{name}: 사본 바이트 {'같음' if same else '다름'}, 지문 {'일치' if fp else '불일치'}")
    return not bad, "; ".join(bad) or "5종 모두 바이트 동일"


def check_A2(h):
    bad = []
    for name, data in VARIANTS.items():
        d, c = tmpcase(h)
        with d:
            c.through_objections()
            r = c.candidate(data)
            if r.returncode != 0:
                bad.append(f"{name}: 거부")
                continue
            if (c.root / "candidate_001.md").read_bytes() != data:
                bad.append(f"{name}: 저장 바이트 다름")
    return not bad, "; ".join(bad) or "5종 모두 수용, 바이트 동일"


# ---------- B ----------
def check_B(h):
    res = {}
    d, c = tmpcase(h)
    with d:
        c.through_objections()
        res["B1"] = (c.candidate(b"x\n", reviewed="0" * 64).returncode != 0, "해시 불일치 후보")
    d, c = tmpcase(h)
    with d:
        c.init()
        c.review("purpose")
        res["B2"] = (c.review("structure", pid="purpose-1").returncode != 0, "제안 번호 중복")
        before = (c.root / "review_purpose.json").read_bytes()
        c.review("purpose")
        res["B6"] = ((c.root / "review_purpose.json").read_bytes() == before, "같은 역할 재제출 뒤 기존 기록")
        res["B5"] = (c.obj("purpose").returncode != 0 and c.candidate(b"x\n").returncode != 0, "검토 3개 전 반론·후보")
        for r in ("structure", "meaning"):
            c.review(r)
        res["B3"] = (c.obj("purpose", [{"proposal_id": "없음", "reason": "r"}]).returncode != 0, "없는 제안 대상 반론")
        n_held = len(c.held())
        res["B8"] = (n_held >= 5 and all({"time", "command", "reason"} <= set(x) for x in c.held()),
                     f"보류 기록 {n_held}건")
    d, c = tmpcase(h)
    with d:
        c.through_objections()
        res["B7"] = (c.candidate(b"y\n", verdict="changed").returncode != 0, "'변화' 후보의 동일 내용 비교")
    d, c = tmpcase(h)
    with d:
        c.init()
        (c.root / "original.md").write_bytes(b"tampered\n")
        r = c.run("verify")
        res["B4"] = (r.returncode != 0, "원문 변조 뒤 verify")
    d, c = tmpcase(h)
    with d:
        c.through_objections()
        c.candidate(b"z\n", reviewed="1" * 64)
        last = c.held()[-1] if c.held() else {}
        keys = set(last) - {"time", "command", "reason"}
        res["B9"] = (bool(keys & {"input_sha256", "inputs", "payload", "payload_path", "submitted"}),
                     f"보류 기록의 추가 칸: {sorted(keys) or '없음'}")
    return res


# ---------- C ----------
def check_C(h):
    m = replay.measure(Path(h))
    cnt = m["counts"]
    kinds_ok = sum(m["dedicated_kinds_ok"].values())
    res = {
        "C1": (cnt["우회"] == 0, f"우회 {cnt['우회']}"),
        "C2": (m["truthful_rejected"] == 0, f"그대로 넣었을 때 거부 {m['truthful_rejected']}"),
        "C3": (cnt["자리없음"] == 0, f"자리없음 {cnt['자리없음']}"),
        "C3b": (cnt["보류"] == 0, f"보류 {cnt['보류']}"),
        "C4": (kinds_ok == len(replay.DEDICATED), f"전용 기록 종류 {kinds_ok}/{len(replay.DEDICATED)}"),
    }
    if not m["case_b_included"]:
        for k in res:
            res[k] = (res[k][0], res[k][1] + " (창작 사례 추출본 없음: 211자 장면만)")
    d, c = tmpcase(h)
    with d:
        c.through_objections()
        r = c.candidate("다. 가. 나.\n".encode(), verdict="uncertain")
        moved = r.returncode == 0 and c.state()["stage"] == "reader_feedback"
        res["C5"] = (moved, "기록되고 반응 단계로 진행" if moved else "거부 또는 진행 안 됨")
    d, c = tmpcase(h)
    with d:
        c.through_objections()
        c.candidate("다. 가. 나.\n".encode())
        r = c.feedback({"candidate": "candidate_001.md", "preference": "candidate", "verbatim": "가",
                        "comment": None, "reading_order": None})
        ok = False
        if r.returncode == 0:
            fb = c.state()["feedback"][-1]
            ok = fb.get("verbatim") == "가" and fb.get("comment") in (None, "") and fb.get("reading_order") in (None, "")
        res["C6"] = (ok, "원문 그대로, 빈칸 유지" if ok else "거부되거나 빈칸이 채워짐")
    return res, m


# ---------- D ----------
def _complete_case(h, tmp):
    c = Case(h, tmp, max_candidates=3)
    c.through_objections()
    assert c.candidate("다. 가. 나.\n".encode()).returncode == 0
    assert c.feedback({"candidate": "candidate_001.md", "preference": "candidate",
                       "comment": "좋다", "reading_order": "원문 먼저"}).returncode == 0
    return c


def _consistent(st):
    nr, no, act = len(st["reviews"]), len(st["objections"]), st["active_candidate"]
    expect = ("independent_review" if nr < 3 else "discussion" if no < 3
              else ("reader_feedback", "complete") if act else "candidate")
    return st["stage"] in (expect if isinstance(expect, tuple) else (expect,)), expect


def _next_command(c, root, st):
    stage = st["stage"]
    if stage == "independent_review":
        role = next((r for r in ROLES if r not in st["reviews"]), ROLES[0])  # 모두 있으면 모순 상태: 시도만 함
        return c.run("review", "--role", role, "--input", c.js({"role": role, "summary": "s", "proposals": []}), root=root)
    if stage == "discussion":
        role = next((r for r in ROLES if r not in st["objections"]), ROLES[0])
        return c.run("object", "--role", role, "--input", c.js({"role": role, "summary": "s", "objections": []}), root=root)
    if stage == "reader_feedback":
        return c.run("feedback", "--input", c.js({"candidate": st["active_candidate"], "preference": "equal",
                                                  "comment": "c", "reading_order": "o"}), root=root)
    data = f"새 후보 {c.n}\n".encode()
    c.n += 1
    p = c.tmp / f"next_{c.n}.md"
    p.write_bytes(data)
    dec = c.js({"selected_proposals": [], "reason": "r", "meaning_verdict": "preserved", "meaning_review": "m",
                "reviewed_sha256": sha(data)})
    return c.run("candidate", "--input", str(p), "--decision", dec, root=root)


def check_D(h):
    d1, d2, d3 = [], [], []
    with tempfile.TemporaryDirectory() as d:
        c = _complete_case(h, Path(d))
        snaps = sorted(c.root.glob("state_*.json"))
        for k in range(1, len(snaps) + 1):
            root = Path(d) / f"rb_{k}"
            shutil.copytree(c.root, root)
            before = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file() and p.name not in ("events.jsonl", "held.jsonl")}
            r = c.run("rollback", "--snapshot", str(k), root=root)
            if r.returncode != 0:
                d1.append(f"{k}: 되돌리기 거부")
                continue
            for name, b in before.items():
                if not (root / name).exists() or (root / name).read_bytes() != b:
                    d3.append(f"{k}: {name}")
            st = c.state(root)
            ok, expect = _consistent(st)
            if not ok:
                d1.append(f"{k}: 단계 {st['stage']} ↔ 기록상 {expect}")
            r2 = _next_command(c, root, st)
            if r2.returncode != 0:
                d2.append(f"{k}({st['stage']}): {(r2.stderr.strip().splitlines() or [''])[-1]}")
        n = len(snaps)
    return {
        "D1": (not d1, f"스냅샷 {n}개 중 모순 {len(d1)}" + (f": {d1[:3]}" if d1 else "")),
        "D2": (not d2, f"스냅샷 {n}개 중 다음 명령 실패 {len(d2)}" + (f": {d2[:3]}" if d2 else "")),
        "D3": (not d3, f"지워지거나 바뀐 기록 {len(d3)}"),
    }


# ---------- E ----------
def check_E1():
    book = LAB / "private/CASE-20261001-001/transcript.json"
    if not book.exists():
        return None, "추출본 없음: 판단 불가"
    import re
    sq = lambda t: re.sub(r"\s+", "", t)
    src = sq("\n".join(u["text"] for u in json.loads(book.read_text(encoding="utf-8"))["units"]))
    grams = {src[i:i + 8] for i in range(len(src) - 7)}
    files = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
    hits = []
    for f in files:
        try:
            t = sq((REPO / f).read_text(encoding="utf-8"))
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        n = sum(1 for i in range(len(t) - 7) if t[i:i + 8] in grams)
        if n:
            hits.append(f"{f}({n})")
    return not hits, f"추적 파일 {len(files)}개 중 8자 겹침 파일 {len(hits)}" + (f": {hits[:5]}" if hits else "")


# ---------- F ----------
def check_F(h):
    res = {}
    hdir = Path(h).parent
    readme = hdir / "README.md"
    if readme.exists():
        import re
        refs = sorted(set(re.findall(r"(examples/[\w./-]+\.json|test_harness\.py)", readme.read_text(encoding="utf-8"))))
        missing = [r for r in refs if not (hdir / r).exists()]
        res["F1"] = (bool(refs) and not missing, f"README가 가리킨 파일 {len(refs)}개 중 없음 {len(missing)}")
    else:
        res["F1"] = (False, "README 없음")
    with tempfile.TemporaryDirectory() as d:
        c = Case(h, Path(d))
        r = c.run("verify", root=Path(d) / "없는폴더")
        res["F2"] = (r.returncode != 0 and "Traceback" not in r.stderr, "처리되지 않은 오류 없음" if "Traceback" not in r.stderr else "Traceback 발생")
    d, c = tmpcase(h)
    with d:
        c.init()
        r = c.init()
        res["F3"] = (r.returncode != 0 and not (c.root / "held.jsonl").exists(),
                     "기존 사례 기록 그대로" if not (c.root / "held.jsonl").exists() else "기존 사례에 보류 기록이 생김")
    return res


# ---------- G ----------
def check_G1(h):
    d, c = tmpcase(h)
    with d:
        c.through_objections()
        ok = c.candidate("다. 가. 나.\n".encode()).returncode == 0
        ok = ok and c.feedback({"candidate": "candidate_001.md", "preference": "candidate",
                                "comment": "좋다", "reading_order": "원문 먼저"}).returncode == 0
        ok = ok and c.run("verify").returncode == 0 and c.run("report").returncode == 0
    return ok, "끝까지 성공" if ok else "중간 실패"


def run_all(harness: Path) -> dict:
    h = Path(harness).resolve()
    out = {}
    out["A1"] = check_A1(h)
    out["A2"] = check_A2(h)
    out.update(check_B(h))
    cres, rep = check_C(h)
    out.update(cres)
    out.update(check_D(h))
    out["E1"] = check_E1()
    out.update(check_F(h))
    out["G1"] = check_G1(h)
    rows = {}
    for k in TARGET:
        ok, note = out[k]
        rows[k] = {"result": "N/A" if ok is None else ("PASS" if ok else "FAIL"), "target": TARGET[k], "note": note}
    return {"harness": str(h), "harness_sha256": sha(h.read_bytes()), "criteria": rows,
            "replay": {k: rep[k] for k in ("facts", "case_b_included", "counts", "truthful_rejected", "dedicated_kinds_ok")}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harness", default=str(HERE / "harness.py"))
    ap.add_argument("--label", default="run")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args(argv)
    res = run_all(Path(args.harness))
    res["measured_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res["label"] = args.label
    for k, v in res["criteria"].items():
        print(f"{k:4} {v['result']:4} 목표 {str(v['target']):4} | {v['note']}")
    if args.save:
        out = HERE / "results" / f"{datetime.date.today().isoformat()}_{args.label}.json"
        with out.open("x", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("저장:", out.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
