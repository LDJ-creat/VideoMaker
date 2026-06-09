from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from structure.slot_roles import VISUAL_ROLES

VISUAL_SLOT_ROLES = VISUAL_ROLES


def provisional_gap_report(
    structure: dict[str, Any],
    slot_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build weak/missing slot ids for quota planning before GapPlanner runs."""
    from app.agents.slot_mapper import classify_slot_matches

    _, weak_ids, missing_ids = classify_slot_matches(structure, slot_matches)
    return {
        "weakSlots": [{"slotId": slot_id} for slot_id in weak_ids],
        "missingSlots": [{"slotId": slot_id} for slot_id in missing_ids],
    }


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _is_visual_slot(slot: dict[str, Any]) -> bool:
    role = str(slot.get("role", ""))
    required = list(slot.get("requiredAssetType") or [])
    if role in VISUAL_SLOT_ROLES:
        return True
    return "video" in required or "image" in required


@dataclass
class VideoGenQuota:
    """Per-generation video quota: each slot may consume up to max_per_slot successful jobs."""

    max_per_slot: int = 1
    max_slots: int = 3
    consumed_slots: dict[str, int] = field(default_factory=dict)

    def __init__(
        self,
        *,
        max_per_slot: int | None = None,
        max_slots: int | None = None,
        consumed_slots: dict[str, int] | None = None,
        # Legacy kwargs (tests / old checkpoints)
        max_calls: int | None = None,
        used: int | None = None,
    ) -> None:
        if max_calls is not None and max_slots is None:
            max_slots = max(0, max_calls)
        if max_per_slot is None:
            max_per_slot = _env_int("VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT", 1)
        if max_slots is None:
            max_slots = _env_int("VIDEOMAKER_VIDEO_GEN_MAX_SLOTS", 3)
        self.max_per_slot = max(0, int(max_per_slot))
        self.max_slots = max(0, int(max_slots))
        if consumed_slots is not None:
            self.consumed_slots = dict(consumed_slots)
        elif used is not None and used > 0:
            # Legacy: treat as one anonymous slot fully used
            self.consumed_slots = {"__legacy__": int(used)}
        else:
            self.consumed_slots = {}

    @property
    def used(self) -> int:
        return sum(
            1
            for count in self.consumed_slots.values()
            if count >= self.max_per_slot
        )

    @property
    def max_calls(self) -> int:
        """Backward-compatible alias: total successful jobs allowed in this generation."""
        return self.max_slots * self.max_per_slot if self.max_per_slot else self.max_slots

    @property
    def remaining_slots(self) -> int:
        return max(0, self.max_slots - self.used)

    @property
    def remaining(self) -> int:
        return self.remaining_slots

    def has_video_quota(self) -> bool:
        return self.remaining_slots > 0

    def can_generate_for_slot(self, slot_id: str) -> bool:
        if not slot_id or self.remaining_slots <= 0:
            return False
        return self.consumed_slots.get(slot_id, 0) < self.max_per_slot

    def consume(self, slot_id: str = "__legacy__") -> bool:
        if not self.can_generate_for_slot(slot_id):
            return False
        self.consumed_slots[slot_id] = self.consumed_slots.get(slot_id, 0) + 1
        return True

    @classmethod
    def from_env(cls) -> VideoGenQuota:
        legacy = os.getenv("VIDEOMAKER_VIDEO_GEN_QUOTA", "").strip()
        max_slots = _env_int("VIDEOMAKER_VIDEO_GEN_MAX_SLOTS", 0)
        if not max_slots and legacy:
            try:
                max_slots = max(0, int(legacy))
            except ValueError:
                max_slots = 1
        if not max_slots:
            max_slots = 3
        return cls(
            max_per_slot=_env_int("VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT", 1),
            max_slots=max_slots,
        )

    @classmethod
    def from_structure(
        cls,
        structure: dict[str, Any],
        *,
        gap_report: dict[str, Any] | None = None,
    ) -> VideoGenQuota:
        slots_by_id = {
            slot["id"]: slot
            for slot in structure.get("slots", [])
            if isinstance(slot, dict) and slot.get("id")
        }
        candidate_ids: set[str] = set()
        if gap_report:
            for bucket in ("weakSlots", "missingSlots"):
                for item in gap_report.get(bucket, []):
                    if isinstance(item, dict) and item.get("slotId"):
                        candidate_ids.add(str(item["slotId"]))
        if not candidate_ids:
            candidate_ids = set(slots_by_id.keys())

        visual_count = sum(
            1
            for slot_id in candidate_ids
            if slot_id in slots_by_id and _is_visual_slot(slots_by_id[slot_id])
        )
        env_cap = _env_int("VIDEOMAKER_VIDEO_GEN_MAX_SLOTS", 0)
        max_slots = visual_count if visual_count > 0 else len(slots_by_id)
        if env_cap > 0:
            max_slots = min(max_slots, env_cap)
        return cls(
            max_per_slot=_env_int("VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT", 1),
            max_slots=max(1, max_slots),
        )

    @classmethod
    def from_checkpoint(cls, data: dict | None) -> VideoGenQuota:
        if not data:
            return cls.from_env()
        if "consumedSlots" in data or "maxSlots" in data or "maxPerSlot" in data:
            consumed = data.get("consumedSlots") or {}
            if not isinstance(consumed, dict):
                consumed = {}
            return cls(
                max_per_slot=int(data.get("maxPerSlot", data.get("max_per_slot", 1))),
                max_slots=int(data.get("maxSlots", data.get("max_slots", 3))),
                consumed_slots={str(k): int(v) for k, v in consumed.items()},
            )
        used = int(data.get("used", 0))
        max_calls = int(data.get("maxCalls", data.get("max_calls", 1)))
        consumed: dict[str, int] = {}
        if used > 0:
            consumed["__legacy__"] = min(used, 1)
        return cls(
            max_per_slot=1,
            max_slots=max(3, max(0, max_calls)),
            consumed_slots=consumed,
        )

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "maxPerSlot": self.max_per_slot,
            "maxSlots": self.max_slots,
            "consumedSlots": dict(self.consumed_slots),
            "used": self.used,
            "maxCalls": self.max_slots * self.max_per_slot if self.max_per_slot else self.max_slots,
        }
