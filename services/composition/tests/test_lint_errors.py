from __future__ import annotations

from composition.author.lint_errors import classify_lint_error, enrich_lint_errors
from composition.author.normalize_acp_spec import is_smoke_empty_spec, normalize_acp_material_spec


def test_classify_sandbox_path() -> None:
    assert classify_lint_error("Path escapes project sandbox: generated/foo.mp4") == "sandbox_path"


def test_classify_gsap_opacity_noop() -> None:
    msg = (
        "✗ gsap_from_opacity_noop: \".top-line\" has CSS `opacity: 0` and a gsap.from() "
        "that also sets opacity to 0."
    )
    assert classify_lint_error(msg) == "gsap_opacity_noop"


def test_enrich_lint_errors_includes_fix_recipe() -> None:
    payload = enrich_lint_errors(["Path escapes project sandbox: x"])
    assert payload["hintCode"] == "sandbox_path"
    assert "basename" in payload["fixRecipe"]
    assert payload["errorCategories"]["sandbox_path"] == 1


def test_enrich_includes_merged_allowed_display_copy() -> None:
    payload = enrich_lint_errors(
        ["Display copy not in renderPolicy.allowedDisplayCopy: 随便写的"],
        author_payload={
            "compositionAuthorBrief": {"displayCopyPolicy": {"allowed": ["试错"]}},
            "renderPolicy": {"allowedDisplayCopy": ["完整金句"]},
        },
    )
    assert payload["hintCode"] == "forbidden_copy"
    assert "试错" in payload["suggestedAllowedDisplayCopy"]
    assert "完整金句" in payload["suggestedAllowedDisplayCopy"]


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
