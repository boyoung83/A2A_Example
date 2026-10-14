from datetime import datetime

from conftest import make_report
from handover.render import render_report
from handover.schema import Contact, Fact, TimelineEntry, Unconfirmed

HEADS = ["■ 발생한 일", "■ 조치한 내용", "■ 현재 상태", "■ 다음 근무자 확인 사항",
         "■ 시간순 경과", "■ 주요 수치·대상", "■ 연락·요청 현황", "■ 미확인 사항"]


def test_header_priority_and_summary():
    r = make_report(summary="2호기 누유 의심", priority="긴급", priority_reason="설비 아래 액체 발견, 설비 사용 중지 상태")
    out = render_report(r, "메모", "a.txt", datetime(2026, 10, 15, 14, 30), [])
    assert " 긴급도: [긴급] 설비 아래 액체 발견, 설비 사용 중지 상태" in out
    assert " 요약: 2호기 누유 의심" in out
    assert "작성: 2026-10-15 14:30 / 원문: a.txt" in out
    assert out.index("긴급도") < out.index("요약") < out.index("■ 발생한 일")


def test_section_order_and_empty():
    out = render_report(make_report(), "메모", "a.txt", datetime(2026, 10, 15, 14, 30), [])
    positions = [out.index(h) for h in HEADS]
    assert positions == sorted(positions)
    assert out.count("- 메모에 기록 없음") == 8
    assert "※ 자동 점검: 이상 없음" in out


def test_detail_line_formats():
    r = make_report(
        timeline=[TimelineEntry(time="14:10", text="진동 발생, 작업 중지", source_quote="q")],
        key_facts=[Fact(label="대기 제품", value="12개", source_quote="q")],
        contacts=[Contact(party="설비팀", request="점검 요청", status="결과 미회신", source_quote="q")],
    )
    out = render_report(r, "메모", "a.txt", datetime(2026, 10, 15), [])
    assert "- 14:10  진동 발생, 작업 중지" in out
    assert "- 대기 제품: 12개" in out
    assert "- 설비팀 — 점검 요청 — 결과 미회신" in out


def test_unconfirmed_format():
    r = make_report(unconfirmed=[Unconfirmed(subject="라벨 여분 수량", note="메모에 '얼마 안 남음'만 기록"),
                                 Unconfirmed(subject="원인", note="")])
    out = render_report(r, "메모", "a.txt", datetime(2026, 10, 15), [])
    assert "- 라벨 여분 수량: 미확인 (메모에 '얼마 안 남음'만 기록)" in out
    assert "- 원인: 미확인\n" in out


def test_warnings_and_memo_appended():
    out = render_report(make_report(), "원문내용", "a.txt", datetime(2026, 10, 15), ["원문에 없는 숫자 '10': x"])
    assert "- 원문에 없는 숫자 '10': x" in out
    assert "※ 자동 점검: 이상 없음" not in out
    assert "[원문 메모]" in out and out.rstrip().endswith("원문내용")
