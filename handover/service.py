"""메모 하나를 보고서로 만드는 전체 흐름 (CLI와 앱이 함께 사용)."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from handover.checks import check_report
from handover.files import save_report
from handover.llm import summarize
from handover.render import render_report
from handover.schema import HandoverReport
from handover.store import Record, content_hash, save_record


@dataclass
class GenerationResult:
    report: HandoverReport
    warnings: list[str]
    text: str
    path: Path
    record: Record


def generate(memo: str, source_name: str, source_stem: str, client, out_dir: Path,
             now: datetime | None = None) -> GenerationResult:
    report = summarize(memo, client)
    warnings = check_report(report, memo)
    now = now or datetime.now()
    text = render_report(report, memo, source_name, now, warnings)
    path = save_report(text, out_dir, source_stem, now)
    record = Record(source_name, now, content_hash(memo), memo, report, warnings, path)
    save_record(record)
    return GenerationResult(report, warnings, text, path, record)
