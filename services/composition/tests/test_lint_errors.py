from __future__ import annotations

from composition.author.lint_errors import classify_lint_error, enrich_lint_errors
from composition.author.normalize_acp_spec import is_smoke_empty_spec, normalize_acp_material_spec


def test_classify_sandbox_path() -> None:
    assert classify_lint_error("Path escapes project sandbox: generated/foo.mp4") == "sandbox_path"


def test_enrich_lint_errors_includes_fix_recipe() -> None:
    payload = enrich_lint_errors(["Path escapes project sandbox: x"])
    assert payload["hintCode"] == "sandbox_path"
    assert "basename" in payload["fixRecipe"]


def test_normalize_acp_spec_rewrites_generated_path(tmp_path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "slot-1-stock.mp4").write_bytes(b"v")
    spec = {
        "template": "composition",
        "durationSec": 5,
        "composition": {
            "bodyHtml": '<video src="D:/generated/slot-1-stock.mp4"></video>',
            "styles": "",
            "timelineScript": "tl.set({}, {}, 0);",
            "registryBlocks": [],
        },
    }
    normalized = normalize_acp_material_spec(spec, scratch)
    assert "slot-1-stock.mp4" in normalized["composition"]["bodyHtml"]
    assert "generated" not in normalized["composition"]["bodyHtml"]


def test_is_smoke_empty_spec_rejects_empty_benefit_card() -> None:
    assert is_smoke_empty_spec(
        {"template": "benefit-card", "durationSec": 6, "params": {"title": "", "bullets": []}}
    )
