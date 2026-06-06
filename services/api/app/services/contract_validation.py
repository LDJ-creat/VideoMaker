from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@dataclass(frozen=True)
class ValidationErrorItem:
    path: str
    message: str
    validator: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationErrorItem]


class ContractValidator:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[4]
        self.schemas_dir = self.repo_root / "packages" / "contracts" / "schemas"
        self._registry: Registry | None = None
        self._schemas: dict[str, dict[str, Any]] | None = None

    def _ensure_loaded(self) -> None:
        if self._registry is not None:
            return
        schemas: dict[str, dict[str, Any]] = {}
        resources: list[tuple[str, Resource]] = []
        for path in sorted(self.schemas_dir.glob("*.schema.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            schema_id = str(payload.get("$id") or path.name)
            schemas[path.stem.replace(".schema", "")] = payload
            resources.append((schema_id, Resource.from_contents(payload)))
        self._schemas = schemas
        self._registry = Registry().with_resources(resources)

    def validate(self, schema_name: str, payload: dict[str, Any]) -> ValidationResult:
        self._ensure_loaded()
        assert self._schemas is not None and self._registry is not None
        schema = self._schemas.get(schema_name)
        if schema is None:
            return ValidationResult(valid=False, errors=[ValidationErrorItem("", f"Unknown schema {schema_name}", "schema")])
        validator = Draft202012Validator(schema, registry=self._registry)
        errors: list[ValidationErrorItem] = []
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
            path = ".".join(str(part) for part in error.path) or "(root)"
            errors.append(
                ValidationErrorItem(
                    path=path,
                    message=error.message,
                    validator=str(error.validator),
                )
            )
        return ValidationResult(valid=not errors, errors=errors)


_default_validator: ContractValidator | None = None


def validate_script_draft(draft: dict[str, Any]) -> ValidationResult:
    global _default_validator
    if _default_validator is None:
        _default_validator = ContractValidator()
    return _default_validator.validate("script-draft", draft)
