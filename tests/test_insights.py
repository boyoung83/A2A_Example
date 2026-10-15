import json
from datetime import datetime

import pytest

from conftest import FakeClient, make_report
from handover.insights import (InsightPoint, Insights, build_insight_input, extract_insights, load_insights,
                               save_insights)
from handover.llm import ReportError
from handover.schema import Contact, Item, Unconfirmed
from handover.store import Record


def rec(tmp_path, name, priority="일반", **kw):
    report = make_report(priority=priority, summary=f"{name} 요약", priority_reason=f"{name} 이유", **kw)
    return Record(source_name=name, created_at=datetime(2026, 10, 15, 9, 0), memo_hash=name, memo="m",
                  report=report, warnings=[], txt_path=tmp_path / f"{name}.txt")


SAMPLE = Insights(
    headline="설비 이상 2건이 교대 시점까지 해결되지 않음",
    patterns=[InsightPoint(title="설비팀 회신 대기", detail="두 건 모두 점검 결과 미회신", related=["a.txt", "b.txt"])],
    risks=[InsightPoint(title="재발 알람", detail="같은 알람 재발", related=["b.txt", "없는메모.txt"])],
    gaps=[InsightPoint(title="원인 미기록", detail="원인이 반복적으로 미확인", related=["a.txt"])],
)


def test_input_contains_compact_record_facts(tmp_path):
    r = rec(tmp_path, "a.txt", "긴급",
            events=[Item(text="2호기 진동", source_quote="q")],
            unconfirmed=[Unconfirmed(subject="원인", note="")],
            contacts=[Contact(party="설비팀", request="점검", status="미회신", source_quote="q")])
    data = json.loads(build_insight_input([r]))
    assert data == [{"memo": "a.txt", "priority": "긴급", "reason": "a.txt 이유", "summary": "a.txt 요약",
                     "events": ["2호기 진동"], "unconfirmed": ["원인"], "contacts": ["설비팀 — 점검 — 미회신"]}]


def test_extract_drops_unknown_related_names(tmp_path):
    fake = FakeClient("end_turn", SAMPLE)
    out = extract_insights([rec(tmp_path, "a.txt"), rec(tmp_path, "b.txt")], fake)
    assert out.risks[0].related == ["b.txt"]
    kw = fake.insight_calls[0]
    assert kw["output_format"] is Insights and "a.txt" in kw["messages"][0]["content"]
    assert "근거" in kw["system"]


def test_extract_needs_records():
    with pytest.raises(ReportError, match="보고서가 없습니다"):
        extract_insights([], FakeClient("end_turn", SAMPLE))


def test_extract_refusal_raises(tmp_path):
    with pytest.raises(ReportError, match="거절"):
        extract_insights([rec(tmp_path, "a.txt")], FakeClient("refusal", None))


def test_save_and_load_snapshot(tmp_path):
    records = [rec(tmp_path, "a.txt"), rec(tmp_path, "b.txt")]
    save_insights(tmp_path, SAMPLE, records, datetime(2026, 10, 15, 10, 0))
    snap = load_insights(tmp_path)
    assert snap.insights == SAMPLE
    assert snap.created_at == datetime(2026, 10, 15, 10, 0)
    assert snap.source_count == 2
    assert snap.is_current(records)
    assert not snap.is_current(records + [rec(tmp_path, "c.txt")])


def test_load_missing_or_broken_snapshot(tmp_path):
    assert load_insights(tmp_path) is None
    (tmp_path / "insights.json").write_text("{", encoding="utf-8")
    assert load_insights(tmp_path) is None
