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
    if "html" in lowered or "composition.bodyhtml" in lowered or "safety" in lowered:
        return "html_safety"
    if "standalone composition" in lowered or "autoalpha:1 hold" in lowered or 'id="root"' in lowered:
        return "standalone_canvas"
    if "schema" in lowered or "invalid materialspec" in lowered:
        return "schema_invalid"
    if "lint failed" in lowered or "hyperframes" in lowered:
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
        "forbidden_copy": "Only use strings from renderPolicy.allowedDisplayCopy; never render voiceover verbatim",
        "forbidden_copy_empty_allowlist": (
            "Use authorContract.allowedDisplayCopy strings for on-screen copy; "
            "do NOT read repository source — update spec HTML with allowed phrases only"
        ),
        "lint_timeout": "Retry composition_lint_draft once; do not read repo source",
        "html_safety": "Fix composition fragment: no script injection, valid GSAP timeline using shell tl",
        "standalone_canvas": (
            "Use opaque --vm-bg on #root, avoid id=\"root\" in bodyHtml, and end timeline with "
            "tl.set(..., { autoAlpha: 1 }) when content starts hidden"
        ),
        "missing_spec": "Call write_material_spec once with a valid MaterialSpec JSON object",
        "unknown": "Fix validation errors, run composition_lint_draft, then write_material_spec",
    }
    return recipes.get(hint_code, recipes["unknown"])


def primary_hint_code(errors: list[str]) -> str:
    if not errors:
        return ""
    return classify_lint_error(errors[0])


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
    }
    if author_payload and hint in {"forbidden_copy", "forbidden_copy_empty_allowlist"}:
        contract = author_payload.get("authorContract")
        if isinstance(contract, dict):
            allowed = contract.get("allowedDisplayCopy")
            if isinstance(allowed, list) and allowed:
                payload["suggestedAllowedDisplayCopy"] = allowed
        render_policy = author_payload.get("renderPolicy")
        if isinstance(render_policy, dict):
            allowed = render_policy.get("allowedDisplayCopy")
            if isinstance(allowed, list) and allowed:
                payload.setdefault(
                    "suggestedAllowedDisplayCopy",
                    [str(item) for item in allowed if str(item).strip()],
                )
    return payload
