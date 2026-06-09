from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from composition.paths import detect_repo_root


@dataclass(frozen=True)
class ValidationErrorItem:
    path: str
    message: str
    validator: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationErrorItem]


def _format_error_path(path_parts: list[Any]) -> str:
    if not path_parts:
        return "$"
    rendered = "$"
    for part in path_parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}"
    return rendered


class SchemaLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or detect_repo_root()
        self.schemas_dir = self.repo_root / "packages" / "contracts" / "schemas"
        self._schemas: dict[str, dict[str, Any]] | None = None
        self._registry: Registry | None = None

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

    def validate(self, name: str, payload: dict[str, Any]) -> ValidationResult:
        self._ensure_loaded()
        assert self._schemas is not None and self._registry is not None
        schema = self._schemas[name]
        validator = Draft202012Validator(schema, registry=self._registry)
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
        formatted = [
            ValidationErrorItem(
                path=_format_error_path(list(error.absolute_path)),
                message=error.message,
                validator=error.validator,
            )
            for error in errors
        ]
        return ValidationResult(valid=not formatted, errors=formatted)


_default_loader: SchemaLoader | None = None


def validate_contract(name: str, payload: dict[str, Any]) -> ValidationResult:
    global _default_loader
    if _default_loader is None:
        _default_loader = SchemaLoader()
    return _default_loader.validate(name, payload)
