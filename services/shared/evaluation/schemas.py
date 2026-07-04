from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class EvaluationSchemaLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        current = Path(__file__).resolve()
        self.repo_root = repo_root or current.parents[3]
        self.schemas_dir = self.repo_root / "packages" / "contracts" / "schemas"
        self._registry: Registry | None = None
        self._schemas: dict[str, dict[str, Any]] | None = None

    def _ensure_loaded(self) -> None:
        if self._schemas is not None:
            return
        schemas: dict[str, dict[str, Any]] = {}
        registry = Registry()
        for schema_path in sorted(self.schemas_dir.glob("*.schema.json")):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            key = schema_path.name.replace(".schema.json", "")
            schemas[key] = schema
            schema_id = schema.get("$id")
            if isinstance(schema_id, str):
                registry = registry.with_resource(schema_id, Resource.from_contents(schema))
        self._schemas = schemas
        self._registry = registry

    def validate(self, name: str, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        self._ensure_loaded()
        assert self._schemas is not None and self._registry is not None
        schema = self._schemas.get(name)
        if schema is None:
            return False, [f"unknown schema: {name}"]
        validator = Draft202012Validator(schema, registry=self._registry)
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
        messages = [error.message for error in errors]
        return not messages, messages


_LOADER = EvaluationSchemaLoader()


def validate_evaluation_report(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    return _LOADER.validate("evaluation-report", payload)
