from datetime import datetime

from conftest import SAMPLE_REPORT, FakeClient, make_report
from handover.service import generate
from handover.store import Record, content_hash, load_records, save_record, sort_for_dashboard


def record(tmp_path, name, priority="일반", when=datetime(2026, 10, 15, 9, 0), stem=None):
    stem = stem or f"인수인계_{name}_{when:%Y%m%d_%H%M%S}"
    return Record(source_name=name, created_at=when, memo_hash=content_hash(name), memo=name,
                  report=make_report(priority=priority), warnings=[], txt_path=tmp_path / f"{stem}.txt")


def test_save_and_load_roundtrip(tmp_path):
    r = record(tmp_path, "a.txt", "긴급")
    path = save_record(r)
    assert path == r.txt_path.with_suffix(".json")
    assert load_records(tmp_path) == [r]


def test_load_keeps_latest_per_source(tmp_path):
    save_record(record(tmp_path, "a.txt", "일반", datetime(2026, 10, 15, 9, 0)))
    newer = record(tmp_path, "a.txt", "긴급", datetime(2026, 10, 15, 10, 0))
    save_record(newer)
    assert load_records(tmp_path) == [newer]


def test_load_keeps_same_name_with_different_content(tmp_path):
    first = record(tmp_path, "직접 입력", when=datetime(2026, 10, 15, 9, 0), stem="r1")
    second = record(tmp_path, "직접 입력", when=datetime(2026, 10, 15, 10, 0), stem="r2")
    second.memo_hash = content_hash("다른 메모")
    save_record(first); save_record(second)
    assert len(load_records(tmp_path)) == 2


def test_load_skips_old_or_broken_json(tmp_path):
    (tmp_path / "old.json").write_text('{"foo": 1}', encoding="utf-8")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    good = record(tmp_path, "a.txt")
    save_record(good)
    assert load_records(tmp_path) == [good]


def test_load_missing_dir_is_empty(tmp_path):
    assert load_records(tmp_path / "없음") == []


def test_sort_priority_then_newest(tmp_path):
    a = record(tmp_path, "a", "일반", datetime(2026, 10, 15, 9))
    b = record(tmp_path, "b", "긴급", datetime(2026, 10, 15, 9))
    c = record(tmp_path, "c", "주의", datetime(2026, 10, 15, 9))
    d = record(tmp_path, "d", "긴급", datetime(2026, 10, 15, 11))
    assert [r.source_name for r in sort_for_dashboard([a, b, c, d])] == ["d", "b", "c", "a"]


def test_content_hash_ignores_whitespace():
    assert content_hash("a  b\n") == content_hash("a b")
    assert content_hash("a b") != content_hash("a c")


def test_generate_writes_json_sidecar(tmp_path):
    result = generate("08:40 라벨 비뚤어짐.", "m.txt", "m", FakeClient("end_turn", SAMPLE_REPORT), tmp_path,
                      datetime(2026, 10, 15, 9, 0))
    assert result.path.with_suffix(".json").is_file()
    assert result.record.memo_hash == content_hash("08:40 라벨 비뚤어짐.")
    assert load_records(tmp_path) == [result.record]
