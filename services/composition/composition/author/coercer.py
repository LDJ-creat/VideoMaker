from __future__ import annotations

from typing import Any

_ROLE_DEFAULT_TEMPLATE: dict[str, str] = {
    "benefit_card": "benefit-card",
    "comparison": "benefit-card",
    "proof": "benefit-card",
    "transition": "benefit-card",
    "cta": "benefit-card",
    "hook_text": "title-lower-third",
    "hook_visual": "ken-burns",
    "product_closeup": "ken-burns",
    "usage_scene": "ken-burns",
}


def fallback_legacy_spec(slot: dict[str, Any], *, duration_sec: float = 3.0) -> dict[str, Any]:
    role = str(slot.get("role", "")).strip()
    template = _ROLE_DEFAULT_TEMPLATE.get(role, "benefit-card")
    title = str(slot.get("scriptIntent") or slot.get("visualIntent") or "VideoMaker")[:120]
    params: dict[str, Any] = {"title": title}
    visual = str(slot.get("visualIntent", "")).strip()
    if template == "benefit-card" and visual:
        params["bullets"] = [visual[:160]]
    return {
        "template": template,
        "durationSec": max(0.5, min(30.0, float(duration_sec))),
        "params": params,
    }
