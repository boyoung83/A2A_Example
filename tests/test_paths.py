import sys
from pathlib import Path

from handover.paths import base_dir


def test_base_dir_is_project_root_when_running_from_source():
    assert (base_dir() / "app.py").is_file()


def test_base_dir_is_exe_folder_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "HandoverReport.exe"))
    assert base_dir() == tmp_path
