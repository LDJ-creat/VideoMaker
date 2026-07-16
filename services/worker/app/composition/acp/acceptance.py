from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.pipelines.material_review import material_spec_content_hash
from app.pipelines.material_slot_revise import scan_forbidden_acp_scratch_files

_SESSION_MTIME_TOLERANCE_SEC = 1.0


def accept_acp_author_result(
    *,
    spec: dict[str, Any],
    scratch_dir: Path,
    author_started: float,
    author_payload: dict[str, Any],
    agent_diagnostics: dict[str, Any],
    partial_harvest: bool = False,
    session_lint_passed: bool = False,
) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    hint_codes: list[str] = []

    spec_path = scratch_dir / "material-spec.json"
    lint_marker = scratch_dir / "material-spec.lint-passed"

    if not lint_marker.is_file() and not session_lint_passed:
        errors.append("ACP session did not complete write_material_spec with lint pass")
        hint_codes.append("write_not_completed")

    if spec_path.is_file() and not session_lint_passed:
        try:
            if spec_path.stat().st_mtime < author_started - _SESSION_MTIME_TOLERANCE_SEC:
                errors.append("Harvested material-spec predates session start")
                hint_codes.append("stale_spec_harvest")
        except OSError:
            pass

    contract = author_payload.get("authorContract")
    must_change = isinstance(contract, dict) and contract.get("mustChangeSpec")
    gate = author_payload.get("materialGateRevise")
    is_gate_revise = isinstance(gate, dict) and gate.get("source") == "material_gate_revise"

    if is_gate_revise and must_change:
        existing_hash = str(author_payload.get("existingSpecHash") or "").strip()
        if existing_hash and material_spec_content_hash(spec) == existing_hash:
            errors.append("Regenerated spec hash unchanged from archived spec")
            hint_codes.append("regression_unchanged_spec")

    exit_code = agent_diagnostics.get("agentExitCode")
    if exit_code is not None and not session_lint_passed:
        try:
            code = int(exit_code)
        except (TypeError, ValueError):
            code = 1
        if code != 0 and not partial_harvest:
            errors.append(f"ACP agent exited abnormally (exitCode={code})")
            hint_codes.append("agent_abnormal_exit")

    if partial_harvest and is_gate_revise and must_change:
        errors.append("Gate revise does not allow silent partial harvest")
        hint_codes.append("partial_harvest_blocked")

    helper_block = os.getenv("VIDEOMAKER_ACP_HELPER_SCRIPT_BLOCK", "true").strip().lower()
    if helper_block not in {"0", "false", "no", "off"}:
        forbidden = scan_forbidden_acp_scratch_files(scratch_dir)
        if forbidden:
            errors.append(
                "Forbidden helper scripts in scratch: "
                + ", ".join(forbidden)
            )
            hint_codes.append("forbidden_helper_script")

    return (not errors, errors, hint_codes)
