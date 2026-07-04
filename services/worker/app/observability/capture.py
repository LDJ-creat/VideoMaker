from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


_SUMMARY_MAX_CHARS = 4096
_TEXT_PREVIEW_CHARS = 200
_SENSITIVE_BASE64_KEYS = frozenset({"imageBase64", "keyframeBase64", "image_base64"})
_PATH_KEYS = frozenset({"path", "referenceImagePath", "uri", "videoPath"})


def resolve_observability_capture() -> str:
    raw = os.getenv("VIDEOMAKER_OBSERVABILITY_CAPTURE", "full").strip().lower()
    if raw in {"full", "summary", "off"}:
        return raw
    return "full"


def resolve_langfuse_capture() -> str:
    raw = os.getenv("LANGFUSE_CAPTURE", "").strip().lower()
    if raw in {"full", "summary", "off"}:
        return raw
    return resolve_observability_capture()


def capture_enabled_for_local(capture: str) -> bool:
    return capture != "off"


def capture_enabled_for_langfuse(capture: str) -> bool:
    return capture != "off"


def prepare_payload(value: Any, *, capture: str) -> Any:
    if capture == "off":
        return None
    sanitized = _sanitize_value(value)
    if capture == "summary":
        return _summarize_value(sanitized)
    return sanitized


def _summarize_value(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= _SUMMARY_MAX_CHARS:
            return value
        return value[:_SUMMARY_MAX_CHARS] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_summarize_value(item) for item in value[:20]]
    if isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False)
        if len(text) <= _SUMMARY_MAX_CHARS:
            return value
        return {"summary": text[:_SUMMARY_MAX_CHARS] + "…"}
    text = str(value)
    if len(text) <= _SUMMARY_MAX_CHARS:
        return text
    return text[:_SUMMARY_MAX_CHARS] + "…"


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return _sanitize_dict(value)
    if isinstance(value, str) and value.startswith("data:") and ";base64," in value:
        return _sanitize_data_url(value)
    return value


def _sanitize_dict(value: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "text" and isinstance(item, str):
            sanitized[key] = _sanitize_text_field(item)
        elif key in _PATH_KEYS and isinstance(item, str):
            sanitized[key] = _sanitize_path_field(item)
        elif key in _SENSITIVE_BASE64_KEYS and isinstance(item, str):
            sanitized[key] = _sanitize_inline_base64(item)
        else:
            sanitized[key] = _sanitize_value(item)
    return sanitized


def _sanitize_text_field(text: str) -> dict[str, Any] | str:
    if len(text) <= _TEXT_PREVIEW_CHARS:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return {
        "type": "text_ref",
        "charCount": len(text),
        "sha256Prefix": digest,
        "preview": text[:_TEXT_PREVIEW_CHARS],
    }


def _sanitize_path_field(path_value: str) -> dict[str, Any]:
    digest = hashlib.sha256(path_value.encode("utf-8")).hexdigest()[:16]
    return {
        "type": "path_ref",
        "basename": Path(path_value).name,
        "sha256Prefix": digest,
    }


def _sanitize_inline_base64(encoded: str) -> dict[str, Any]:
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return {
        "type": "base64_ref",
        "sha256Prefix": digest,
        "base64Chars": len(encoded),
    }


def _sanitize_data_url(value: str) -> dict[str, Any]:
    header, _, encoded = value.partition(",")
    mime = "application/octet-stream"
    if header.startswith("data:"):
        mime = header[5:].split(";", 1)[0] or mime
    raw = encoded.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return {
        "type": "data_url_ref",
        "mime": mime,
        "sha256Prefix": digest,
        "base64Chars": len(encoded),
    }


def sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_sanitize_message(message) for message in messages]


def _sanitize_message(message: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(message)
    content = sanitized.get("content")
    if isinstance(content, list):
        sanitized["content"] = [_sanitize_content_part(part) for part in content]
    return sanitized


def _sanitize_content_part(part: Any) -> Any:
    if not isinstance(part, dict):
        return part
    cloned = dict(part)
    for key in ("image_url", "video_url"):
        nested = cloned.get(key)
        if not isinstance(nested, dict):
            continue
        url = nested.get("url")
        if isinstance(url, str) and ";base64," in url:
            cloned[key] = {"url": _sanitize_data_url(url)}
    return cloned
