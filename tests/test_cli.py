import io
from datetime import datetime

from conftest import SAMPLE_REPORT, FakeClient
from handover.config import load_api_key
from handover_report import main, read_memo_interactive, save_report


def test_file_mode_prints_and_saves(tmp_path, capsys):
    memo = tmp_path / "m.txt"
    memo.write_text("08:40 라벨 비뚤어짐.", encoding="utf-8")
    out_dir = tmp_path / "r"
    assert main(["--file", str(memo), "--out", str(out_dir)], client=FakeClient("end_turn", SAMPLE_REPORT)) == 0
    saved = list(out_dir.glob("인수인계_m_*.txt"))
    assert len(saved) == 1 and "■ 발생한 일" in saved[0].read_text(encoding="utf-8")
    assert "■ 발생한 일" in capsys.readouterr().out


def test_blank_memo_no_api_call(tmp_path, capsys):
    memo = tmp_path / "m.txt"
    memo.write_text("  \n\n", encoding="utf-8")
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    assert main(["--file", str(memo)], client=fake) == 2 and fake.calls == []
    assert "메모가 비어 있습니다" in capsys.readouterr().err


def test_missing_file_exit_2(tmp_path):
    assert main(["--file", str(tmp_path / "없음.txt")], client=FakeClient("end_turn", SAMPLE_REPORT)) == 2


def test_save_no_overwrite(tmp_path):
    now = datetime(2026, 10, 15, 14, 30, 0)
    a = save_report("A", tmp_path, "m", now)
    b = save_report("B", tmp_path, "m", now)
    assert a != b and b.name.endswith("_2.txt") and a.read_text(encoding="utf-8") == "A"


def test_dir_continues_after_failure(tmp_path):
    for n in ("a", "b"):
        (tmp_path / f"{n}.txt").write_text("메모", encoding="utf-8")
    fake = FakeClient(results=[("refusal", None), ("end_turn", SAMPLE_REPORT)])
    out_dir = tmp_path / "r"
    assert main(["--dir", str(tmp_path), "--out", str(out_dir)], client=fake) == 1
    assert len(list(out_dir.glob("*.txt"))) == 1


def test_interactive_reader_stops_at_double_blank():
    assert read_memo_interactive(io.StringIO("줄1\n\n줄2\n\n\n무시")) == "줄1\n\n줄2"


def test_api_key_env_wins(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-file", encoding="utf-8")
    assert load_api_key({"ANTHROPIC_API_KEY": "sk-env"}, env_file) == "sk-env"


def test_api_key_from_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('﻿# 주석\nOTHER=1\nexport ANTHROPIC_API_KEY = "sk-file"  \n', encoding="utf-8")
    assert load_api_key({}, env_file) == "sk-file"


def test_api_key_missing(tmp_path):
    (tmp_path / ".env").write_text("OTHER=1\n", encoding="utf-8")
    assert load_api_key({}, tmp_path / ".env") is None
    assert load_api_key({}, tmp_path / "없음.env") is None


def test_dir_reads_cp949_and_skips_undecodable(tmp_path):
    (tmp_path / "a.txt").write_bytes("08:40 라벨 비뚤어짐.".encode("cp949"))
    (tmp_path / "b.txt").write_bytes(b"\x80\xff\x80\xff")
    (tmp_path / "c.txt").write_text("메모", encoding="utf-8")
    out_dir = tmp_path / "r"
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    assert main(["--dir", str(tmp_path), "--out", str(out_dir)], client=fake) == 1
    assert len(list(out_dir.glob("*.txt"))) == 2
    assert "라벨 비뚤어짐" in fake.calls[0]["messages"][0]["content"]
