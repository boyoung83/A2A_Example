from datetime import datetime

import pytest

from conftest import SAMPLE_REPORT, FakeClient
from handover.llm import ReportError
from handover.schema import HandoverReport, Item
from handover.service import generate


def test_generate_renders_saves_and_returns_parts(tmp_path):
    now = datetime(2026, 10, 15, 9, 0, 0)
    result = generate("08:40 라벨 비뚤어짐.", "직접 입력", "입력", FakeClient("end_turn", SAMPLE_REPORT), tmp_path, now)
    assert result.report == SAMPLE_REPORT
    assert result.warnings == []
    assert result.path == tmp_path / "인수인계_입력_20261015_090000.txt"
    assert result.path.read_text(encoding="utf-8") == result.text
    assert "■ 발생한 일" in result.text


def test_generate_reports_warnings(tmp_path):
    bad = HandoverReport(events=[Item(text="라벨 10장 남음", source_quote="08:40 라벨 비뚤어짐.")],
                         actions=[], current_status=[], next_checks=[], unconfirmed=[])
    result = generate("08:40 라벨 비뚤어짐.", "m", "m", FakeClient("end_turn", bad), tmp_path)
    assert any("'10'" in w for w in result.warnings)


def test_generate_propagates_report_error_without_saving(tmp_path):
    with pytest.raises(ReportError):
        generate("메모", "m", "m", FakeClient("refusal", None), tmp_path)
    assert list(tmp_path.iterdir()) == []
