from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class VideoGenQuota:
    """Per-generation video job quota shared by gap planning and material execution."""

    max_calls: int = 1
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    def has_video_quota(self) -> bool:
        return self.remaining > 0

    def consume(self) -> bool:
        if self.used >= self.max_calls:
            return False
        self.used += 1
        return True

    @classmethod
    def from_env(cls) -> VideoGenQuota:
        raw = os.getenv("VIDEOMAKER_VIDEO_GEN_QUOTA", "1")
        try:
            max_calls = max(0, int(raw))
        except ValueError:
            max_calls = 1
        return cls(max_calls=max_calls, used=0)

    @classmethod
    def from_checkpoint(cls, data: dict | None) -> VideoGenQuota:
        if not data:
            return cls()
        used = int(data.get("used", 0))
        max_calls = int(data.get("maxCalls", data.get("max_calls", 1)))
        return cls(max_calls=max(0, max_calls), used=max(0, used))

    def to_checkpoint(self) -> dict[str, int]:
        return {"used": self.used, "maxCalls": self.max_calls}
