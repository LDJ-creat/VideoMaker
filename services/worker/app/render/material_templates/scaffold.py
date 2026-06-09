"""Re-export composition build/scaffold for worker backward compatibility."""

from composition.build.composition_builder import build_composition, validate_spec_dict
from composition.build.legacy_scaffold import (
    MaterialScaffoldError,
    ensure_paths_in_project_sandbox,
    sanitize_params,
    sanitize_string,
    validate_material_spec,
)

__all__ = [
    "MaterialScaffoldError",
    "build_composition",
    "ensure_paths_in_project_sandbox",
    "sanitize_params",
    "sanitize_string",
    "validate_material_spec",
    "validate_spec_dict",
]
