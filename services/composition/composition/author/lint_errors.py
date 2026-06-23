from __future__ import annotations

from typing import Any


def classify_lint_error(message: str) -> str:
    lowered = message.lower()
    if "escapes project sandbox" in lowered or "path_escape" in lowered or "escapes asset sandbox" in lowered:
        return "sandbox_path"
    if "forbidden" in lowered and "copy" in lowered:
        return "forbidden_copy"
    if "html" in lowered or "composition.bodyhtml" in lowered or "safety" in lowered:
        return "html_safety"
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
        "html_safety": "Fix composition fragment: no script injection, valid GSAP timeline using shell tl",
        "missing_spec": "Call write_material_spec once with a valid MaterialSpec JSON object",
        "unknown": "Fix validation errors, run composition_lint_draft, then write_material_spec",
    }
    return recipes.get(hint_code, recipes["unknown"])


def primary_hint_code(errors: list[str]) -> str:
    if not errors:
        return ""
    return classify_lint_error(errors[0])


def enrich_lint_errors(errors: list[str]) -> dict[str, Any]:
    hint = primary_hint_code(errors)
    return {
        "errors": errors,
        "hintCode": hint,
        "fixRecipe": fix_recipe_for_hint(hint),
    }
