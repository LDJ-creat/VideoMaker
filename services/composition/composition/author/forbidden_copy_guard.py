from __future__ import annotations

import re
from html import unescape
from typing import Any

_MIN_FORBIDDEN_LEN = 6

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def normalize_author_slot(slot: dict[str, Any]) -> dict[str, Any]:
    creative = slot.get("creativeDirection")
    if isinstance(creative, dict):
        normalized = {
            "role": slot.get("role"),
            "creativeDirection": {
                "scriptGoal": str(creative.get("scriptGoal") or ""),
                "visualGoal": str(creative.get("visualGoal") or ""),
            },
            "doNotRenderVerbatim": True,
        }
    else:
        normalized = {
            "role": slot.get("role"),
            "creativeDirection": {
                "scriptGoal": str(slot.get("scriptIntent") or ""),
                "visualGoal": str(slot.get("visualIntent") or ""),
            },
            "doNotRenderVerbatim": True,
        }
    if slot.get("importance") is not None:
        normalized["importance"] = slot.get("importance")
    required = slot.get("requiredAssetType")
    if isinstance(required, list) and required:
        normalized["requiredAssetType"] = list(required)
    return normalized


FIELD_SEMANTICS: dict[str, str] = {
    "slot.creativeDirection": "Creative brief for layout/motion — never render verbatim on screen.",
    "finishBrief.creativeBrief": "Implementation spec — guides polish tasks, not visible copy.",
    "finishBrief.finishIntent": "Polish task description — implement as motion/UI, not as text nodes.",
    "finishBrief.voiceoverContext.line": "VO timing/emotion reference only — subtitles burn via timeline track.",
    "renderPolicy.allowedDisplayCopy": "Only these strings may appear as readable on-screen copy.",
}


def _append_phrase(phrases: list[str], seen: set[str], raw: str) -> None:
    text = str(raw or "").strip()
    if len(text) < _MIN_FORBIDDEN_LEN or text in seen:
        return
    seen.add(text)
    phrases.append(text)


def collect_forbidden_copy_phrases(payload: dict[str, Any]) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()

    slot = payload.get("slot")
    if isinstance(slot, dict):
        creative = slot.get("creativeDirection")
        if isinstance(creative, dict):
            _append_phrase(phrases, seen, str(creative.get("scriptGoal") or ""))
            _append_phrase(phrases, seen, str(creative.get("visualGoal") or ""))
        _append_phrase(phrases, seen, str(slot.get("scriptIntent") or ""))
        _append_phrase(phrases, seen, str(slot.get("visualIntent") or ""))

    finish = payload.get("finishBrief")
    if isinstance(finish, dict):
        _append_phrase(phrases, seen, str(finish.get("finishIntent") or ""))
        _append_phrase(phrases, seen, str(finish.get("packagingHint") or ""))
        creative_brief = finish.get("creativeBrief")
        if isinstance(creative_brief, dict):
            _append_phrase(phrases, seen, str(creative_brief.get("visualDirection") or ""))
            _append_phrase(phrases, seen, str(creative_brief.get("narrativeGoal") or ""))
        voiceover = finish.get("voiceoverContext")
        if isinstance(voiceover, dict):
            _append_phrase(phrases, seen, str(voiceover.get("line") or ""))
        scene = finish.get("storyboardScene")
        if isinstance(scene, dict):
            _append_phrase(phrases, seen, str(scene.get("visual") or ""))
            _append_phrase(phrases, seen, str(scene.get("script") or ""))
        for req in finish.get("packagingRequirements") or []:
            _append_phrase(phrases, seen, str(req or ""))

    return phrases


def _allowed_display_copy(payload: dict[str, Any]) -> list[str]:
    render_policy = payload.get("renderPolicy")
    if isinstance(render_policy, dict):
        allowed = render_policy.get("allowedDisplayCopy")
        if isinstance(allowed, list):
            return [str(item).strip() for item in allowed if str(item).strip()]
    finish = payload.get("finishBrief")
    if isinstance(finish, dict):
        nested = finish.get("renderPolicy")
        if isinstance(nested, dict):
            allowed = nested.get("allowedDisplayCopy")
            if isinstance(allowed, list):
                return [str(item).strip() for item in allowed if str(item).strip()]
    return []


def _strip_html_text(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw)
    return _WS_RE.sub(" ", unescape(text)).strip()


def extract_spec_visible_text(spec: dict[str, Any]) -> str:
    chunks: list[str] = []
    composition = spec.get("composition")
    if isinstance(composition, dict):
        body_html = str(composition.get("bodyHtml") or "")
        if body_html:
            chunks.append(_strip_html_text(body_html))
    params = spec.get("params")
    if isinstance(params, dict):
        title = str(params.get("title") or "").strip()
        if title:
            chunks.append(title)
        subtitle = str(params.get("subtitle") or "").strip()
        if subtitle:
            chunks.append(subtitle)
        bullets = params.get("bullets")
        if isinstance(bullets, list):
            chunks.extend(str(item).strip() for item in bullets if str(item).strip())
    return "\n".join(chunks)


def check_forbidden_copy_in_spec(
    spec: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    rendered = extract_spec_visible_text(spec)
    if not rendered.strip():
        return []

    allowed = _allowed_display_copy(payload)
    allowed_set = set(allowed)
    errors: list[str] = []

    for phrase in collect_forbidden_copy_phrases(payload):
        if phrase in allowed_set:
            continue
        if phrase in rendered:
            errors.append(
                f"Forbidden brief or voiceover copy rendered verbatim: {phrase[:80]}"
            )

    if not allowed:
        cjk_runs = re.findall(r"[\u4e00-\u9fff]{4,}", rendered)
        if len(cjk_runs) >= 3:
            errors.append(
                "Readable Chinese copy detected without renderPolicy.allowedDisplayCopy — "
                "prefer text-free packaging overlays."
            )

    return errors
