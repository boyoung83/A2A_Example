import json
from datetime import datetime

import pydantic
import pytest

from conftest import FakeClient, make_report
from handover.classify import Classification, MemoCategory, classify_missing
from handover.schema import CATEGORIES
from handover.store import Record, load_records, save_record
from handover.view import other_breakdown, pie_groups


def rec(tmp_path, name, category="설비 이상", stem=None):
    return Record(source_name=name, created_at=datetime(2026, 10, 15, 9, 0), memo_hash=name, memo=f"{name} 메모",
                  report=make_report(category=category), warnings=[],
                  txt_path=tmp_path / f"{stem or name}.txt")


def test_category_values_restricted():
    assert "설비 이상" in CATEGORIES and "수량 불일치" in CATEGORIES
    with pytest.raises(pydantic.ValidationError):
        make_report(category="아무거나")


def test_old_record_without_category_loads_as_unclassified(tmp_path):
    path = save_record(rec(tmp_path, "a.txt"))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["report"]["category"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert load_records(tmp_path)[0].report.category == "미분류"


def test_classify_missing_updates_only_unclassified(tmp_path):
    a, b = rec(tmp_path, "a.txt", "미분류"), rec(tmp_path, "b.txt", "안전")
    save_record(a); save_record(b)
    fake = FakeClient(classification=Classification(items=[
        MemoCategory(memo="a.txt", category="수량 불일치"), MemoCategory(memo="없음.txt", category="안전")]))
    changed = classify_missing([a, b], fake)
    assert changed == 1 and a.report.category == "수량 불일치" and b.report.category == "안전"
    assert len(fake.classify_calls) == 1 and "a.txt" in fake.classify_calls[0]["messages"][0]["content"]
    assert "b.txt" not in fake.classify_calls[0]["messages"][0]["content"]
    assert {r.source_name: r.report.category for r in load_records(tmp_path)} == {"a.txt": "수량 불일치", "b.txt": "안전"}


def test_classify_missing_handles_same_name_records(tmp_path):
    a1, a2 = rec(tmp_path, "a.txt", "미분류", stem="r1"), rec(tmp_path, "a.txt", "미분류", stem="r2")
    fake = FakeClient(classification=Classification(items=[MemoCategory(memo="a.txt", category="안전")]))
    assert classify_missing([a1, a2], fake) == 2
    assert a1.report.category == a2.report.category == "안전"


def test_classify_missing_skips_call_when_all_classified(tmp_path):
    fake = FakeClient()
    assert classify_missing([rec(tmp_path, "a.txt", "안전")], fake) == 0
    assert fake.classify_calls == []


def test_pie_groups_fixed_order_other_and_unclassified(tmp_path):
    cats = ["안전"] * 2 + ["설비 이상"] * 4 + ["서류·전산", "서류·전산", "정상·기록", "미분류"]
    records = [rec(tmp_path, f"{i}.txt", c) for i, c in enumerate(cats)]
    # 색이 유형을 따라가도록 순서는 건수가 아니라 고정 순서. 정상·기록은 '문제 유형'이 아니므로 뺀다.
    assert pie_groups(records) == [("설비 이상", 4), ("안전", 2), ("기타", 2), ("미분류", 1)]
    assert other_breakdown(records) == [("서류·전산", 2)]
