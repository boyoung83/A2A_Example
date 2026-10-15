import pydantic
import pytest

from conftest import make_report
from handover.schema import Contact, Fact, HandoverReport, Item, TimelineEntry, Unconfirmed


def test_report_roundtrip():
    r = make_report(
        summary="라벨 비뚤어짐",
        events=[Item(text="라벨 비뚤어짐", source_quote="08:40 포장 2호기 라벨이 자꾸 비뚤어짐.")],
        timeline=[TimelineEntry(time="08:40", text="라벨 비뚤어짐", source_quote="08:40 포장 2호기 라벨이 자꾸 비뚤어짐.")],
        key_facts=[Fact(label="확인 수량", value="20개", source_quote="이후 20개 확인했는데 정상.")],
        contacts=[Contact(party="오후조", request="재확인", status="회신 여부 미기록", source_quote="오후조에서 다시 확인 필요.")],
        unconfirmed=[Unconfirmed(subject="원인", note="")],
        priority="주의", priority_reason="원인 미확인",
    )
    assert HandoverReport.model_validate_json(r.model_dump_json()) == r


def test_field_order_puts_judgement_last():
    assert list(HandoverReport.model_fields) == [
        "summary", "events", "actions", "current_status", "next_checks",
        "timeline", "key_facts", "contacts", "unconfirmed", "category", "priority_reason", "priority"]


def test_priority_values_restricted():
    with pytest.raises(pydantic.ValidationError):
        make_report(priority="급함")
