"""작업 메모를 교대 인수인계 보고서로 정리한다.

사용법:
    python handover_report.py                      # 메모를 붙여넣기
    python handover_report.py --file 메모.txt
    python handover_report.py --dir 참고
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

from handover.checks import check_report
from handover.llm import ReportError, summarize
from handover.render import render_report

KEY_FILE = Path(__file__).resolve().parent / "claudeapi.txt"


def load_api_key(env, key_file: Path) -> str | None:
    if env.get("ANTHROPIC_API_KEY"):
        return env["ANTHROPIC_API_KEY"]
    if key_file.is_file():
        for line in key_file.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                return line.strip()
    return None


def read_memo_interactive(stream: TextIO) -> str:
    lines: list[str] = []
    for raw in stream:
        line = raw.rstrip("\n")
        if line == "" and lines and lines[-1] == "":
            lines.pop()
            break
        lines.append(line)
    return "\n".join(lines).strip()


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


def process(memo: str, source_name: str, source_stem: str, out_dir: Path, client) -> Path:
    report = summarize(memo, client)
    warnings = check_report(report, memo)
    now = datetime.now()
    text = render_report(report, memo, source_name, now, warnings)
    print(text)
    path = save_report(text, out_dir, source_stem, now)
    print(f"저장됨: {path}\n")
    return path


def main(argv: list[str] | None = None, client=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="작업 메모를 교대 인수인계 보고서로 정리합니다.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--file", type=Path, help="메모 텍스트 파일 하나")
    source.add_argument("--dir", type=Path, help="폴더 안의 .txt 메모를 각각 처리")
    parser.add_argument("--out", type=Path, default=Path("reports"), help="보고서 저장 폴더 (기본: reports)")
    args = parser.parse_args(argv)

    if args.dir is not None:
        if not args.dir.is_dir():
            print(f"폴더를 찾을 수 없습니다: {args.dir}", file=sys.stderr)
            return 2
        files = sorted(args.dir.glob("*.txt"))
        if not files:
            print(f"폴더에 .txt 메모가 없습니다: {args.dir}", file=sys.stderr)
            return 2
        sources = [(f.name, f.stem, f.read_text(encoding="utf-8-sig")) for f in files]
    elif args.file is not None:
        if not args.file.is_file():
            print(f"파일을 찾을 수 없습니다: {args.file}", file=sys.stderr)
            return 2
        sources = [(args.file.name, args.file.stem, args.file.read_text(encoding="utf-8-sig"))]
    else:
        print("메모를 붙여넣고 빈 줄에서 Enter를 두 번 누르세요.")
        sources = [("직접 입력", "입력", read_memo_interactive(sys.stdin))]

    if args.dir is None and not sources[0][2].strip():
        print("메모가 비어 있습니다.", file=sys.stderr)
        return 2

    if client is None:
        api_key = load_api_key(os.environ, KEY_FILE)
        if not api_key:
            print("API 키가 없습니다. ANTHROPIC_API_KEY 환경변수를 설정하거나 "
                  f"{KEY_FILE.name} 파일에 키를 넣어주세요.", file=sys.stderr)
            return 2
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

    failed = 0
    for name, stem, memo in sources:
        if not memo.strip():
            print(f"[{name}] 메모가 비어 있습니다.", file=sys.stderr)
            failed += 1
            continue
        try:
            process(memo, name, stem, args.out, client)
        except ReportError as e:
            print(f"[{name}] 보고서 생성 실패: {e}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
