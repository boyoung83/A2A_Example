import tkinter as tk

import pytest

from conftest import SAMPLE_REPORT, FakeClient, make_report
from handover.schema import Contact, Fact, TimelineEntry, Unconfirmed
from handover.view import build_sections


def test_build_sections_order_and_placeholders():
    r = make_report(unconfirmed=[Unconfirmed(subject="라벨 여분 수량", note="수량은 못 셈."),
                                 Unconfirmed(subject="원인", note="")])
    sections = build_sections(r)
    assert [s.title for s in sections] == ["발생한 일", "조치한 내용", "현재 상태", "다음 근무자 확인 사항",
                                           "시간순 경과", "주요 수치·대상", "연락·요청 현황", "미확인 사항"]
    assert sections[0].lines == ["메모에 기록 없음"]
    assert sections[7].lines == ["라벨 여분 수량: 미확인 (수량은 못 셈.)", "원인: 미확인"]
    assert sections[7].kind == "unconfirmed"


def test_build_sections_detail_formats():
    r = make_report(
        timeline=[TimelineEntry(time="14:10", text="진동 발생", source_quote="q")],
        key_facts=[Fact(label="대기 제품", value="12개", source_quote="q")],
        contacts=[Contact(party="설비팀", request="점검 요청", status="결과 미회신", source_quote="q")],
    )
    by_kind = {s.kind: s.lines for s in build_sections(r)}
    assert by_kind["timeline"] == ["14:10  진동 발생"]
    assert by_kind["facts"] == ["대기 제품: 12개"]
    assert by_kind["contacts"] == ["설비팀 — 점검 요청 — 결과 미회신"]


@pytest.fixture(scope="session")
def tk_session():
    # Tk 인터프리터를 테스트마다 새로 만들면 Windows에서 가끔 초기화가 실패한다 → 세션당 하나만 만든다.
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("화면(Tk)을 사용할 수 없는 환경")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def root(tk_session):
    window = tk.Toplevel(tk_session)
    window.withdraw()
    yield window
    window.destroy()


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


def write_memos(folder, names):
    for name in names:
        (folder / f"{name}.txt").write_text(f"{name} 메모", encoding="utf-8")


def test_dashboard_batch_sorted_and_counted(root, tmp_path):
    write_memos(tmp_path, ["a", "b", "c"])
    fake = FakeClient(results=[("end_turn", make_report(priority=p, summary=p)) for p in ("일반", "긴급", "주의")])
    app = make_app(root, tmp_path, fake)
    app.show_tab("dashboard")
    app.run_batch()
    app.poll_results()
    rows = app.dashboard_rows()
    assert [r[0] for r in rows] == ["긴급", "주의", "일반"]
    assert app.tile_counts() == {"전체": 3, "긴급": 1, "주의": 1, "일반": 1, "경고": 0, "실패": 0}


def test_dashboard_second_batch_skips_processed(root, tmp_path):
    write_memos(tmp_path, ["a", "b"])
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    app = make_app(root, tmp_path, fake)
    app.run_batch()
    app.poll_results()
    app.run_batch()
    app.poll_results()
    assert len(fake.calls) == 2
    assert len(app.dashboard_rows()) == 2


def test_dashboard_empty_folder(root, tmp_path):
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    app = make_app(root, tmp_path, fake)
    app.run_batch()
    assert ".txt 메모가 없습니다" in app.batch_status_text()
    assert fake.calls == []


def test_dashboard_ignores_second_run_while_busy(root, tmp_path):
    write_memos(tmp_path, ["a"])
    jobs = []
    from app import HandoverApp
    app = HandoverApp(root, client_factory=lambda: FakeClient("end_turn", SAMPLE_REPORT),
                      out_dir=tmp_path / "reports", samples_dir=tmp_path, runner=jobs.append)
    app.run_batch()
    app.run_batch()
    assert len(jobs) == 1


def test_dashboard_select_shows_detail(root, tmp_path):
    write_memos(tmp_path, ["a"])
    report = make_report(summary="2호기 누유 의심", priority="긴급", priority_reason="설비 아래 액체 발견")
    app = make_app(root, tmp_path, FakeClient("end_turn", report))
    app.run_batch()
    app.poll_results()
    app.select_dashboard_row(0)
    assert "설비 아래 액체 발견" in app.detail_status_text()


def test_dashboard_loads_existing_records_on_start(root, tmp_path):
    write_memos(tmp_path, ["a"])
    app = make_app(root, tmp_path, FakeClient("end_turn", SAMPLE_REPORT))
    app.run_batch()
    app.poll_results()
    window = tk.Toplevel(root)
    try:
        again = make_app(window, tmp_path, FakeClient("end_turn", SAMPLE_REPORT))
        assert len(again.dashboard_rows()) == 1
    finally:
        window.destroy()
