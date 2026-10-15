"""API 키 설정: 환경변수 ANTHROPIC_API_KEY, 없으면 프로젝트 폴더의 .env."""
from pathlib import Path

from handover.paths import base_dir

KEY_NAME = "ANTHROPIC_API_KEY"
ENV_FILE = base_dir() / ".env"


def load_api_key(env, env_file: Path = ENV_FILE) -> str | None:
    if env.get(KEY_NAME):
        return env[KEY_NAME]
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        if name == KEY_NAME:
            return value.strip().strip("'\"") or None
    return None
