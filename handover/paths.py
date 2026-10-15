"""프로그램 기준 폴더 (.env, 참고/, reports/가 있는 곳)."""
import sys
from pathlib import Path


def base_dir() -> Path:
    # 실행 파일(.exe)로 묶었을 때는 exe가 있는 폴더, 소스로 실행할 때는 프로젝트 폴더
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
