"""처리 결과(.json)를 보고서(.txt) 옆에 저장하고 대시보드용으로 다시 읽는다."""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pydantic

from handover.schema import PRIORITY_ORDER, UNCLASSIFIED, HandoverReport


@dataclass
class Record:
    source_name: str
    created_at: datetime
    memo_hash: str
    memo: str
    report: HandoverReport
    warnings: list[str]
    txt_path: Path


def content_hash(memo: str) -> str:
    return hashlib.sha256(" ".join(memo.split()).encode("utf-8")).hexdigest()


def save_record(record: Record) -> Path:
    path = record.txt_path.with_suffix(".json")
    data = {
        "source_name": record.source_name,
        "created_at": record.created_at.isoformat(),
        "memo_hash": record.memo_hash,
        "memo": record.memo,
        "report": record.report.model_dump(),
        "warnings": record.warnings,
        "txt_file": record.txt_path.name,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load(path: Path) -> Record | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["report"].setdefault("category", UNCLASSIFIED)  # 문제 유형이 생기기 전에 만든 보고서
        return Record(
            source_name=data["source_name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            memo_hash=data["memo_hash"],
            memo=data["memo"],
            report=HandoverReport.model_validate(data["report"]),
            warnings=list(data["warnings"]),
            txt_path=path.with_name(data["txt_file"]),
        )
    except (OSError, ValueError, KeyError, TypeError, pydantic.ValidationError):
        return None  # 이전 형식이거나 손상된 파일은 대시보드에서 제외


def load_records(out_dir: Path) -> list[Record]:
    if not out_dir.is_dir():
        return []
    # 같은 메모(이름과 내용이 모두 같음)를 다시 처리한 경우만 최신 1건으로 합친다.
    # 이름만 같은 경우(예: 직접 입력한 메모 여러 건)는 서로 다른 건으로 둔다.
    latest: dict[tuple[str, str], Record] = {}
    for path in out_dir.glob("*.json"):
        record = _load(path)
        if record is None:
            continue
        key = (record.source_name, record.memo_hash)
        if key not in latest or record.created_at > latest[key].created_at:
            latest[key] = record
    return list(latest.values())


def sort_for_dashboard(records: list[Record]) -> list[Record]:
    newest_first = sorted(records, key=lambda r: r.created_at, reverse=True)
    return sorted(newest_first, key=lambda r: PRIORITY_ORDER.index(r.report.priority))
