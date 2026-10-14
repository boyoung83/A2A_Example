import pytest

from conftest import SAMPLE_REPORT, FakeClient
from handover.llm import ReportError, summarize
from handover.schema import HandoverReport


def test_summarize_returns_parsed():
    fake = FakeClient(stop_reason="end_turn", parsed=SAMPLE_REPORT)
    assert summarize("메모A", fake) == SAMPLE_REPORT
    kw = fake.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["output_format"] is HandoverReport
    assert "메모A" in kw["messages"][0]["content"] and "미확인" in kw["system"]


def test_refusal_raises():
    with pytest.raises(ReportError, match="거절"):
        summarize("메모", FakeClient(stop_reason="refusal", parsed=None))


def test_unparsed_raises():
    with pytest.raises(ReportError):
        summarize("메모", FakeClient(stop_reason="end_turn", parsed=None))
