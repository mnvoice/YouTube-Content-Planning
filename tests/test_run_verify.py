"""벤치마크 실행 폴더 만들기(CLI)와 검증(verify-run)을 가짜 YouTube API로 끝까지 확인한다."""

import json

import pytest

import test_benchmark as tb
from ytplan import benchmark, cli, net, verify


@pytest.fixture
def env(tmp_path, monkeypatch):
    """원본 설치 폴더(.env 보관)와 새 작업 폴더를 나눠 둔다."""
    original = tmp_path / "original"
    original.mkdir()
    (original / ".env").write_text("YOUTUBE_API_KEY=AIza" + "K" * 35 + "\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(net, "get_json", tb.fake_get_json)
    monkeypatch.setattr(benchmark, "_git_commit", lambda: {"commit": "abc1234def", "dirty": False})
    return original, work


def _run(original, extra=()):
    cli.main(["--env-file", str(original / ".env"), "--out", "results", "benchmark",
              "--seeds", "50대 건강,노후 준비", "--channel", "@nobody", "--min-baseline", "3", *extra])


def _only_run_dir(work):
    runs = sorted((work / "results").glob("benchmark_*"))
    assert len(runs) == 1
    return runs[0]


def test_benchmark_writes_new_run_folder_and_reads_env_file_without_touching_it(env):
    original, work = env
    before = (original / ".env").read_bytes()
    _run(original)
    run_dir = _only_run_dir(work)
    assert {f.name for f in run_dir.iterdir()} == {"benchmark.json", "benchmark.md", "channels.csv", "run.log"}
    assert (original / ".env").read_bytes() == before  # 원본 .env는 읽기만
    assert not (work / ".env").exists()  # 새 폴더에 키 파일을 복사하지 않음
    log = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "수집 결과: 전체 3 · 성공 2 · 보류 0 · 실패 1 · 미실행 0" in log


def test_benchmark_refuses_to_overwrite_existing_run_dir(env):
    original, work = env
    (work / "fixed").mkdir()
    with pytest.raises(SystemExit) as info:
        _run(original, ["--run-dir", str(work / "fixed")])
    assert info.value.code == 2


def test_verify_run_passes_on_fresh_output(env):
    original, work = env
    _run(original)
    run_dir = _only_run_dir(work)
    checks = verify.verify_run(run_dir, expect_commit="abc1234")
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    report = verify.write_report(run_dir, checks)
    text = report.read_text(encoding="utf-8")
    assert "검증 결과: 통과" in text and verify.sha256(run_dir / "benchmark.json") in text


def test_verify_run_via_cli_exit_codes(env):
    original, work = env
    _run(original)
    run_dir = _only_run_dir(work)
    cli.main(["verify-run", str(run_dir), "--expect-commit", "abc1234"])  # 통과하면 예외 없음
    with pytest.raises(SystemExit) as info:
        cli.main(["verify-run", str(run_dir), "--expect-commit", "fff0000"])
    assert info.value.code == 1


def _tamper(run_dir, fn):
    path = run_dir / "benchmark.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize(
    "tamper, failing",
    [
        (lambda d: d["channels"][0].__setitem__("median_views_long", 1), "평소 조회수·배수 재계산"),
        (lambda d: d["collection"]["counts"].__setitem__("성공", 5), "수집 건수 일치"),
        (lambda d: d["hits"].pop(), "히트 재계산"),
        (lambda d: d["patterns"][0].__setitem__("hit_n", 99), "제목 구조 재계산"),
        (lambda d: d["meta"].__setitem__("code", {"commit": "abc1234def", "dirty": True}), "코드 커밋"),
    ],
)
def test_verify_run_detects_tampering(env, tamper, failing):
    original, work = env
    _run(original)
    run_dir = _only_run_dir(work)
    _tamper(run_dir, tamper)
    failed = {c.name for c in verify.verify_run(run_dir) if not c.ok}
    assert failing in failed


def test_verify_run_detects_leaked_key(env):
    original, work = env
    _run(original)
    run_dir = _only_run_dir(work)
    with open(run_dir / "run.log", "a", encoding="utf-8") as f:
        f.write("GET https://www.googleapis.com/youtube/v3/search?q=x&key=abcdefghijk12345\n")
    failed = {c.name for c in verify.verify_run(run_dir) if not c.ok}
    assert "API 키 노출 없음" in failed


def test_ideas_and_script_use_latest_run(env, monkeypatch):
    original, work = env
    _run(original)
    cli.main(["--out", "results", "ideas", "--prompt-only", "--count", "5"])
    prompt = (work / "results" / "ideas_prompt.md").read_text(encoding="utf-8")
    assert "퇴직한 남편이 달라졌어요" in prompt
