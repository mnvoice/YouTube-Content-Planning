"""벤치마크 실행 폴더를 검증한다 (Codex 등 실행 담당자의 확인용).

    python -m ytplan verify-run output/benchmark_20260926-101500 --expect-commit <커밋 해시>

저장된 원자료(videos)로 평소 조회수·배수·히트·제목 구조를 다시 계산해 보고서 숫자와 맞는지,
수집 건수가 서로 맞는지, 파일에 API 키가 새어 들어가지 않았는지 확인하고
결과를 같은 폴더의 verification.md에 파일별 SHA-256과 함께 남긴다.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import benchmark, net

REQUIRED_FILES = ("benchmark.json", "benchmark.md", "channels.csv", "run.log")
REQUIRED_KEYS = ("meta", "collection", "channels", "videos", "hits", "patterns", "age_evidence")
_KEY_PARAM = re.compile(r"[?&]key=[0-9A-Za-z_\-]{10,}")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recompute_channel(videos: list[dict], min_baseline: int) -> tuple[int | None, int | None]:
    longs = [v["views"] for v in videos if v["mature"] and not v["is_short"]]
    shorts = [v["views"] for v in videos if v["mature"] and v["is_short"]]
    med_long = statistics.median(longs) if len(longs) >= min_baseline else None
    med_short = statistics.median(shorts) if len(shorts) >= min_baseline else None
    return med_long, med_short


def verify_run(run_dir: Path, expect_commit: str | None = None) -> list[Check]:
    checks: list[Check] = []
    missing = [f for f in REQUIRED_FILES if not (run_dir / f).exists()]
    checks.append(Check("필수 파일", not missing, "누락: " + ", ".join(missing) if missing else ", ".join(REQUIRED_FILES)))
    if "benchmark.json" in missing:
        return checks

    try:
        data = json.loads((run_dir / "benchmark.json").read_text(encoding="utf-8"))
    except ValueError as e:
        checks.append(Check("JSON 읽기", False, str(e)))
        return checks
    absent = [k for k in REQUIRED_KEYS if k not in data]
    checks.append(Check("JSON 필수 항목", not absent, "누락: " + ", ".join(absent) if absent else "모두 있음"))
    if absent:
        return checks

    meta, col = data["meta"], data["collection"]
    code = meta.get("code", {})
    commit_ok = code.get("commit") not in (None, "unknown") and (not expect_commit or code["commit"].startswith(expect_commit))
    checks.append(Check("코드 커밋", commit_ok and not code.get("dirty"),
                        f"{code.get('commit')} (수정 파일 {'있음' if code.get('dirty') else '없음'})"
                        + (f", 기대값 {expect_commit}" if expect_commit else "")))
    checks.append(Check("실행 완료", bool(meta.get("complete")),
                        "완료" if meta.get("complete") else f"중단: {meta.get('stop_reason')} (부분 결과)"))

    rows = col.get("channels", [])
    counts = col.get("counts", {})
    tally = Counter(r["status"] for r in rows)
    bad_status = [r["status"] for r in rows if r["status"] not in benchmark.STATUSES]
    counts_ok = (not bad_status and counts.get("전체") == len(rows)
                 and all(counts.get(s, 0) == tally.get(s, 0) for s in benchmark.STATUSES))
    checks.append(Check("수집 건수 일치", counts_ok,
                        " · ".join(f"{k} {v}" for k, v in counts.items()) + (f" / 이상한 상태 {bad_status}" if bad_status else "")))

    summaries = {c["id"]: c for c in data["channels"]}
    status_by_id = {r["id"]: r["status"] for r in rows if r.get("id")}
    mismatch = [cid for cid, c in summaries.items() if status_by_id.get(cid) != c.get("status")]
    stray = [r["title"] or r["ref"] for r in rows if r["status"] in ("실패", "미실행") and r.get("id") in summaries]
    checks.append(Check("채널 상태 일치", not mismatch and not stray,
                        f"요약 {len(summaries)}개" + (f", 불일치 {mismatch}" if mismatch else "") + (f", 잘못 포함 {stray}" if stray else "")))

    thresholds = meta.get("thresholds", {})
    min_baseline = thresholds.get("min_baseline", benchmark.MIN_BASELINE)
    videos = data["videos"]
    by_channel: dict[str, list[dict]] = {}
    for v in videos:
        by_channel.setdefault(v["channel_id"], []).append(v)
    bad_medians, bad_multiples = [], 0
    for cid, c in summaries.items():
        med_long, med_short = _recompute_channel(by_channel.get(cid, []), min_baseline)
        if (int(med_long) if med_long is not None else None) != c.get("median_views_long") or \
           (int(med_short) if med_short is not None else None) != c.get("median_views_short"):
            bad_medians.append(c["title"])
        for v in by_channel.get(cid, []):
            base = med_short if v["is_short"] else med_long
            expected = round(v["views"] / base, 2) if base and v["mature"] else None
            if expected != v["channel_multiple"]:
                bad_multiples += 1
    checks.append(Check("평소 조회수·배수 재계산", not bad_medians and not bad_multiples,
                        f"영상 {len(videos):,}개" + (f", 중앙값 불일치 {bad_medians}" if bad_medians else "")
                        + (f", 배수 불일치 {bad_multiples}개" if bad_multiples else "")))

    all_hits = benchmark.pick_hits(videos, thresholds.get("hit_multiple", benchmark.HIT_MULTIPLE),
                                   thresholds.get("hit_min_views", benchmark.HIT_MIN_VIEWS))
    saved_ids = [h["id"] for h in data["hits"]]
    hits_ok = [h["id"] for h in all_hits[: len(saved_ids)]] == saved_ids and len(saved_ids) == min(len(all_hits), 200)
    from_ok_channels = all(status_by_id.get(h.get("channel_id")) == "성공" for h in data["hits"])
    checks.append(Check("히트 재계산", hits_ok and from_ok_channels,
                        f"히트 {len(all_hits)}개 (저장 {len(saved_ids)}개)" + ("" if from_ok_channels else ", 성공 아닌 채널의 히트 포함")))

    recomputed = {p["pattern"]: p for p in benchmark.pattern_stats(all_hits, videos)}
    bad_patterns = [p["pattern"] for p in data["patterns"]
                    if (recomputed.get(p["pattern"], {}).get("hit_n"), recomputed.get(p["pattern"], {}).get("base_n"))
                    != (p.get("hit_n"), p.get("base_n"))]
    checks.append(Check("제목 구조 재계산", not bad_patterns, "불일치: " + ", ".join(bad_patterns) if bad_patterns else "일치"))

    if "channels.csv" not in missing:
        with open(run_dir / "channels.csv", encoding="utf-8-sig", newline="") as f:
            csv_rows = list(csv.DictReader(f))
        checks.append(Check("channels.csv 행 수", len(csv_rows) == len(rows), f"{len(csv_rows)}행 / 상태 {len(rows)}건"))
    if "benchmark.md" not in missing:
        md = (run_dir / "benchmark.md").read_text(encoding="utf-8")
        line = f"전체 {counts.get('전체', 0)} · 성공 {counts.get('성공', 0)} · 보류 {counts.get('보류', 0)}"
        checks.append(Check("보고서 숫자 일치", line in md and str(code.get("commit")) in md, line))

    leaks = []
    for f in sorted(run_dir.iterdir()):
        if f.is_file() and f.name != "verification.md":
            text = f.read_text(encoding="utf-8", errors="ignore")
            if any(pat.search(text) for pat in net._KEY_PATTERNS) or _KEY_PARAM.search(text):
                leaks.append(f.name)
    checks.append(Check("API 키 노출 없음", not leaks, "노출 의심: " + ", ".join(leaks) if leaks else "모든 파일 확인"))
    return checks


def write_report(run_dir: Path, checks: list[Check]) -> Path:
    ok = all(c.ok for c in checks)
    lines = [f"# 검증 결과: {'통과' if ok else '확인 필요'}", "", f"- 폴더: {run_dir}", "",
             "| 항목 | 결과 | 내용 |", "|---|---|---|"]
    lines += [f"| {c.name} | {'통과' if c.ok else '실패'} | {c.detail} |" for c in checks]
    lines += ["", "## 파일 SHA-256 (전달 후 같은 파일인지 확인용)", ""]
    for name in REQUIRED_FILES:
        f = run_dir / name
        if f.exists():
            lines.append(f"- `{name}` {sha256(f)}")
    path = run_dir / "verification.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
