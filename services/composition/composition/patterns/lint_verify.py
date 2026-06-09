from __future__ import annotations

import json
from pathlib import Path


def lint_log_confirms_pass(log_path: Path) -> bool:
    if not log_path.is_file():
        return False
    try:
        payload = json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(payload.get("ok"))
