"""HandoverReport를 고정 양식의 인수인계 보고서 텍스트로 만든다."""
from datetime import datetime

from handover.schema import HandoverReport, Item

EMPTY = "- 메모에 기록 없음"
DOUBLE = "=" * 30
SINGLE = "-" * 30


def _items(items: list[Item]) -> list[str]:
    return [f"- {item.text}" for item in items] or [EMPTY]


def render_report(report: HandoverReport, memo: str, source_name: str,
                  created_at: datetime, warnings: list[str]) -> str:
    lines = [
        DOUBLE,
        " 교대 인수인계 보고서",
        f" 작성: {created_at:%Y-%m-%d %H:%M} / 원문: {source_name}",
        DOUBLE,
        "■ 발생한 일", *_items(report.events),
        "■ 조치한 내용", *_items(report.actions),
        "■ 현재 상태", *_items(report.current_status),
        "■ 다음 근무자 확인 사항", *_items(report.next_checks),
        "■ 미확인 사항",
    ]
    unconfirmed = [f"- {u.subject}: 미확인" + (f" ({u.note})" if u.note else "")
                   for u in report.unconfirmed]
    lines += unconfirmed or [EMPTY]

    lines.append(SINGLE)
    if warnings:
        lines.append("※ 자동 점검 경고 (원문과 대조해 확인하세요)")
        lines += [f"- {w}" for w in warnings]
    else:
        lines.append("※ 자동 점검: 이상 없음")
    lines += [SINGLE, "[원문 메모]", memo.strip()]
    return "\n".join(lines) + "\n"
