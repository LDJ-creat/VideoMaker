from __future__ import annotations

from app.gateway.model_gateway import ModelGateway
from app.validation.prompt_schema import format_schema_prompt_appendix
from app.validation.schema_loader import _LOADER


def test_format_revise_planner_appendix_lists_enums() -> None:
    schema = _LOADER.get_schema("revise-planner-output")
    appendix = format_schema_prompt_appendix("revise-planner-output", schema)
    assert "Contract appendix: RevisePlannerOutput" in appendix
    assert "reduce_subtitles" in appendix
    assert "subtitle_patch" in appendix
    assert "executionMode" in appendix


def test_model_gateway_appends_schema_appendix() -> None:
    appendix = ModelGateway._schema_prompt_appendix("edit-intent")
    assert "Contract appendix: EditIntent" in appendix
    assert "adjust_hook" in appendix
    assert "executionTool" in appendix
