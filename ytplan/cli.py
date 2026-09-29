"""명령줄 도구: python -m ytplan <명령> ...

  setup     API 키를 .env에 저장하고 작동 확인
  bank      아이템 뱅크 보기
  expand    키워드 자동완성 확장 (사람들이 실제로 치는 검색어 모으기)
  research  YouTube·네이버 데이터랩·뉴스로 아이템 조사
  benchmark 조회수가 잘 나오는 채널을 찾아 히트 영상·제목 패턴 분석 (새 실행 폴더에 저장)
  verify-run 벤치마크 실행 폴더 검증
  ideas     벤치마크 결과로 Claude가 새 아이템 제안 (뱅크에 추가 가능)
  rank      점수 매겨 순위표 만들기
  calendar  업로드 캘린더 만들기
  script    Claude로 영상 기획안(대본) 만들기
  feedback  독자 채점 장부: 에이전트 예측과 독자 결과를 따로 적고 비교
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime
from pathlib import Path

from . import benchmark, config, feedback, research, report
from .planner import WEEKDAYS_KO, build_calendar
from .scoring import score_all
from .sources import youtube
from .topics import DEFAULT_BANK, load_topics, select


def _ids(value: str | None) -> list[str] | None:
    return [v.strip().upper() for v in value.split(",") if v.strip()] if value else None


def _weekdays(value: str) -> list[int]:
    days = []
    for token in value.split(","):
        token = token.strip()
        if token in WEEKDAYS_KO:
            days.append(WEEKDAYS_KO.index(token))
        elif token.isdigit() and 0 <= int(token) <= 6:
            days.append(int(token))
        else:
            raise argparse.ArgumentTypeError(f"요일은 월~일 또는 0~6으로 적어 주세요: {token}")
    return days


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"저장: {path}")


def cmd_setup(args) -> None:
    from . import setup_keys

    ok = setup_keys.run(Path(args.env or args.env_file), only={args.only} if args.only else None, check_only=args.check)
    if not ok:
        sys.exit(1)


def cmd_bank(args) -> None:
    topics = select(load_topics(args.bank), pillar=args.pillar)
    for t in topics:
        season = ",".join(map(str, t.season)) + "월" if t.season else "연중"
        print(f"{t.id:4} [{t.pillar}] {t.title}  (공감{t.empathy} 정보{t.info} AI{t.ai_fit} 위험:{t.risk} {season})")
        if args.verbose:
            print(f"      공감 훅: \"{t.empathy_hook}\"")
            print(f"      핵심 정보: {t.info_core}")
            print(f"      출처: {', '.join(t.sources)}")
    print(f"\n총 {len(topics)}개")


def cmd_expand(args) -> None:
    suggestions = youtube.expand(args.keyword)
    for s in suggestions:
        print(s)
    print(f"\n총 {len(suggestions)}개 (유튜브 검색창 자동완성 기준)")
    if args.save:
        _write(Path(args.out) / "expand" / f"{args.keyword}.txt", "\n".join(suggestions) + "\n")


def cmd_research(args) -> None:
    all_topics = load_topics(args.bank)
    topics = select(all_topics, _ids(args.topic), args.pillar)
    results = research.run(
        topics,
        youtube_key=config.get("YOUTUBE_API_KEY"),
        naver_id=config.get("NAVER_CLIENT_ID"),
        naver_secret=config.get("NAVER_CLIENT_SECRET"),
        days=args.days,
        use_news=not args.no_news,
    )
    for t in topics:
        _write(Path(args.out) / "research" / f"{t.id}.md", report.research_markdown(t.id, t.title, results[t.id]))


def _new_run_dir(args) -> Path:
    run_dir = Path(args.run_dir) if args.run_dir else Path(args.out) / f"benchmark_{datetime.now():%Y%m%d-%H%M%S}"
    if run_dir.exists():
        raise ValueError(f"이미 있는 폴더에는 쓰지 않습니다 (기존 결과 보존): {run_dir}")
    run_dir.mkdir(parents=True)
    return run_dir


def cmd_benchmark(args) -> None:
    api_key = config.get("YOUTUBE_API_KEY")
    if not api_key:
        print(f"YOUTUBE_API_KEY가 필요합니다. {args.env_file}에 넣어 주세요.", file=sys.stderr)
        sys.exit(1)
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()] if args.seeds else list(benchmark.DEFAULT_SEEDS)
    discover = not args.no_discover
    n_channels = (args.top if discover else 0) + len(args.channel or [])
    quota = benchmark.estimate_quota(len(seeds) if discover else 0, n_channels, args.videos) + args.age_hits
    run_dir = _new_run_dir(args)
    log_lines: list[str] = []

    def log(message: str) -> None:
        print(message)
        log_lines.append(message)

    log(f"실행 폴더: {run_dir}")
    log(f"예상 YouTube 할당량: 약 {quota:,} 유닛 (하루 기본 10,000)")
    try:
        data = benchmark.run(
            api_key,
            load_topics(args.bank),
            seeds=seeds,
            channel_refs=args.channel,
            discover=discover,
            top=args.top,
            days=args.days,
            min_subs=args.min_subs,
            max_videos=args.videos,
            include_broadcasters=args.include_broadcasters,
            min_baseline=args.min_baseline,
            age_hits=args.age_hits,
            log=log,
        )
        (run_dir / "benchmark.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "benchmark.md").write_text(report.benchmark_markdown(data), encoding="utf-8")
        report.channels_csv(data, run_dir / "channels.csv")
        counts = data["collection"]["counts"]
        log("수집 결과: " + " · ".join(f"{k} {v}" for k, v in counts.items()))
        if not data["meta"]["complete"]:
            log(f"주의: 중간에 멈췄습니다 ({data['meta']['stop_reason']}). 부분 결과만 저장했습니다.")
        for v in data["hits"][:10]:
            log(f"  {v['channel_multiple']:>5}x {v['views']:>10,}회  {v['title'][:50]}  ({v['channel']})")
        log(f"저장: {run_dir}/benchmark.json, benchmark.md, channels.csv, run.log")
        log(f"검증: python -m ytplan verify-run {run_dir}")
    finally:
        (run_dir / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")


def cmd_verify_run(args) -> None:
    from . import verify

    run_dir = Path(args.run_dir)
    checks = verify.verify_run(run_dir, args.expect_commit)
    for c in checks:
        print(f"[{'통과' if c.ok else '실패'}] {c.name}: {c.detail}")
    print(f"저장: {verify.write_report(run_dir, checks)}")
    if not all(c.ok for c in checks):
        sys.exit(1)


def _load_benchmark(args) -> dict:
    """--benchmark로 준 파일, 없으면 --out 안의 가장 최근 실행 폴더, 그것도 없으면 research/benchmark.json."""
    if args.benchmark:
        return json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    runs = sorted(Path(args.out).glob("benchmark_*/benchmark.json"))
    if runs:
        return json.loads(runs[-1].read_text(encoding="utf-8"))
    return research.load_benchmark()


def cmd_ideas(args) -> None:
    from . import ideas  # anthropic SDK는 이 명령에서만 필요

    data = _load_benchmark(args)
    if not data.get("hits"):
        print("벤치마크 결과가 없습니다. 먼저 `python -m ytplan benchmark`를 실행하세요.", file=sys.stderr)
        sys.exit(1)
    topics = load_topics(args.bank)
    out = Path(args.out)
    if args.prompt_only:
        text = (
            "아래 두 블록을 claude.ai 대화창에 차례로 붙여 넣으세요.\n\n"
            "## 1. 지침\n\n" + ideas.SYSTEM_PROMPT + "\n## 2. 요청\n\n" + ideas.build_prompt(data, topics, args.count)
        )
        _write(out / "ideas_prompt.md", text)
        return
    _require_anthropic_key()
    print(f"히트 영상 {len(data['hits'])}개로 새 아이템 {args.count}개 기획 중... (1~3분 걸릴 수 있습니다)")
    result = ideas.generate_ideas(data, topics, args.count)
    rows = ideas.to_bank_rows(result, topics)
    _write(out / "ideas.md", ideas.render_markdown(result, rows))
    ideas.write_rows(rows, out / "ideas_bank.csv")
    print(f"저장: {out / 'ideas_bank.csv'}")
    if args.append:
        bank_path = Path(args.bank) if args.bank else DEFAULT_BANK
        ideas.write_rows(rows, bank_path, append=True)
        print(f"아이템 뱅크에 {len(rows)}개 추가: {bank_path}")


def _require_anthropic_key() -> None:
    if not (config.get("ANTHROPIC_API_KEY") or config.get("ANTHROPIC_AUTH_TOKEN")):
        print("ANTHROPIC_API_KEY가 없습니다. .env에 넣거나 --prompt-only로 프롬프트만 뽑으세요.", file=sys.stderr)
        sys.exit(1)


def cmd_rank(args) -> None:
    topics = select(load_topics(args.bank), pillar=args.pillar)
    month = args.month or date.today().month
    cards = score_all(topics, research.load_all(topics), month)
    out = Path(args.out)
    _write(out / "ranking.md", report.ranking_markdown(cards, month))
    report.ranking_csv(cards, out / "ranking.csv")
    print(f"저장: {out / 'ranking.csv'}\n")
    for i, c in enumerate(cards[: args.top], 1):
        print(f"{i:2}. {c.total:5.1f}  {c.topic.id} [{c.topic.pillar}] {c.topic.title}  (반영도 {c.coverage * 100:.0f}%)")


def cmd_calendar(args) -> None:
    topics = load_topics(args.bank)
    start = date.fromisoformat(args.start) if args.start else date.today()
    slots = build_calendar(topics, research.load_all(topics), start, weeks=args.weeks, weekdays=args.days)
    _write(Path(args.out) / "calendar.md", report.calendar_markdown(slots))
    for s in slots:
        print(f"{s.day} ({WEEKDAYS_KO[s.day.weekday()]})  {s.card.topic.id} [{s.card.topic.pillar}] {s.card.topic.title}")


def cmd_script(args) -> None:
    from . import generate  # anthropic SDK는 이 명령에서만 필요

    topic = select(load_topics(args.bank), _ids(args.topic))[0]
    data = research.load(topic.id)
    bench = _load_benchmark(args)
    lessons = feedback.lessons(feedback.load_all(Path(args.ledger)))
    if lessons:
        print("독자 실험에서 확인된 표현 유형을 프롬프트에 반영합니다.")
    out = Path(args.out) / "scripts"
    if args.prompt_only:
        prompt = generate.build_prompt(topic, data, args.minutes, bench, lessons)
        text = (
            "아래 두 블록을 claude.ai 대화창에 차례로 붙여 넣으세요.\n\n"
            "## 1. 지침\n\n" + generate.SYSTEM_PROMPT + "\n## 2. 요청\n\n" + prompt
        )
        _write(out / f"{topic.id}_prompt.md", text)
        return
    _require_anthropic_key()
    print(f"{topic.id} '{topic.title}' 기획안 생성 중... (1~3분 걸릴 수 있습니다)")
    plan = generate.generate_plan(topic, data, args.minutes, benchmark=bench, lessons=lessons)
    _write(out / f"{topic.id}.md", generate.render_markdown(topic, plan))
    _write(out / f"{topic.id}.json", generate.plan_to_json(plan))


def _save_decision(decision: dict, args) -> None:
    print(f"저장: {feedback.save(decision, Path(args.ledger))}")


def cmd_fb_new(args) -> None:
    video = args.video.upper()
    if args.option:
        texts = args.option
    else:
        path = Path(args.out) / "scripts" / f"{video}.json"
        if not path.exists():
            raise ValueError(f"{path}가 없습니다. 먼저 script --topic {video}를 실행하거나 --option으로 후보를 직접 적으세요.")
        texts = feedback.options_from_plan(json.loads(path.read_text(encoding="utf-8")), args.slot)
    decision = feedback.new_decision(video, args.slot, texts, feedback.parse_tags(args.tag))
    target = Path(args.ledger) / f"{decision['id']}.json"
    if target.exists() and not args.replace:
        raise ValueError(f"{decision['id']}는 이미 장부에 있습니다. 새로 만들려면 --replace (예측·결과가 지워집니다).")
    _save_decision(decision, args)
    for o in decision["options"]:
        print(f"  {o['key']}. {o['text']}  [{', '.join(o['tags']) or '유형 없음'}]")
    print(f"\n다음: 에이전트마다 따로 예측을 적습니다 → feedback predict {decision['id']} --agent claude --auto")


def cmd_fb_predict(args) -> None:
    decision = feedback.load(args.decision, Path(args.ledger))
    if args.auto:
        _require_anthropic_key()
        p = feedback.auto_predict(decision, args.agent)
    elif args.pick:
        feedback.add_prediction(decision, args.agent, args.pick, args.confidence, args.reason or "")
        p = decision["predictions"][-1]
    else:
        raise ValueError("--pick 후보번호 또는 --auto(Claude가 예측)를 주세요.")
    _save_decision(decision, args)
    conf = "" if p["confidence"] is None else f", 확신도 {p['confidence']:.2f}"
    print(f"{args.agent}: {p['pick']}번{conf}  {p['reason']}")


def cmd_fb_pick(args) -> None:
    ledger = Path(args.ledger)
    decision = feedback.load(args.decision, ledger)
    model = feedback.reader_model(feedback.load_all(ledger))
    rng = random.Random(args.seed) if args.seed is not None else None
    decision["tested"] = feedback.pick_test_options(decision, model, args.max, rng)
    _save_decision(decision, args)
    favorite, _ = feedback.consensus(decision)
    voted = {p["pick"] for p in decision["predictions"]}
    print("YouTube Studio A/B 테스트(또는 독자 패널)에 올릴 후보:")
    for key in decision["tested"]:
        role = "에이전트 합의" if key == favorite else ("반대 후보: 에이전트가 안 고름" if key not in voted else "독자 모델 탐색")
        print(f"  {key}. {feedback.option(decision, key)['text']}  ({role})")


def cmd_fb_result(args) -> None:
    decision = feedback.load(args.decision, Path(args.ledger))
    if bool(args.ab) == bool(args.panel):
        raise ValueError("--ab 또는 --panel 중 하나만 주세요.")
    if args.ab:
        out = feedback.record_result(decision, "ab", feedback.parse_ab(args.ab), args.verdict, args.note or "", replace=args.replace)
    else:
        out = feedback.record_result(decision, "panel", feedback.parse_panel(args.panel), note=args.note or "", replace=args.replace)
    _save_decision(decision, args)
    verdict = feedback.AB_VERDICTS[out["verdict"]]
    print(f"독자 결과: {verdict}" + (f", 승자 {out['winner']}번" if out["winner"] else ""))


def cmd_fb_report(args) -> None:
    decisions = feedback.load_all(Path(args.ledger))
    if not decisions:
        print(f"장부({args.ledger})가 비어 있습니다. feedback new로 시작하세요.", file=sys.stderr)
        sys.exit(1)
    _write(Path(args.out) / "feedback_report.md", feedback.report_markdown(decisions, _load_benchmark(args)))
    for r in feedback.agent_scores(decisions):
        print(f"{r['agent']}: 독자 승자 {r['hits']}/{r['n']} 맞힘 (우연 기대 {r['chance']:.1f}) → {r['verdict']}")


def cmd_fb_status(args) -> None:
    for line in feedback.status_lines(feedback.load_all(Path(args.ledger))) or ["장부가 비어 있습니다."]:
        print(line)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ytplan", description="40~50대 정보·공감형 유튜브 기획 도구")
    p.add_argument("--bank", help="아이템 뱅크 CSV 경로 (기본: 내장 topic_bank.csv)")
    p.add_argument("--out", default="output", help="결과 저장 폴더 (기본: output)")
    p.add_argument("--env-file", default=".env", help="API 키를 읽을 .env 경로 (기본: 현재 폴더의 .env, 읽기만 함)")
    p.add_argument("--ledger", default=feedback.DEFAULT_LEDGER, help="독자 채점 장부 폴더 (기본: feedback)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="API 키를 .env에 저장하고 작동 확인")
    s.add_argument("--only", choices=["youtube", "naver", "anthropic"], help="이 서비스의 키만 입력")
    s.add_argument("--check", action="store_true", help="입력 없이 저장된 키가 작동하는지만 확인")
    s.add_argument("--env", help="키를 저장할 파일 (기본: --env-file 값, 보통 현재 폴더의 .env)")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("bank", help="아이템 뱅크 보기")
    s.add_argument("--pillar", help="콘텐츠 기둥으로 거르기 (예: 건강, 돈, 가족)")
    s.add_argument("-v", "--verbose", action="store_true", help="공감 훅·핵심 정보·출처까지 보기")
    s.set_defaults(func=cmd_bank)

    s = sub.add_parser("expand", help="유튜브 자동완성으로 연관 검색어 모으기 (키 불필요)")
    s.add_argument("keyword")
    s.add_argument("--save", action="store_true", help="output/expand/에 저장")
    s.set_defaults(func=cmd_expand)

    s = sub.add_parser("research", help="YouTube·데이터랩·뉴스 조사")
    s.add_argument("--topic", help="아이템 id, 쉼표로 여러 개 (예: M01,H02)")
    s.add_argument("--pillar", help="콘텐츠 기둥 전체 조사")
    s.add_argument("--days", type=int, default=365, help="YouTube 인기 영상 조회 기간(일)")
    s.add_argument("--no-news", action="store_true", help="뉴스 조사 생략")
    s.set_defaults(func=cmd_research)

    s = sub.add_parser("benchmark", help="잘 되는 채널을 찾아 히트 영상·제목 패턴 분석")
    s.add_argument("--seeds", help="채널을 찾을 키워드, 쉼표로 구분 (기본: 40~50대 관심 키워드 10개)")
    s.add_argument("--channel", action="append", help="직접 분석할 채널 (@핸들, 채널 주소, UC… id). 여러 번 쓸 수 있음")
    s.add_argument("--no-discover", action="store_true", help="자동으로 찾지 않고 --channel로 준 채널만 분석")
    s.add_argument("--top", type=int, default=15, help="자동으로 고를 채널 수")
    s.add_argument("--days", type=int, default=365, help="채널을 찾을 때 볼 기간(일)")
    s.add_argument("--min-subs", type=int, default=10_000, help="이보다 구독자가 적은 채널은 제외")
    s.add_argument("--videos", type=int, default=150, help="채널당 분석할 최신 영상 수")
    s.add_argument("--include-broadcasters", action="store_true", help="방송사·뉴스 채널도 포함")
    s.add_argument("--min-baseline", type=int, default=benchmark.MIN_BASELINE,
                   help="평소 조회수 기준을 잡을 최소 영상 수 (형식별)")
    s.add_argument("--age-hits", type=int, default=benchmark.AGE_EVIDENCE_HITS,
                   help="댓글 나이 언급을 확인할 히트 영상 수 (영상당 1 유닛, 0이면 생략)")
    s.add_argument("--run-dir", help="결과를 쓸 새 폴더 (기본: <out>/benchmark_날짜-시간). 이미 있으면 거부")
    s.set_defaults(func=cmd_benchmark)

    s = sub.add_parser("verify-run", help="벤치마크 실행 폴더 검증 (재계산·건수·키 노출)")
    s.add_argument("run_dir", help="benchmark가 만든 실행 폴더")
    s.add_argument("--expect-commit", help="실행에 써야 했던 커밋 해시 (앞부분만 적어도 됨)")
    s.set_defaults(func=cmd_verify_run)

    s = sub.add_parser("ideas", help="벤치마크 결과로 새 아이템 제안 (Claude)")
    s.add_argument("--count", type=int, default=15, help="제안받을 아이템 수")
    s.add_argument("--benchmark", help="사용할 benchmark.json (기본: 가장 최근 실행 폴더)")
    s.add_argument("--append", action="store_true", help="결과를 아이템 뱅크 CSV에 바로 추가")
    s.add_argument("--prompt-only", action="store_true", help="API 호출 없이 프롬프트만 저장 (claude.ai에 붙여 넣기용)")
    s.set_defaults(func=cmd_ideas)

    s = sub.add_parser("rank", help="점수 매겨 순위표 만들기")
    s.add_argument("--month", type=int, choices=range(1, 13), metavar="1-12", help="기준 월 (기본: 이번 달)")
    s.add_argument("--pillar")
    s.add_argument("--top", type=int, default=15, help="화면에 보여 줄 개수")
    s.set_defaults(func=cmd_rank)

    s = sub.add_parser("calendar", help="업로드 캘린더 만들기")
    s.add_argument("--start", help="시작일 YYYY-MM-DD (기본: 오늘)")
    s.add_argument("--weeks", type=int, default=8)
    s.add_argument("--days", type=_weekdays, default=[1, 4], help="업로드 요일 (예: 화,금 / 기본: 화,금)")
    s.set_defaults(func=cmd_calendar)

    s = sub.add_parser("script", help="Claude로 영상 기획안 만들기")
    s.add_argument("--topic", required=True, help="아이템 id (예: M03)")
    s.add_argument("--minutes", type=int, default=10, help="영상 길이(분)")
    s.add_argument("--benchmark", help="참고할 benchmark.json (기본: 가장 최근 실행 폴더)")
    s.add_argument("--prompt-only", action="store_true", help="API 호출 없이 프롬프트만 저장 (claude.ai에 붙여 넣기용)")
    s.set_defaults(func=cmd_script)

    fb = sub.add_parser("feedback", help="독자 채점 장부: 에이전트 예측과 독자 결과를 따로 적고 비교")
    fsub = fb.add_subparsers(dest="action", required=True)

    s = fsub.add_parser("new", help="표현 후보를 장부에 등록 (기본: script 결과의 제목 후보)")
    s.add_argument("video", help="아이템 id (예: M03)")
    s.add_argument("--slot", default="title", help="title / thumbnail / hook / scene 등 (기본: title)")
    s.add_argument("--option", action="append", help="후보를 직접 적기. 여러 번 쓸 수 있음 (없으면 기획안 JSON에서 읽음)")
    s.add_argument("--tag", action="append", help="표현 유형 직접 붙이기 (예: 1=구체 장면;감정). 여러 번 쓸 수 있음")
    s.add_argument("--replace", action="store_true", help="같은 선택이 있으면 새로 만들기 (예측·결과 삭제)")
    s.set_defaults(func=cmd_fb_new)

    s = fsub.add_parser("predict", help="에이전트 예측 적기 (독자 결과를 보기 전에만)")
    s.add_argument("decision", help="선택 id (예: M03-title)")
    s.add_argument("--agent", required=True, help="예측한 에이전트 이름 (예: claude, codex)")
    s.add_argument("--pick", help="독자가 고를 것 같은 후보 번호")
    s.add_argument("--confidence", type=float, help="그 후보가 이길 확률 0~1")
    s.add_argument("--reason", help="한두 문장 근거")
    s.add_argument("--auto", action="store_true", help="Claude가 후보 순서를 섞어 따로 예측 (API 키 필요)")
    s.set_defaults(func=cmd_fb_predict)

    s = fsub.add_parser("pick", help="A/B 테스트·패널에 올릴 후보 고르기 (합의 후보 + 반대 후보 + 탐색)")
    s.add_argument("decision")
    s.add_argument("--max", type=int, default=3, help="올릴 후보 수 (YouTube A/B는 최대 3개)")
    s.add_argument("--seed", type=int, help="같은 결과를 다시 뽑고 싶을 때")
    s.set_defaults(func=cmd_fb_pick)

    s = fsub.add_parser("result", help="독자 결과 적기 (YouTube A/B 또는 독자 패널)")
    s.add_argument("decision")
    s.add_argument("--ab", help="A/B 시청 시간 점유율(%%) 예: 1=41,3=35,5=24")
    s.add_argument("--verdict", choices=list(feedback.AB_VERDICTS), help="YouTube 판정: winner(승자) / same(차이 없음) / inconclusive(판정 불가)")
    s.add_argument("--panel", help="독자 패널 맞힌(고른) 수/인원 예: 1=4/5,2=1/5")
    s.add_argument("--note", help="메모")
    s.add_argument("--replace", action="store_true", help="이미 적힌 결과를 바꾸기")
    s.set_defaults(func=cmd_fb_result)

    s = fsub.add_parser("report", help="에이전트 적중·합의 강도·표현 유형별 학습 보고서")
    s.add_argument("--benchmark", help="비교할 benchmark.json (기본: 가장 최근 실행 폴더)")
    s.set_defaults(func=cmd_fb_report)

    s = fsub.add_parser("status", help="장부에 있는 선택과 진행 상태")
    s.set_defaults(func=cmd_fb_status)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config.load_dotenv(args.env_file)
    try:
        args.func(args)
    except (KeyError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(2)
    except (RuntimeError, OSError) as e:
        print(f"실행 실패 (네트워크·API 키·할당량을 확인하세요): {e}", file=sys.stderr)
        sys.exit(1)
