"""명령줄 도구: python -m ytplan <명령> ...

  bank      아이템 뱅크 보기
  expand    키워드 자동완성 확장 (사람들이 실제로 치는 검색어 모으기)
  research  YouTube·네이버 데이터랩·뉴스로 아이템 조사
  benchmark 조회수가 잘 나오는 채널을 찾아 히트 영상·제목 패턴 분석
  ideas     벤치마크 결과로 Claude가 새 아이템 제안 (뱅크에 추가 가능)
  rank      점수 매겨 순위표 만들기
  calendar  업로드 캘린더 만들기
  script    Claude로 영상 기획안(대본) 만들기
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import benchmark, config, research, report
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


def cmd_benchmark(args) -> None:
    api_key = config.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY가 필요합니다. .env에 넣어 주세요.", file=sys.stderr)
        sys.exit(1)
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()] if args.seeds else list(benchmark.DEFAULT_SEEDS)
    discover = not args.no_discover
    n_channels = (args.top if discover else 0) + len(args.channel or [])
    quota = benchmark.estimate_quota(len(seeds) if discover else 0, n_channels, args.videos)
    print(f"예상 YouTube 할당량: 약 {quota:,} 유닛 (하루 기본 10,000)")
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
    )
    print(f"저장: {research.save_benchmark(data)}")
    _write(Path(args.out) / "benchmark.md", report.benchmark_markdown(data))
    for v in data["hits"][:10]:
        print(f"  {v['channel_multiple']:>5}x {v['views']:>10,}회  {v['title'][:50]}  ({v['channel']})")


def cmd_ideas(args) -> None:
    from . import ideas  # anthropic SDK는 이 명령에서만 필요

    data = research.load_benchmark()
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
    bench = research.load_benchmark()
    out = Path(args.out) / "scripts"
    if args.prompt_only:
        prompt = generate.build_prompt(topic, data, args.minutes, bench)
        text = (
            "아래 두 블록을 claude.ai 대화창에 차례로 붙여 넣으세요.\n\n"
            "## 1. 지침\n\n" + generate.SYSTEM_PROMPT + "\n## 2. 요청\n\n" + prompt
        )
        _write(out / f"{topic.id}_prompt.md", text)
        return
    _require_anthropic_key()
    print(f"{topic.id} '{topic.title}' 기획안 생성 중... (1~3분 걸릴 수 있습니다)")
    plan = generate.generate_plan(topic, data, args.minutes, benchmark=bench)
    _write(out / f"{topic.id}.md", generate.render_markdown(topic, plan))
    _write(out / f"{topic.id}.json", generate.plan_to_json(plan))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ytplan", description="40~50대 정보·공감형 유튜브 기획 도구")
    p.add_argument("--bank", help="아이템 뱅크 CSV 경로 (기본: 내장 topic_bank.csv)")
    p.add_argument("--out", default="output", help="결과 저장 폴더 (기본: output)")
    sub = p.add_subparsers(dest="command", required=True)

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
    s.set_defaults(func=cmd_benchmark)

    s = sub.add_parser("ideas", help="벤치마크 결과로 새 아이템 제안 (Claude)")
    s.add_argument("--count", type=int, default=15, help="제안받을 아이템 수")
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
    s.add_argument("--prompt-only", action="store_true", help="API 호출 없이 프롬프트만 저장 (claude.ai에 붙여 넣기용)")
    s.set_defaults(func=cmd_script)
    return p


def main(argv: list[str] | None = None) -> None:
    config.load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (KeyError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(2)
    except (RuntimeError, OSError) as e:
        print(f"실행 실패 (네트워크·API 키·할당량을 확인하세요): {e}", file=sys.stderr)
        sys.exit(1)
