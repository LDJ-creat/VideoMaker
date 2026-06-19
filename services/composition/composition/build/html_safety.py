from __future__ import annotations

import re

FORBIDDEN_BODY_PATTERNS = (
    re.compile(r"<\s*!doctype\b", re.I),
    re.compile(r"<\s*html\b", re.I),
    re.compile(r"<\s*head\b", re.I),
    re.compile(r"<\s*body\b", re.I),
    re.compile(r"<\s*script\b", re.I),
    re.compile(r"<\s*iframe\b", re.I),
    re.compile(r"<\s*object\b", re.I),
    re.compile(r"<\s*link\b", re.I),
    re.compile(r"javascript:", re.I),
    re.compile(r"\bon[a-z]+\s*=", re.I),
)

FORBIDDEN_SCRIPT_PATTERNS = (
    re.compile(r"\beval\s*\(", re.I),
    re.compile(r"\bFunction\s*\(", re.I),
    re.compile(r"\bfetch\s*\(", re.I),
    re.compile(r"\bimport\s*\(", re.I),
    re.compile(r"\bdocument\.write\b", re.I),
)

MAX_BODY_LEN = 32_000
MAX_STYLES_LEN = 16_000
MAX_TIMELINE_SCRIPT_LEN = 8_000


class HtmlSafetyError(ValueError):
    pass


def _check_patterns(text: str, patterns: tuple[re.Pattern[str], ...], label: str) -> None:
    for pattern in patterns:
        if pattern.search(text):
            raise HtmlSafetyError(f"{label} contains forbidden pattern: {pattern.pattern}")


def validate_composition_fragment(
    *,
    body_html: str,
    styles: str = "",
    timeline_script: str = "",
) -> None:
    if len(body_html) > MAX_BODY_LEN:
        raise HtmlSafetyError("bodyHtml exceeds max length")
    if len(styles) > MAX_STYLES_LEN:
        raise HtmlSafetyError("styles exceeds max length")
    if len(timeline_script) > MAX_TIMELINE_SCRIPT_LEN:
        raise HtmlSafetyError("timelineScript exceeds max length")
    _check_patterns(body_html, FORBIDDEN_BODY_PATTERNS, "bodyHtml")
    if styles:
        _check_patterns(styles, FORBIDDEN_BODY_PATTERNS, "styles")
    if timeline_script:
        _check_patterns(timeline_script, FORBIDDEN_SCRIPT_PATTERNS, "timelineScript")
