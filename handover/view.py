"""화면에 그릴 보고서 섹션 (앱 전용, tkinter와 분리해 테스트 가능하게 둔다)."""
from dataclasses import dataclass

from handover.schema import HandoverReport, Item

EMPTY = "메모에 기록 없음"


@dataclass
class Section:
    title: str
    kind: str  # events / actions / status / checks / unconfirmed
    lines: list[str]


def _texts(items: list[Item]) -> list[str]:
    return [item.text for item in items] or [EMPTY]


def build_sections(report: HandoverReport) -> list[Section]:
    unconfirmed = [f"{u.subject}: 미확인" + (f" ({u.note})" if u.note else "") for u in report.unconfirmed]
    return [
        Section("발생한 일", "events", _texts(report.events)),
        Section("조치한 내용", "actions", _texts(report.actions)),
        Section("현재 상태", "status", _texts(report.current_status)),
        Section("다음 근무자 확인 사항", "checks", _texts(report.next_checks)),
        Section("미확인 사항", "unconfirmed", unconfirmed or [EMPTY]),
    ]
