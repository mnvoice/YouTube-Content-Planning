"""기록 하네스 1단계 완료 기준과 유지 기준의 회귀 감시 (editing_lab/harness/ACCEPTANCE.md)."""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / "editing_lab" / "harness"
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("acceptance", HERE / "acceptance.py")
acc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acc)

HARNESS = HERE / "harness.py"


@pytest.mark.parametrize("check", [acc.check_A1, acc.check_A2, acc.check_G1])
def test_single_criteria(check):
    ok, note = check(HARNESS)
    assert ok, note


def test_kept_rejections_B1_to_B8():
    res = acc.check_B(HARNESS)
    failed = {k: v[1] for k, v in res.items() if k != "B9" and not v[0]}
    assert not failed, failed


def test_rollback_D1_to_D3():
    res = acc.check_D(HARNESS)
    failed = {k: v[1] for k, v in res.items() if not v[0]}
    assert not failed, failed
