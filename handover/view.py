"""화면·텍스트 보고서에 쓸 섹션 구성 (tkinter와 분리해 테스트 가능하게 둔다)."""
from dataclasses import dataclass

from handover.schema import HandoverReport, Item

EMPTY = "메모에 기록 없음"


@dataclass
class Section:
    title: str
    kind: str  # events / actions / status / checks / timeline / facts / contacts / unconfirmed
    lines: list[str]


def _texts(items: list[Item]) -> list[str]:
    return [item.text for item in items] or [EMPTY]


OTHER = "기타"
# 원형 그래프에서 고정 색을 갖는 유형 (색은 순위가 아니라 유형을 따라간다). 나머지는 '기타'로 묶는다.
PIE_TYPES = ["설비 이상", "수량 불일치", "품질·검사", "안전", "라벨·식별"]
NOT_A_PROBLEM = "정상·기록"  # '문제 유형' 비율에서는 뺀다


def pie_groups(records) -> list[tuple[str, int]]:
    """원형 그래프 조각: 고정 유형(정해진 순서) → 기타 → 미분류. 0건인 조각과 정상·기록은 뺀다."""
    from handover.schema import UNCLASSIFIED
    counts: dict[str, int] = {}
    for r in records:
        c = r.report.category
        if c == NOT_A_PROBLEM:
            continue
        key = c if c in PIE_TYPES or c == UNCLASSIFIED else OTHER
        counts[key] = counts.get(key, 0) + 1
    order = PIE_TYPES + [OTHER, UNCLASSIFIED]
    return [(key, counts[key]) for key in order if counts.get(key)]


def other_breakdown(records) -> list[tuple[str, int]]:
    """'기타'에 묶인 유형별 건수 (많은 순)."""
    from handover.schema import UNCLASSIFIED
    counts: dict[str, int] = {}
    for r in records:
        c = r.report.category
        if c not in PIE_TYPES and c not in (UNCLASSIFIED, NOT_A_PROBLEM):
            counts[c] = counts.get(c, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


def unconfirmed_ranking(records, limit: int = 8) -> list[tuple[str, str, int]]:
    """미확인 항목이 많은 메모 순 (같으면 긴급도 순). 미확인이 없는 메모는 뺀다."""
    from handover.schema import PRIORITY_ORDER
    rows = [(r.source_name, r.report.priority, len(r.report.unconfirmed)) for r in records]
    rows = [row for row in rows if row[2] > 0]
    rows.sort(key=lambda row: (-row[2], PRIORITY_ORDER.index(row[1])))
    return rows[:limit]


def build_sections(report: HandoverReport) -> list[Section]:
    timeline = [f"{t.time}  {t.text}" for t in report.timeline]
    facts = [f"{f.label}: {f.value}" for f in report.key_facts]
    contacts = [f"{c.party} — {c.request} — {c.status}" for c in report.contacts]
    unconfirmed = [f"{u.subject}: 미확인" + (f" ({u.note})" if u.note else "") for u in report.unconfirmed]
    return [
        Section("발생한 일", "events", _texts(report.events)),
        Section("조치한 내용", "actions", _texts(report.actions)),
        Section("현재 상태", "status", _texts(report.current_status)),
        Section("다음 근무자 확인 사항", "checks", _texts(report.next_checks)),
        Section("시간순 경과", "timeline", timeline or [EMPTY]),
        Section("주요 수치·대상", "facts", facts or [EMPTY]),
        Section("연락·요청 현황", "contacts", contacts or [EMPTY]),
        Section("미확인 사항", "unconfirmed", unconfirmed or [EMPTY]),
    ]
