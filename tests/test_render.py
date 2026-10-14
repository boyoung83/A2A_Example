from datetime import datetime

from handover.render import render_report
from handover.schema import HandoverReport, Unconfirmed


def empty_report():
    return HandoverReport(events=[], actions=[], current_status=[], next_checks=[], unconfirmed=[])


def test_section_order_and_empty():
    out = render_report(empty_report(), "메모", "a.txt", datetime(2026, 10, 15, 14, 30), [])
    heads = ["■ 발생한 일", "■ 조치한 내용", "■ 현재 상태", "■ 다음 근무자 확인 사항", "■ 미확인 사항"]
    positions = [out.index(h) for h in heads]
    assert positions == sorted(positions)
    assert out.count("- 메모에 기록 없음") == 5
    assert "작성: 2026-10-15 14:30 / 원문: a.txt" in out
    assert "※ 자동 점검: 이상 없음" in out


def test_unconfirmed_format():
    r = empty_report()
    r.unconfirmed = [Unconfirmed(subject="라벨 여분 수량", note="메모에 '얼마 안 남음'만 기록"),
                     Unconfirmed(subject="원인", note="")]
    out = render_report(r, "메모", "a.txt", datetime(2026, 10, 15), [])
    assert "- 라벨 여분 수량: 미확인 (메모에 '얼마 안 남음'만 기록)" in out
    assert "- 원인: 미확인\n" in out


def test_warnings_and_memo_appended():
    out = render_report(empty_report(), "원문내용", "a.txt", datetime(2026, 10, 15), ["원문에 없는 숫자 '10': x"])
    assert "- 원문에 없는 숫자 '10': x" in out
    assert "※ 자동 점검: 이상 없음" not in out
    assert "[원문 메모]" in out and out.rstrip().endswith("원문내용")
