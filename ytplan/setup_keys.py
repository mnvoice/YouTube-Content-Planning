"""API 키를 .env에 저장하고, 키가 실제로 작동하는지 확인한다.

    python -m ytplan setup                 # 모든 키를 차례로 입력 (엔터 = 기존 값 유지)
    python -m ytplan setup --only youtube  # YouTube 키만
    python -m ytplan setup --check         # 입력 없이 저장된 키만 확인

키는 화면에 보이지 않게 입력받고(getpass), 채팅·코드·GitHub 어디에도 남기지 않는다.
"""

from __future__ import annotations

import getpass
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from . import config, net
from .sources import naver, youtube


@dataclass(frozen=True)
class KeySpec:
    name: str
    group: str
    label: str
    issue_url: str


KEYS = (
    KeySpec("YOUTUBE_API_KEY", "youtube", "YouTube Data API v3 키", "https://console.cloud.google.com/apis/credentials"),
    KeySpec("NAVER_CLIENT_ID", "naver", "네이버 데이터랩 Client ID", "https://developers.naver.com/apps/"),
    KeySpec("NAVER_CLIENT_SECRET", "naver", "네이버 데이터랩 Client Secret", "https://developers.naver.com/apps/"),
    KeySpec("ANTHROPIC_API_KEY", "anthropic", "Claude API 키", "https://console.anthropic.com/settings/keys"),
)
GROUP_LABELS = {"youtube": "YouTube", "naver": "네이버 데이터랩", "anthropic": "Claude"}


def mask(value: str | None) -> str:
    if not value:
        return "없음"
    return f"설정됨 (…{value[-4:]})" if len(value) > 8 else "설정됨"


def clean(value: str) -> str:
    """붙여 넣을 때 딸려 온 공백·따옴표·'KEY=' 접두어를 걷어 낸다."""
    value = value.strip().strip('"').strip("'").strip()
    return re.sub(r"^[A-Z_]+=", "", value).strip()


def update_env(path: Path, values: dict[str, str], template: Path | None = None) -> None:
    """기존 줄과 주석은 그대로 두고 해당 키의 값만 바꾼다. 없는 키는 끝에 붙인다."""
    if path.exists():
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    elif template and template.exists():
        lines = template.read_text(encoding="utf-8-sig").splitlines()
    else:
        lines = []
    remaining = dict(values)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines += [f"{k}={v}" for k, v in remaining.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)  # 나만 읽을 수 있게 (윈도우에서는 무시됨)
    except OSError:
        pass


def _status(message: str) -> str:
    m = re.search(r"\((\d{3})\)", message)
    return m.group(1) if m else ""


def check_youtube(key: str) -> tuple[bool, str]:
    try:
        # 가장 싼 호출(1 유닛)로 키만 확인한다. 캐시하지 않는다.
        net.get_json(f"{youtube.API}/i18nRegions", {"part": "snippet", "hl": "ko", "key": key}, ttl=0)
    except OSError:
        return False, "인터넷 연결을 확인하세요."
    except RuntimeError as e:
        msg = str(e)
        if "API_KEY_INVALID" in msg or "API key not valid" in msg:
            return False, "키가 올바르지 않습니다. 복사할 때 앞뒤가 잘리지 않았는지 확인하세요."
        if "SERVICE_DISABLED" in msg or "accessNotConfigured" in msg or "has not been used" in msg:
            return False, "Google Cloud 콘솔에서 'YouTube Data API v3'를 '사용 설정'하세요. (켠 뒤 몇 분 걸릴 수 있음)"
        if "quotaExceeded" in msg:
            return False, "오늘 할당량을 다 썼습니다. 한국 시간 오후 4~5시(태평양 시간 자정)에 초기화됩니다."
        if "API_KEY_SERVICE_BLOCKED" in msg:
            return False, "키의 'API 제한사항'에 YouTube Data API v3가 들어 있는지 확인하세요."
        if "referer" in msg.lower() or "IP address" in msg or "API_KEY_HTTP_REFERRER_BLOCKED" in msg:
            return False, "키의 '애플리케이션 제한사항'(웹사이트·IP) 때문에 막혔습니다. '없음'으로 바꾸세요."
        return False, f"확인 실패: {msg[:200]}"
    return True, "정상"


