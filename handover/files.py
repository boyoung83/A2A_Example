"""메모 읽기와 보고서 저장 (CLI와 앱이 함께 사용)."""
from datetime import datetime
from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp949")


def read_memo_file(path: Path) -> str:
    """UTF-8로 읽고, 안 되면 한글 Windows 메모장 기본값(CP949)으로 다시 읽는다."""
    data = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8/cp949", data, 0, len(data), "지원하지 않는 인코딩")


def save_report(text: str, out_dir: Path, source_stem: str, now: datetime) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"인수인계_{source_stem}_{now:%Y%m%d_%H%M%S}"
    path = out_dir / f"{base}.txt"
    n = 2
    while path.exists():
        path = out_dir / f"{base}_{n}.txt"
        n += 1
    path.write_text(text, encoding="utf-8")
    return path
