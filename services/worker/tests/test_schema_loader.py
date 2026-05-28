from __future__ import annotations

import json
from pathlib import Path

from app.validation.schema_loader import SchemaLoader, validate_contract


def test_schema_loader_discovers_all_contract_schemas() -> None:
    loader = SchemaLoader()
    names = loader.available_schema_names()
    assert "video-structure" in names
    assert "asset-inventory" in names
    assert "gap-report" in names
    assert "generation-plan" in names
    assert "render-timeline" in names
    assert len(names) >= 8


def test_validate_contract_returns_structured_errors() -> None:
    payload = {"id": "x"}
    result = validate_contract("video-structure", payload)
    assert result.valid is False
    assert result.errors
    first = result.errors[0]
    assert first.path
    assert isinstance(first.message, str)
    assert isinstance(first.validator, str)


def test_every_schema_can_compile_and_validate_minimal_shape() -> None:
    loader = SchemaLoader()
    schemas_dir = loader.schemas_dir
    schema_files = list(schemas_dir.glob("*.schema.json"))
    assert schema_files

    for schema_file in schema_files:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        name = schema_file.name.replace(".schema.json", "")
        minimal = {}
        result = validate_contract(name, minimal)
        # empty payload is expected to fail for strict contracts,
        # but validation should execute without raising.
        assert result.valid in {True, False}
        assert isinstance(result.errors, list)

