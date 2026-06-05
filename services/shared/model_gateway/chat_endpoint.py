from __future__ import annotations

_CHAT_COMPLETIONS_SUFFIX = "/chat/completions"


def resolve_chat_completions_url(base_url: str) -> str:
    """Resolve OpenAI-compatible chat completions URL from a provider base URL.

    Accepts either a directory-style base (``https://api.openai.com/v1``) or a
    full endpoint URL already ending with ``/chat/completions`` (common for
    Volcengine Ark and similar gateways).
    """
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return _CHAT_COMPLETIONS_SUFFIX.lstrip("/")
    lower = normalized.lower()
    if lower.endswith(_CHAT_COMPLETIONS_SUFFIX):
        return normalized
    return f"{normalized}{_CHAT_COMPLETIONS_SUFFIX}"
