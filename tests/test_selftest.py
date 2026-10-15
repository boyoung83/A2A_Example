from handover.selftest import run_selftest


def test_selftest_reports_every_component(tmp_path):
    out = tmp_path / "selftest.txt"
    ok = run_selftest(out)
    text = out.read_text(encoding="utf-8")
    assert ok is True
    for part in ("anthropic", "openpyxl", "ssl", "tkinter", "excel"):
        assert f"[OK] {part}" in text
    assert "결과: 통과" in text
