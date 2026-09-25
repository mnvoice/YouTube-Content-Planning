import pytest

from ytplan import config, net, setup_keys

TEMPLATE = """# 주석은 유지
YOUTUBE_API_KEY=

NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
ANTHROPIC_API_KEY=
"""


def test_clean_pasted_values():
    assert setup_keys.clean('  "AIzaSyABC123"  ') == "AIzaSyABC123"
    assert setup_keys.clean("YOUTUBE_API_KEY=AIzaSyABC123") == "AIzaSyABC123"
    assert setup_keys.clean("") == ""


def test_mask():
    assert setup_keys.mask(None) == "없음"
    assert setup_keys.mask("AIzaSyABCDEFGH1234") == "설정됨 (…1234)"
    assert "1234" not in setup_keys.mask("abc1234")  # 짧은 값은 끝자리도 보여 주지 않는다


def test_update_env_from_template_keeps_comments(tmp_path):
    (tmp_path / ".env.example").write_text(TEMPLATE, encoding="utf-8")
    env = tmp_path / ".env"
    setup_keys.update_env(env, {"YOUTUBE_API_KEY": "AIzaNEW"}, tmp_path / ".env.example")
    text = env.read_text(encoding="utf-8")
    assert "# 주석은 유지" in text and "YOUTUBE_API_KEY=AIzaNEW" in text
    assert config.read_env(env)["YOUTUBE_API_KEY"] == "AIzaNEW"

    setup_keys.update_env(env, {"YOUTUBE_API_KEY": "AIzaNEWER", "EXTRA": "x"})
    values = config.read_env(env)
    assert values["YOUTUBE_API_KEY"] == "AIzaNEWER" and values["EXTRA"] == "x"
    assert env.read_text(encoding="utf-8").count("YOUTUBE_API_KEY=") == 1


def test_read_env_handles_bom(tmp_path):
    env = tmp_path / ".env"
    env.write_text("YOUTUBE_API_KEY=abc\n", encoding="utf-8-sig")  # 윈도우 메모장 저장 형식
    assert config.read_env(env) == {"YOUTUBE_API_KEY": "abc"}


@pytest.mark.parametrize(
    "error, expected",
    [
        ('GET x 실패 (400): {"reason": "API_KEY_INVALID"}', "올바르지 않습니다"),
        ("GET x 실패 (403): YouTube Data API v3 has not been used in project 123", "사용 설정"),
        ('GET x 실패 (403): {"reason": "quotaExceeded"}', "할당량"),
        ('GET x 실패 (403): {"reason": "API_KEY_SERVICE_BLOCKED"}', "API 제한사항"),
        ('GET x 실패 (403): {"reason": "API_KEY_HTTP_REFERRER_BLOCKED"}', "애플리케이션 제한사항"),
    ],
)
def test_check_youtube_explains_errors(monkeypatch, error, expected):
    def fail(*a, **k):
        raise RuntimeError(error)

    monkeypatch.setattr(net, "get_json", fail)
    ok, message = setup_keys.check_youtube("KEY")
    assert not ok and expected in message


def test_check_youtube_ok_and_uncached(monkeypatch):
    seen = {}

    def fake(url, params=None, headers=None, ttl=None):
        seen.update(url=url, ttl=ttl, key=params["key"])
        return {"items": []}

    monkeypatch.setattr(net, "get_json", fake)
    assert setup_keys.check_youtube("KEY") == (True, "정상")
    assert seen["url"].endswith("/i18nRegions") and seen["ttl"] == 0


@pytest.mark.parametrize("code, expected", [("401", "올바르지 않습니다"), ("403", "데이터랩"), ("429", "한도")])
def test_check_naver_explains_errors(monkeypatch, code, expected):
    def fail(*a, **k):
        raise RuntimeError(f"POST x 실패 ({code}): error")

    monkeypatch.setattr(net, "post_json", fail)
    ok, message = setup_keys.check_naver("id", "secret")
    assert not ok and expected in message


def test_run_saves_only_entered_keys_and_verifies(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text(TEMPLATE, encoding="utf-8")
    env = tmp_path / ".env"
    answers = iter(["  AIzaSyREALKEY9876  "])
    monkeypatch.setattr(setup_keys, "check_youtube", lambda key: (key == "AIzaSyREALKEY9876", "정상"))
    logs = []
    ok = setup_keys.run(env, only={"youtube"}, ask=lambda prompt: next(answers), out=logs.append)
    assert ok
    assert config.read_env(env)["YOUTUBE_API_KEY"] == "AIzaSyREALKEY9876"
    text = "\n".join(logs)
    assert "AIzaSyREALKEY9876" not in text  # 키 전체가 화면에 찍히지 않는다
    assert "[정상] YouTube" in text


def test_run_enter_keeps_existing_and_skips_unset(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("YOUTUBE_API_KEY=OLDKEY12345\n", encoding="utf-8")
    monkeypatch.setattr(setup_keys, "check_youtube", lambda key: (True, "정상"))
    logs = []
    ok = setup_keys.run(env, only={"youtube", "naver"}, ask=lambda prompt: "", out=logs.append)
    assert ok
    assert config.read_env(env)["YOUTUBE_API_KEY"] == "OLDKEY12345"
    assert "바뀐 값이 없습니다" in "\n".join(logs)
    assert "  [건너뜀] 네이버 데이터랩: 설정 안 됨" in logs


def test_run_check_only_reports_failure(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("YOUTUBE_API_KEY=BADKEY\n", encoding="utf-8")
    monkeypatch.setattr(setup_keys, "check_youtube", lambda key: (False, "키가 올바르지 않습니다."))

    def never_ask(prompt):
        raise AssertionError("--check에서는 입력을 받지 않는다")

    logs = []
    assert not setup_keys.run(env, only={"youtube"}, check_only=True, ask=never_ask, out=logs.append)
    assert "  [실패] YouTube: 키가 올바르지 않습니다." in logs


def test_warns_when_shell_variable_overrides_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("YOUTUBE_API_KEY=FROMFILE\n", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_API_KEY", "FROMSHELL")
    monkeypatch.setattr(config, "loaded_from_file", set())
    monkeypatch.setattr(setup_keys, "check_youtube", lambda key: (True, "정상"))
    logs = []
    setup_keys.run(env, only={"youtube"}, check_only=True, out=logs.append)
    assert any("터미널 환경변수" in line for line in logs)
