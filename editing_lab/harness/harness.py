"""하는 일: 짧은 글의 편집 제안, 반론, 변경안과 독자 반응을 연결합니다.
역할: 모델 판단을 대신하지 않고 입력 고정, 단계 관리, 검증과 기록을 맡습니다.
외부 모델은 호출하지 않습니다. 검토 결과는 JSON 파일로 전달받습니다.
1.1판: 원문과 후보를 바이트 그대로 보존하고, 되돌린 뒤의 단계를 기록에서 다시 계산합니다.
"""
import argparse
import difflib
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROLES = ("purpose", "structure", "meaning")
HARNESS_VERSION = "1.1"


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    # 하는 일: 새 파일만 생성합니다. 역할: 원본과 기존 기록의 덮어쓰기를 막습니다.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def state(root):
    # 하는 일: 가장 마지막 스냅샷을 읽습니다. 역할: JSONL 이력과 현재 상태를 구분합니다.
    return read_json(sorted(root.glob("state_*.json"))[-1])


def save(root, current, event, details):
    # 하는 일: 새 상태 스냅샷과 사건 기록을 생성합니다. 역할: 과정을 추적 가능하게 보존합니다.
    index = len(list(root.glob("state_*.json"))) + 1
    write_new(root / f"state_{index:06d}.json", current)
    with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": now(), "event": event, "details": details}, ensure_ascii=False) + "\n")


def read_text_bytes(path):
    # 하는 일: 파일을 바이트로 읽고 UTF-8 글인지 확인합니다. 역할: 줄바꿈을 바꾸지 않고 지문을 잽니다.
    data = Path(path).read_bytes()
    return data, data.decode("utf-8")


def derive_stage(current):
    # 하는 일: 저장된 검토, 반론, 후보 수에서 단계를 계산합니다. 역할: 단계와 기록이 어긋나지 않게 합니다.
    if len(current["reviews"]) < len(ROLES):
        return "independent_review"
    if len(current["objections"]) < len(ROLES):
        return "discussion"
    return "reader_feedback" if current["active_candidate"] else "candidate"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root, current):
    # 하는 일: 저장된 입력과 산출물의 지문을 확인합니다. 역할: 입력 변경을 조용히 허용하지 않습니다.
    for name, expected in current["files"].items():
        require(digest(root / name) == expected, f"파일 지문 불일치: {name}")


