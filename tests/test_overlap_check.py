import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "overlap_check", Path(__file__).resolve().parents[1] / "editing_lab" / "tools" / "overlap_check.py"
)
oc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oc)


def test_detects_copied_span_even_with_spacing_changes():
    src = "기계는 과거를 성실하게 배웠다. 그래서 문제가 생겼다."
    tgt = "새 문장이다. 기계는과거를 성실 하게배웠다. 끝."
    r = oc.report(src, tgt, min_chars=8)
    assert r["longest_shared_span"] == "기계는과거를성실하게배웠다."
    assert r["longest_shared_len"] == 14


def test_no_overlap_for_unrelated_texts():
    r = oc.report("하늘이 푸르고 바람이 분다.", "야구장에 주심이 선다.", min_chars=8)
    assert r["shared_spans"] == []
    assert r["eojeol3_shared"] == []
    assert r["target_coverage"] == 0


def test_eojeol_trigrams_shared():
    r = oc.report("바람이 부는 저녁에 창문을 닫았다", "어제 바람이 부는 저녁에 걸었다", min_chars=30)
    assert "바람이 부는 저녁에" in r["eojeol3_shared"]


def test_load_units_json(tmp_path):
    p = tmp_path / "t.json"
    p.write_text('{"units": [{"text": "가나다"}, {"text": "라마"}]}', encoding="utf-8")
    assert oc.load_text(str(p)) == "가나다\n라마"
