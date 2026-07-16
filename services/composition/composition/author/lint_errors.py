from __future__ import annotations

from typing import Any


def classify_lint_error(message: str) -> str:
    lowered = message.lower()
    if "empty_allowlist" in lowered or (
        "without renderpolicy.alloweddisplaycopy" in lowered
        and "empty" in lowered
    ):
        return "forbidden_copy_empty_allowlist"
    if "escapes project sandbox" in lowered or "path_escape" in lowered or "escapes asset sandbox" in lowered:
        return "sandbox_path"
    if "forbidden" in lowered and "copy" in lowered:
        return "forbidden_copy"
    if "not in renderpolicy.alloweddisplaycopy" in lowered:
        return "forbidden_copy"
    if "gsap_from_opacity_noop" in lowered or ("opacity" in lowered and "gsap.from" in lowered):
        return "gsap_opacity_noop"
    if "spec_json must be" in lowered:
        return "schema_invalid"
    if "html" in lowered or "composition.bodyhtml" in lowered or "safety" in lowered:
        return "html_safety"
    if "standalone composition" in lowered or "autoalpha:1 hold" in lowered or 'id="root"' in lowered:
        return "standalone_canvas"
    if "schema" in lowered or "invalid materialspec" in lowered:
        return "schema_invalid"
    if "lint failed" in lowered or "hyperframes" in lowered or "✗" in message or "error(s)" in lowered:
        return "hf_lint_failed"
    if "missing material" in lowered or "material-spec" in lowered:
        return "missing_spec"
    return "unknown"


def fix_recipe_for_hint(hint_code: str) -> str:
    recipes = {
        "sandbox_path": (
            "assetRefs.uri and video src must be basename only (e.g. slot-1-stock.mp4) "
            "under scratch; never use generated/ or absolute paths"
        ),
        "schema_invalid": "Run lint-spec --schema-only on scratch, fix JSON schema errors, then full lint",
        "hf_lint_failed": "Read lint-log.json in lint-draft, fix HTML/GSAP/video tags, re-run composition_lint_draft",
        "forbidden_copy": (
            "Paste exact strings from allowedDisplayCopy into bodyHtml (no truncation/rewrite); "
            "highlight keywords with spans inside a full allowlisted sentence"
        ),
        "forbidden_copy_empty_allowlist": (
            "Use authorContract.allowedDisplayCopy strings for on-screen copy; "
            "do NOT read repository source — update spec HTML with allowed phrases only"
        ),
        "gsap_opacity_noop": (
            "Do not set CSS opacity:0 on elements that also use gsap.from({opacity:0}); "
            "leave CSS at opacity:1 (default) and let gsap.from hide→show"
        ),
        "lint_timeout": "Retry composition_lint_draft once; do not read repo source",
        "html_safety": "Fix composition fragment: no script injection, valid GSAP timeline using shell tl",
        "standalone_canvas": (
            "Do NOT put id=\"root\" in bodyHtml (shell already provides #root); use child ids like "
            "#card / #quote-line; end with tl.set hold when content starts hidden"
        ),
        "missing_spec": "Call write_material_spec once with a valid MaterialSpec JSON object",
        "unknown": "Fix validation errors, run composition_lint_draft, then write_material_spec",
    }
    return recipes.get(hint_code, recipes["unknown"])


def primary_hint_code(errors: list[str]) -> str:
    if not errors:
        return ""
    return classify_lint_error(errors[0])


def error_category_counts(errors: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for message in errors:
        code = classify_lint_error(message)
        counts[code] = counts.get(code, 0) + 1
    return counts


def enrich_lint_errors(
    errors: list[str],
    *,
    author_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hint = primary_hint_code(errors)
    payload: dict[str, Any] = {
        "errors": errors,
        "hintCode": hint,
        "fixRecipe": fix_recipe_for_hint(hint),
        "errorCategories": error_category_counts(errors),
    }
    if author_payload and hint in {"forbidden_copy", "forbidden_copy_empty_allowlist"}:
        from composition.author.forbidden_copy_guard import allowed_display_copy_list

        merged = allowed_display_copy_list(author_payload)
        if merged:
            payload["suggestedAllowedDisplayCopy"] = merged
    return payload