def run(args):
    root = Path(args.case)
    if args.command == "init":
        require(args.max_candidates > 0, "후보 한도는 양수여야 합니다")
        source = Path(args.source)
        data, text = read_text_bytes(source)
        require(bool(text.strip()), "원문이 비어 있습니다")
        root.mkdir(parents=True, exist_ok=False)
        (root / "original.md").write_bytes(data)
        current = {"schema_version": 1, "harness_version": HARNESS_VERSION, "created": now(), "goal": args.goal,
                   "scope": args.scope, "model": args.model, "max_candidates": args.max_candidates,
                   "files": {"original.md": digest(root / "original.md")},
                   "reviews": {}, "objections": {}, "candidates": [], "active_candidate": None,
                   "feedback": [], "config_version": "v1", "stage": "independent_review"}
        config = {"version": "v1", "roles": list(ROLES), "discussion_rounds": 1,
                  "automatic_promotion": False, "model": args.model}
        write_new(root / "config_v1.json", config)
        current["files"]["config_v1.json"] = digest(root / "config_v1.json")
        save(root, current, "initialized", {"source_sha256": digest(source)})
        return
    current = state(root)
    verify(root, current)
    if args.command in ("review", "object"):
        data = read_json(args.input)
        require(data.get("role") == args.role, "역할과 JSON role이 다릅니다")
        require(isinstance(data.get("summary"), str) and bool(data["summary"].strip()), "summary가 필요합니다")
        if args.command == "review":
            require(current["stage"] == "independent_review", "독립 검토 단계가 아닙니다")
            proposals = data.get("proposals")
            require(isinstance(proposals, list), "proposals 배열이 필요합니다. 유지 의견은 빈 배열입니다")
            for item in proposals:
                for field in ("proposal_id", "target", "action", "reason", "expected_effect", "downside", "evidence_type"):
                    require(isinstance(item.get(field), str) and bool(item[field].strip()), f"제안의 {field}가 필요합니다")
            ids = [item["proposal_id"] for review in current["reviews"].values() for item in review["proposals"]]
            ids += [item["proposal_id"] for item in proposals]
            require(len(ids) == len(set(ids)), "제안 번호가 중복됩니다")
            bucket = "reviews"
        else:
            require(current["stage"] == "discussion", "독립 검토 3개가 먼저 필요합니다")
            known = {item["proposal_id"] for review in current["reviews"].values() for item in review["proposals"]}
            require(isinstance(data.get("objections"), list), "objections 배열이 필요합니다")
            for item in data["objections"]:
                require(item.get("proposal_id") in known, "반론 대상 제안이 없습니다")
                require(isinstance(item.get("reason"), str) and bool(item["reason"].strip()), "반론 이유가 필요합니다")
            bucket = "objections"
        require(args.role not in current[bucket], "같은 역할의 기록은 한 번만 받습니다")
        filename = f"{args.command}_{args.role}.json"
        write_new(root / filename, data)
        current["files"][filename] = digest(root / filename)
        current[bucket][args.role] = data
        if len(current[bucket]) == 3:
            current["stage"] = "discussion" if args.command == "review" else "candidate"
        save(root, current, args.command, {"role": args.role})
    elif args.command == "candidate":
        require(current["stage"] in ("candidate", "reader_feedback", "complete"), "검토와 반론을 먼저 완료하세요")
        require(len(current["candidates"]) < current["max_candidates"], "후보 실행 한도에 도달했습니다")
        decision = read_json(args.decision)
        known = {item["proposal_id"] for review in current["reviews"].values() for item in review["proposals"]}
        require(isinstance(decision.get("selected_proposals"), list), "selected_proposals 배열이 필요합니다")
        require(set(decision["selected_proposals"]) <= known, "알 수 없는 제안을 선택했습니다")
        require(bool(decision.get("reason")), "선택 이유가 필요합니다")
        require(decision.get("meaning_verdict") in ("preserved", "changed", "uncertain"), "의미 검토 결과가 필요합니다")
        require(bool(decision.get("meaning_review")), "최종 문자열의 의미 검토 근거가 필요합니다")
        data, text = read_text_bytes(args.input)
        require(bool(text.strip()), "변경안이 비어 있습니다")
        require(decision.get("reviewed_sha256") == hashlib.sha256(data).hexdigest(), "의미 검토 대상과 최종 문자열의 SHA-256이 다릅니다")
        if current["scope"] == "same_content":
            require(decision["meaning_verdict"] == "preserved", "동일 내용 비교에는 의미 보존 판정이 필요합니다")
        index = len(current["candidates"]) + 1
        name = f"candidate_{index:03d}.md"
        (root / name).write_bytes(data)
        decision_name = f"decision_{index:03d}.json"
        write_new(root / decision_name, decision)
        original = (root / "original.md").read_bytes().decode("utf-8")
        delta = "".join(difflib.unified_diff(original.splitlines(True), text.splitlines(True), fromfile="original", tofile=name))
        diff_name = f"diff_{index:03d}.txt"
        (root / diff_name).write_text(delta, encoding="utf-8")
        for filename in (name, decision_name, diff_name):
            current["files"][filename] = digest(root / filename)
        current["candidates"].append(name)
        current["active_candidate"] = name
        current["stage"] = "reader_feedback"
        save(root, current, "candidate_saved", {"candidate": name, "decision": decision_name})
    elif args.command == "feedback":
        require(current["stage"] == "reader_feedback", "비교할 후보가 필요합니다")
        data = read_json(args.input)
        require(data.get("candidate") == current["active_candidate"], "반응 대상 후보가 다릅니다")
        require(data.get("preference") in ("original", "candidate", "equal", "uncertain"), "선호 값이 잘못됐습니다")
        require(bool(data.get("comment")) and bool(data.get("reading_order")), "반응과 읽은 순서가 필요합니다")
        name = f"feedback_{len(current['feedback']) + 1:03d}.json"
        write_new(root / name, data)
        current["files"][name] = digest(root / name)
        current["feedback"].append(data)
        current["stage"] = "complete"
        save(root, current, "reader_feedback", data)
    elif args.command == "rollback":
        # 하는 일: 과거 스냅샷의 선택과 설정을 복원합니다. 역할: 기록을 지우지 않고 되돌립니다.
        target = read_json(root / f"state_{args.snapshot:06d}.json")
        verify(root, target)
        current["active_candidate"] = target["active_candidate"]
        current["config_version"] = target["config_version"]
        # 1.1판: 과거 스냅샷의 단계를 그대로 쓰면 이미 받은 검토·반론과 어긋나 진행이 막힙니다.
        current["stage"] = derive_stage(current)
        save(root, current, "rollback", {"snapshot": args.snapshot, "stage": current["stage"],
                                         "output_reproduction_guaranteed": False})
    elif args.command == "report":
        # 하는 일: 관찰 기록에서 읽기 쉬운 요약을 만듭니다. 역할: 모델 예상과 독자 반응을 구분합니다.
        print(json.dumps({"goal": current["goal"], "stage": current["stage"],
              "active_candidate": current["active_candidate"], "reviews": current["reviews"],
              "objections": current["objections"], "reader_feedback": current["feedback"],
              "note": "의미 판정은 제출자의 판단이며 독자 반응은 일반 성능을 입증하지 않습니다"}, ensure_ascii=False, indent=2))
    elif args.command == "verify":
        events = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        print(json.dumps({"files_verified": len(current["files"]), "events_parsed": len(events)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="새 사례 폴더 또는 기존 사례 폴더")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--source", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--scope", choices=("same_content", "creative"), required=True)
    init.add_argument("--model", default="external-session-unspecified")
    init.add_argument("--max-candidates", type=int, default=2)
    for command in ("review", "object"):
        sub = commands.add_parser(command)
        sub.add_argument("--role", choices=ROLES, required=True)
        sub.add_argument("--input", required=True)
    candidate = commands.add_parser("candidate")
    candidate.add_argument("--input", required=True)
    candidate.add_argument("--decision", required=True)
    feedback = commands.add_parser("feedback")
    feedback.add_argument("--input", required=True)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--snapshot", type=int, required=True)
    commands.add_parser("report")
    commands.add_parser("verify")
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        root = Path(args.case)
        if root.is_dir():
            with (root / "held.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"time": now(), "command": args.command, "reason": str(error)}, ensure_ascii=False) + "\n")
        parser.exit(1, f"보류: {error}\n")


if __name__ == "__main__":
    main()
