"""실행 파일 점검: 필요한 구성 요소가 모두 들어 있는지 확인한다 (API는 호출하지 않음).

사용: HandoverReport.exe --selftest  → exe 폴더에 selftest.txt 생성
"""
import tempfile
from datetime import datetime
from pathlib import Path


def _checks():
    def anthropic_client():
        import anthropic
        anthropic.Anthropic(api_key="selftest")  # 클라이언트 생성까지만 (네트워크 호출 없음)
        return anthropic.__version__

    def openpyxl_lib():
        import openpyxl
        return openpyxl.__version__

    def ssl_lib():
        import ssl
        ssl.create_default_context()
        return ssl.OPENSSL_VERSION

    def tkinter_lib():
        import tkinter
        return str(tkinter.TkVersion)

    def excel_export():
        from handover.export import export_workbook
        from handover.schema import HandoverReport
        from handover.store import Record
        report = HandoverReport(summary="점검", events=[], actions=[], current_status=[], next_checks=[],
                                timeline=[], key_facts=[], contacts=[], unconfirmed=[], category="정상·기록",
                                priority_reason="점검", priority="일반")
        with tempfile.TemporaryDirectory() as tmp:
            record = Record("점검.txt", datetime.now(), "h", "m", report, [], Path(tmp) / "점검.txt")
            path = export_workbook([record], None, Path(tmp) / "점검.xlsx")
            return f"{path.stat().st_size} bytes"

    return [("anthropic", anthropic_client), ("openpyxl", openpyxl_lib), ("ssl", ssl_lib),
            ("tkinter", tkinter_lib), ("excel", excel_export)]


def run_selftest(out_path: Path) -> bool:
    lines, ok = [f"실행 파일 점검 {datetime.now():%Y-%m-%d %H:%M:%S}"], True
    for name, check in _checks():
        try:
            lines.append(f"[OK] {name}: {check()}")
        except Exception as e:  # 점검 도구이므로 어떤 실패든 기록한다
            ok = False
            lines.append(f"[실패] {name}: {type(e).__name__}: {e}")
    lines.append("결과: 통과" if ok else "결과: 실패")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ok
