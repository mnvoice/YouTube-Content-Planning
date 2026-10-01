"""새 글과 원문 사이의 표현 겹침을 잰다.

저작권 거리를 사람이 판단하기 전에 쓰는 기계 점검이다. 수치가 낮다고 해서
법적으로 안전하다는 뜻은 아니다. 구성과 예시 선택의 유사성은 따로 본다.

사용법:
    python editing_lab/tools/overlap_check.py SOURCE TARGET [--min-chars 8] [--json]

SOURCE와 TARGET은 .txt, .md, 또는 {"units": [{"text": ...}]} 형태의 .json이다.
원문 본문은 출력하지 않는다. 겹친 글자열은 TARGET에도 있는 것만 보인다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_text(path: str) -> str:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        data = json.loads(raw)
        return "\n".join(u["text"] for u in data["units"])
    if p.suffix == ".md":
        raw = "\n".join(line for line in raw.splitlines() if not line.startswith("#"))
    return raw


def squash(text: str) -> str:
    """공백을 모두 지운다. 띄어쓰기만 바꾼 베끼기도 잡기 위해서다."""
    return re.sub(r"\s+", "", text)


def shared_spans(source: str, target: str, min_chars: int) -> list[str]:
    """공백을 지운 두 글에서 min_chars 이상 이어지는 공통 글자열을 TARGET 순서로 돌려준다."""
    s, t = squash(source), squash(target)
    grams = {s[i : i + min_chars] for i in range(len(s) - min_chars + 1)}
    spans: list[str] = []
    i = 0
    while i <= len(t) - min_chars:
        if t[i : i + min_chars] in grams:
            j = i + min_chars
            while j < len(t) and t[i : j + 1] in s:
                j += 1
            spans.append(t[i:j])
            i = j
        else:
            i += 1
    return spans


def eojeol_ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"[^\s.,!?'\"“”‘’()<>『』「」:;■-]+", text)
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def report(source: str, target: str, min_chars: int = 8) -> dict:
    spans = shared_spans(source, target, min_chars)
    src3, tgt3 = eojeol_ngrams(source, 3), eojeol_ngrams(target, 3)
    common3 = sorted(" ".join(g) for g in src3 & tgt3)
    return {
        "source_chars": len(squash(source)),
        "target_chars": len(squash(target)),
        "min_chars": min_chars,
        "longest_shared_span": max(spans, key=len) if spans else "",
        "longest_shared_len": max((len(x) for x in spans), default=0),
        "shared_spans": spans,
        "shared_span_chars": sum(len(x) for x in spans),
        "target_coverage": round(sum(len(x) for x in spans) / max(len(squash(target)), 1), 4),
        "eojeol3_shared": common3,
        "eojeol3_jaccard": round(len(src3 & tgt3) / max(len(src3 | tgt3), 1), 4),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--min-chars", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    r = report(load_text(args.source), load_text(args.target), args.min_chars)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print(f"원문 {r['source_chars']}자 / 새 글 {r['target_chars']}자 (공백 제외)")
    print(f"{r['min_chars']}자 이상 겹친 글자열: {len(r['shared_spans'])}개, 합계 {r['shared_span_chars']}자, 새 글의 {r['target_coverage']:.1%}")
    for s in r["shared_spans"]:
        print(f"  - {s} ({len(s)}자)")
    print(f"겹친 어절 3-gram: {len(r['eojeol3_shared'])}개, Jaccard {r['eojeol3_jaccard']}")
    for g in r["eojeol3_shared"]:
        print(f"  - {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
