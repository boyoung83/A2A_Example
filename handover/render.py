"""HandoverReport를 고정 양식의 인수인계 보고서 텍스트로 만든다."""
from datetime import datetime

from handover.schema import HandoverReport
from handover.view import build_sections

DOUBLE = "=" * 30
SINGLE = "-" * 30


def render_report(report: HandoverReport, memo: str, source_name: str,
                  created_at: datetime, warnings: list[str]) -> str:
    lines = [
        DOUBLE,
        " 교대 인수인계 보고서",
        f" 작성: {created_at:%Y-%m-%d %H:%M} / 원문: {source_name}",
        f" 긴급도: [{report.priority}] {report.priority_reason}",
        f" 요약: {report.summary}",
        DOUBLE,
    ]
    for section in build_sections(report):
        lines.append(f"■ {section.title}")
        lines += [f"- {line}" for line in section.lines]

    lines.append(SINGLE)
    if warnings:
        lines.append("※ 자동 점검 경고 (원문과 대조해 확인하세요)")
        lines += [f"- {w}" for w in warnings]
    else:
        lines.append("※ 자동 점검: 이상 없음")
    lines += [SINGLE, "[원문 메모]", memo.strip()]
    return "\n".join(lines) + "\n"
