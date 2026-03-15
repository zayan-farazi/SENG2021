from __future__ import annotations

import os
from pathlib import Path


def load_local_env_files() -> None:
    for env_file in candidate_env_files():
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, value = parse_env_line(line)
            if key and value is not None:
                os.environ.setdefault(key, value)


def candidate_env_files() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    return [
        backend_dir / ".env",
        backend_dir / ".env.local",
        repo_root / ".env",
        repo_root / ".env.local",
    ]


def parse_env_line(line: str) -> tuple[str | None, str | None]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None, None

    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()

    if "=" not in stripped:
        return None, None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
        return None, None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value
