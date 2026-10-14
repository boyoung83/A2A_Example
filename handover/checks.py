"""보고서가 원문 메모에 없는 내용을 지어냈는지 대조하는 점검."""
import re

from handover.schema import HandoverReport

RESOLUTION_WORDS = ["해결", "완료", "정상화", "이상없음", "문제없"]
# 같은 문장에 이 표현이 있으면 단정이 아니라 유보/부정으로 본다.
HEDGE_MARKERS = ["여부", "아님", "않", "미확인", "확인되지", "확정"]

_NUMBER = re.compile(r"\d{1,2}:\d{2}|\d+")


def extract_numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _compact(text: str) -> str:
    return "".join(text.split())


def check_report(report: HandoverReport, memo: str) -> list[str]:
    memo_numbers = extract_numbers(memo)
    memo_norm = _normalize(memo)
    memo_compact = _compact(memo)
    warnings: list[str] = []

    items = report.events + report.actions + report.current_status + report.next_checks
    unconfirmed_texts = [s for u in report.unconfirmed for s in (u.subject, u.note) if s]

    for sentence in [item.text for item in items] + unconfirmed_texts:
        for n in sorted(extract_numbers(sentence) - memo_numbers):
            warnings.append(f"원문에 없는 숫자 '{n}': {sentence}")

    for item in items:
        compact = _compact(item.text)
        if any(marker in compact for marker in HEDGE_MARKERS):
            continue
        for word in RESOLUTION_WORDS:
            if word in compact and word not in memo_compact:
                warnings.append(f"원문에 없는 단정 표현 '{word}': {item.text}")

    for item in items:
        if _normalize(item.source_quote) not in memo_norm:
            warnings.append(f"근거 문장이 원문에 없음: {item.source_quote}")

    return warnings
