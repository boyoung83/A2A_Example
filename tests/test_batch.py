import threading

from conftest import SAMPLE_REPORT, FakeClient, make_report
from handover.batch import count_by_priority, find_memos, run_batch
from handover.store import content_hash


def write(folder, name, text):
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def test_find_memos_sorted_txt_only(tmp_path):
    write(tmp_path, "b.txt", "x"); write(tmp_path, "a.txt", "x"); write(tmp_path, "c.md", "x")
    assert [p.name for p in find_memos(tmp_path)] == ["a.txt", "b.txt"]


def test_batch_mixed_results(tmp_path):
    paths = [write(tmp_path, "a.txt", "메모A"), write(tmp_path, "b.txt", "  \n"), write(tmp_path, "c.txt", "메모C")]
    fake = FakeClient(results=[("end_turn", SAMPLE_REPORT), ("refusal", None)])
    items = run_batch(paths, fake, tmp_path / "out", on_update=lambda item: None, workers=1)
    assert [i.status for i in items] == ["완료", "실패", "실패"]
    assert "비어" in items[1].message and "거절" in items[2].message
    assert items[0].record is not None
    assert len(list((tmp_path / "out").glob("*.json"))) == 1


def test_batch_skips_known_hashes(tmp_path):
    paths = [write(tmp_path, "a.txt", "메모A"), write(tmp_path, "b.txt", "메모B")]
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    items = run_batch(paths, fake, tmp_path / "out", on_update=lambda i: None,
                      skip_hashes={content_hash("메모A")}, workers=1)
    assert [i.status for i in items] == ["건너뜀", "완료"]
    assert len(fake.calls) == 1


def test_batch_parallel_all_complete(tmp_path):
    paths = [write(tmp_path, f"{n}.txt", f"메모{n}") for n in range(5)]
    items = run_batch(paths, FakeClient("end_turn", SAMPLE_REPORT), tmp_path / "out", on_update=lambda i: None)
    assert [i.status for i in items] == ["완료"] * 5
    assert len(list((tmp_path / "out").glob("*.txt"))) == 5


def test_batch_update_sequence(tmp_path):
    paths = [write(tmp_path, "a.txt", "메모A"), write(tmp_path, "b.txt", "메모B")]
    seen = []
    lock = threading.Lock()

    def on_update(item):
        with lock:
            seen.append((item.path.name, item.status))

    run_batch(paths, FakeClient("end_turn", SAMPLE_REPORT), tmp_path / "out", on_update=on_update, workers=1)
    assert seen == [("a.txt", "처리 중"), ("a.txt", "완료"), ("b.txt", "처리 중"), ("b.txt", "완료")]


def test_count_by_priority(tmp_path):
    reports = [make_report(priority=p) for p in ("긴급", "주의", "긴급")]
    records = [type("R", (), {"report": r})() for r in reports]
    assert count_by_priority(records) == {"긴급": 2, "주의": 1, "일반": 0}


def test_batch_unexpected_error_marks_failed(tmp_path):
    paths = [write(tmp_path, "a.txt", "메모A")]
    items = run_batch(paths, FakeClient(error=RuntimeError("boom")), tmp_path / "out", on_update=lambda i: None)
    assert items[0].status == "실패" and "boom" in items[0].message
