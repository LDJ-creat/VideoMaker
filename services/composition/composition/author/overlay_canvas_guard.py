from __future__ import annotations

import re
from typing import Any

from composition.author.standalone_canvas_guard import is_hf_native_standalone

_OVERLAY_MODE = "source_then_polish"
_BASE_VIDEO_TAG = re.compile(r"""<video\b[^>]*\bid\s*=\s*['"]base-video['"]""", re.I)
_OPAQUE_BLACK_BG = re.compile(
    r"background\s*:\s*(?:#000\b|#000000\b|black\b)",
    re.I,
)


def _finish_brief(payload: dict[str, Any]) -> dict[str, Any] | None:
    finish = payload.get("finishBrief")
    return finish if isinstance(finish, dict) else None


def is_source_then_polish_overlay(author_payload: dict[str, Any]) -> bool:
    finish = _finish_brief(author_payload)
    if isinstance(finish, dict):
        mode = str(finish.get("completionMode") or "").strip().lower()
        if mode == _OVERLAY_MODE:
            return True
    cab = author_payload.get("compositionAuthorBrief")
    if isinstance(cab, dict) and str(cab.get("mode") or "").strip().lower() == _OVERLAY_MODE:
        return True
    return False


def check_source_then_polish_overlay_composition(
    spec: dict[str, Any],
    author_payload: dict[str, Any],
) -> list[str]:
    if str(spec.get("template") or "") != "composition":
        return []
    if not is_source_then_polish_overlay(author_payload):
        return []
    composition = spec.get("composition")
    if not isinstance(composition, dict):
        return []

    body_html = str(composition.get("bodyHtml") or "")
    styles = str(composition.get("styles") or "")
    errors: list[str] = []

    if not _BASE_VIDEO_TAG.search(body_html):
        errors.append(
            "source_then_polish composition must include <video id=\"base-video\"> as the bottom layer"
        )

    if _OPAQUE_BLACK_BG.search(styles):
        errors.append(
            "source_then_polish overlay must not use fullscreen opaque black scrim covering base-video; "
            "use partial scrim or lower-third overlay only"
        )

    return errors


def check_hf_native_no_external_base_video(
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
    body_html = str(composition.get("bodyHtml") or "")
    if not _BASE_VIDEO_TAG.search(body_html):
        return []
    if re.search(r"""<video\b[^>]*\bsrc\s*=\s*['"][^'"]+\.(?:mp4|webm|mov)""", body_html, re.I):
        return [
            "hf_native standalone composition must not reference external base <video> MP4; "
            "use opaque full-screen HF canvas (--vm-bg) instead of source_then_polish overlay"
        ]
    return []
