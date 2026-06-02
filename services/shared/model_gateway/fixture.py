from __future__ import annotations

import os


def is_fixture_mode() -> bool:
    """True only when VIDEOMAKER_FIXTURE_MODE is truthy (default: live / false)."""
    raw = os.getenv("VIDEOMAKER_FIXTURE_MODE")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}
