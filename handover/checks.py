"""보고서가 원문 메모에 없는 내용을 지어냈는지 대조하는 점검."""
import re

from handover.schema import HandoverReport

RESOLUTION_WORDS = ["해결", "완료", "정상화", "이상 없음", "문제없"]

_NUMBER = re.compile(r"\d{1,2}:\d{2}|\d+")


def extract_numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _normalize(text: str) -> str:
    return " ".join(text.split())


def check_report(report: HandoverReport, memo: str) -> list[str]:
    memo_numbers = extract_numbers(memo)
    memo_norm = _normalize(memo)
    warnings: list[str] = []

    sentences = [item.text for item in report.events + report.actions
                 + report.current_status + report.next_checks]
    sentences += [s for u in report.unconfirmed for s in (u.subject, u.note) if s]

    for sentence in sentences:
        for n in sorted(extract_numbers(sentence) - memo_numbers):
            warnings.append(f"원문에 없는 숫자 '{n}': {sentence}")
        for word in RESOLUTION_WORDS:
            if word in sentence and word not in memo:
                warnings.append(f"원문에 없는 단정 표현 '{word}': {sentence}")

    for item in report.events + report.actions + report.current_status + report.next_checks:
        if _normalize(item.source_quote) not in memo_norm:
            warnings.append(f"근거 문장이 원문에 없음: {item.source_quote}")

    return warnings
