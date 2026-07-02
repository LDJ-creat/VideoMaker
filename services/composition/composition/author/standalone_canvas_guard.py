from __future__ import annotations

import re
from typing import Any

_HF_NATIVE = "hf_native"
_OVERLAY_MODE = "source_then_polish"

_VM_BG_TRANSPARENT = re.compile(r"--vm-bg\s*:\s*transparent\b", re.I)
_ROOT_BG_TRANSPARENT = re.compile(
    r"#root\s*\{[^}]*background\s*:\s*transparent\b",
    re.I | re.S,
)
_BODY_ROOT_ID = re.compile(r"""id\s*=\s*['"]root['"]""", re.I)
_HIDDEN_CONTENT_RULE = re.compile(
    r"\.(?:phrase|word|vm-word|vm-line|vm-hero|stage|card|bridge)[^{]*\{[^}]*"
    r"(?:visibility\s*:\s*hidden|opacity\s*:\s*0)",
    re.I | re.S,
)
_CONTENT_AUTO_ALPHA_HOLD = re.compile(
    r"tl\.(?:set|to)\(\s*['\"][^'\"]*"
    r"(?:phrase|word|vm-word|vm-line|vm-hero|stage|card|bridge|mark|vm-hero|line)"
    r"[^'\"]*['\"][^)]*autoAlpha\s*:\s*1",
    re.I | re.S,
)


def _finish_brief(payload: dict[str, Any]) -> dict[str, Any] | None:
    finish = payload.get("finishBrief")
    return finish if isinstance(finish, dict) else None


def _composition_author_brief(payload: dict[str, Any]) -> dict[str, Any] | None:
    direct = payload.get("compositionAuthorBrief")
    if isinstance(direct, dict):
        return direct
    finish = _finish_brief(payload)
    if finish is None:
        return None
    nested = finish.get("compositionAuthorBrief")
    return nested if isinstance(nested, dict) else None


def is_hf_native_standalone(author_payload: dict[str, Any]) -> bool:
    """True when the slot renders a full-screen HF clip (not a polish overlay)."""
    finish = _finish_brief(author_payload)
    if isinstance(finish, dict):
        mode = str(finish.get("completionMode") or "").strip().lower()
        if mode == _OVERLAY_MODE:
            return False
        if mode == _HF_NATIVE:
            return True

    cab = _composition_author_brief(author_payload)
    if isinstance(cab, dict) and str(cab.get("mode") or "").strip().lower() == _HF_NATIVE:
        return True

    slot = author_payload.get("slot")
    if isinstance(slot, dict) and str(slot.get("completionMode") or "").strip().lower() == _HF_NATIVE:
        return True
    return False


def check_hf_native_standalone_composition(
    spec: dict[str, Any],
    author_payload: dict[str, Any],
) -> list[str]:
    if str(spec.get("template") or "") != "composition":
        return []
    if not is_hf_native_standalone(author_payload):
        return []

    composition = spec.get("composition")
    if not isinstance(composition, dict):
        return []

    errors: list[str] = []
    body_html = str(composition.get("bodyHtml") or "")
    styles = str(composition.get("styles") or "")
    timeline_script = str(composition.get("timelineScript") or "")

    if _BODY_ROOT_ID.search(body_html):
        errors.append(
            'composition.bodyHtml must not declare id="root"; HyperFrames shell already provides #root'
        )

    if _VM_BG_TRANSPARENT.search(styles) or _ROOT_BG_TRANSPARENT.search(styles):
        errors.append(
            "hf_native standalone composition requires opaque --vm-bg / #root background "
            "(transparent renders as black in slot preview MP4)"
        )

    if not re.search(r"--vm-bg\s*:\s*[^;}\s]", styles, re.I):
        errors.append(
            "hf_native standalone composition must declare opaque :root { --vm-bg: ... } "
            "using var(--vm-bg) on #root"
        )

    if _HIDDEN_CONTENT_RULE.search(styles) and not _CONTENT_AUTO_ALPHA_HOLD.search(timeline_script):
        errors.append(
            "composition hides primary content (opacity:0 / visibility:hidden) but timelineScript "
            "never sets autoAlpha:1 on content selectors; HyperFrames may capture all-black frames"
        )

    return errors