def check_naver(client_id: str, client_secret: str) -> tuple[bool, str]:
    end = date.today()
    try:
        naver.search_trend(client_id, client_secret, {"확인": ["국민연금"]}, end - timedelta(days=7), end, time_unit="date")
    except OSError:
        return False, "인터넷 연결을 확인하세요."
    except RuntimeError as e:
        code = _status(str(e))
        if code == "401":
            return False, "Client ID 또는 Client Secret이 올바르지 않습니다."
        if code == "403":
            return False, "애플리케이션의 '사용 API'에 '데이터랩(검색어트렌드)'을 추가하세요."
        if code == "429":
            return False, "오늘 호출 한도(1,000회)를 다 썼습니다."
        return False, f"확인 실패: {str(e)[:200]}"
    return True, "정상"


def check_anthropic(key: str) -> tuple[bool, str]:
    import anthropic

    try:
        anthropic.Anthropic(api_key=key, max_retries=0).models.list(limit=1)
    except anthropic.AuthenticationError:
        return False, "키가 올바르지 않습니다."
    except anthropic.PermissionDeniedError:
        return False, "이 키에 권한이 없습니다. 콘솔에서 키 상태를 확인하세요."
    except anthropic.APIConnectionError:
        return False, "인터넷 연결을 확인하세요."
    except anthropic.APIStatusError as e:
        return False, f"확인 실패 ({e.status_code})"
    return True, "정상"


def verify(values: dict[str, str], groups: set[str], out: Callable[[str], None] = print) -> bool:
    """저장된 키를 그룹별로 확인한다. 하나라도 실패하면 False."""
    checks = {
        "youtube": (["YOUTUBE_API_KEY"], lambda v: check_youtube(v["YOUTUBE_API_KEY"])),
        "naver": (["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"],
                  lambda v: check_naver(v["NAVER_CLIENT_ID"], v["NAVER_CLIENT_SECRET"])),
        "anthropic": (["ANTHROPIC_API_KEY"], lambda v: check_anthropic(v["ANTHROPIC_API_KEY"])),
    }
    all_ok = True
    out("\n키 확인")
    for group in ("youtube", "naver", "anthropic"):
        if group not in groups:
            continue
        names, check = checks[group]
        label = GROUP_LABELS[group]
        if not all(values.get(n) for n in names):
            out(f"  [건너뜀] {label}: 설정 안 됨")
            continue
        ok, message = check(values)
        all_ok &= ok
        out(f"  [{'정상' if ok else '실패'}] {label}: {message}")
        for n in names:
            shell = os.environ.get(n, "").strip()
            if n not in config.loaded_from_file and shell and shell != values[n]:
                out(f"    ! 터미널 환경변수 {n}에 다른 값이 있어 .env보다 먼저 쓰입니다. 그 환경변수를 지우세요.")
    return all_ok


def _git_note(env_path: Path) -> str:
    gitignore = env_path.parent / ".gitignore"
    ignored = gitignore.exists() and ".env" in [ln.strip() for ln in gitignore.read_text(encoding="utf-8").splitlines()]
    if ignored:
        return " (.gitignore에 들어 있어 GitHub에 올라가지 않습니다)"
    if (env_path.parent / ".git").exists():
        return "\n  ! .gitignore에 .env가 없습니다. 키가 GitHub에 올라가지 않도록 .gitignore에 .env를 추가하세요."
    return ""


def run(
    env_path: Path,
    only: set[str] | None = None,
    check_only: bool = False,
    ask: Callable[[str], str] = getpass.getpass,
    out: Callable[[str], None] = print,
) -> bool:
    groups = only or set(GROUP_LABELS)
    specs = [k for k in KEYS if k.group in groups]
    current = config.read_env(env_path)

    if not check_only:
        out(f"API 키 설정 → {env_path.resolve()}")
        out("키를 붙여 넣어도 화면에 글자가 보이지 않는 게 정상입니다. 붙여 넣고 엔터를 누르세요.")
        out("엔터만 누르면 기존 값을 그대로 둡니다.\n")
        new: dict[str, str] = {}
        for spec in specs:
            out(f"[{spec.label}] 현재: {mask(current.get(spec.name))}")
            out(f"  발급: {spec.issue_url}")
            value = clean(ask("  입력(보이지 않음)> "))
            if value:
                new[spec.name] = value
                out(f"  → 입력됨 (…{value[-4:]})")
        if new:
            template = env_path.parent / ".env.example"
            update_env(env_path, new, template)
            out(f"\n저장했습니다: {env_path}{_git_note(env_path)}")
            current = config.read_env(env_path)
        else:
            out("\n바뀐 값이 없습니다.")

    return verify(current, groups, out)
