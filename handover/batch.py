"""폴더의 메모를 한 번에 처리한다. 한 건이 실패해도 나머지는 계속한다."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from handover.files import read_memo_file
from handover.llm import ReportError
from handover.schema import PRIORITY_ORDER
from handover.service import generate
from handover.store import Record, content_hash


@dataclass
class BatchItem:
    path: Path
    status: str  # 대기 / 처리 중 / 완료 / 건너뜀 / 실패
    message: str = ""
    record: Record | None = None


def find_memos(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.txt"))


def _process(item: BatchItem, client, out_dir: Path, skip_hashes: set[str],
             on_update: Callable[[BatchItem], None]):
    item.status = "처리 중"
    on_update(item)
    try:
        memo = read_memo_file(item.path)
        if not memo.strip():
            item.status, item.message = "실패", "메모가 비어 있습니다"
        elif content_hash(memo) in skip_hashes:
            item.status, item.message = "건너뜀", "이미 처리한 메모"
        else:
            result = generate(memo, item.path.name, item.path.stem, client, out_dir)
            item.status, item.record = "완료", result.record
    except UnicodeDecodeError:
        item.status, item.message = "실패", "파일을 읽지 못했습니다 (UTF-8/CP949가 아님)"
    except ReportError as e:
        item.status, item.message = "실패", str(e)
    except OSError as e:
        item.status, item.message = "실패", f"파일 처리 실패: {e}"
    except Exception as e:  # 워커 스레드의 예외는 밖으로 나오지 않으므로 여기서 실패로 기록한다
        item.status, item.message = "실패", f"예상치 못한 오류: {e}"
    on_update(item)


def run_batch(paths: list[Path], client, out_dir: Path, on_update: Callable[[BatchItem], None],
              skip_hashes: set[str] | None = None, workers: int = 4) -> list[BatchItem]:
    items = [BatchItem(path, "대기") for path in paths]
    skip = skip_hashes or set()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for item in items:
            pool.submit(_process, item, client, out_dir, skip, on_update)
    return items


def count_by_priority(records) -> dict[str, int]:
    counts = {p: 0 for p in PRIORITY_ORDER}
    for record in records:
        counts[record.report.priority] += 1
    return counts
