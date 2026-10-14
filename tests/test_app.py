import tkinter as tk

import pytest

from conftest import SAMPLE_REPORT, FakeClient
from handover.schema import HandoverReport, Unconfirmed
from handover.view import build_sections


def test_build_sections_order_and_placeholders():
    r = HandoverReport(events=[], actions=[], current_status=[], next_checks=[],
                       unconfirmed=[Unconfirmed(subject="라벨 여분 수량", note="수량은 못 셈."),
                                    Unconfirmed(subject="원인", note="")])
    sections = build_sections(r)
    assert [s.title for s in sections] == ["발생한 일", "조치한 내용", "현재 상태", "다음 근무자 확인 사항", "미확인 사항"]
    assert sections[0].lines == ["메모에 기록 없음"]
    assert sections[4].lines == ["라벨 여분 수량: 미확인 (수량은 못 셈.)", "원인: 미확인"]
    assert sections[4].kind == "unconfirmed"


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("화면(Tk)을 사용할 수 없는 환경")
    r.withdraw()
    yield r
    r.destroy()


def make_app(root, tmp_path, client):
    from app import HandoverApp
    return HandoverApp(root, client_factory=lambda: client, out_dir=tmp_path / "reports",
                       samples_dir=tmp_path, runner=lambda fn: fn())


def test_app_generates_saves_and_lists_history(root, tmp_path):
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    app = make_app(root, tmp_path, fake)
    app.load_memo_text("08:40 라벨 비뚤어짐.", "작업메모_01")
    app.generate()
    app.poll_results()
    saved = list((tmp_path / "reports").glob("인수인계_작업메모_01_*.txt"))
    assert len(saved) == 1
    assert app.history_paths == saved
    assert "이상 없음" in app.status_text()


def test_app_blank_memo_does_not_call_api(root, tmp_path):
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    app = make_app(root, tmp_path, fake)
    app.generate()
    assert fake.calls == []
    assert "메모를 입력" in app.status_text()


def test_app_shows_error_on_failure(root, tmp_path):
    app = make_app(root, tmp_path, FakeClient("refusal", None))
    app.load_memo_text("메모", "m")
    app.generate()
    app.poll_results()
    assert "거절" in app.status_text()
    assert not (tmp_path / "reports").exists() or not list((tmp_path / "reports").iterdir())
