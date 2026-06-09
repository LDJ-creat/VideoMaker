from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from composition.build.composition_builder import build_composition
from composition.patterns.deposit import PromoteRejected, composition_draft_dir
from composition.patterns.lint_verify import lint_log_confirms_pass
from composition.patterns.sanitize import load_generation_plan_context, sanitize_instance_spec
from composition.paths import detect_repo_root
from composition.schema_loader import validate_contract

PatternAuthorFn = Callable[..., dict[str, Any]]


@dataclass
class PromotePrepareContext:
    storage_root: Path
    project_id: str
    generation_id: str
    slot_id: str
    slot_role: str = ""
    storyboard_summary: str = ""
    master_narration: str = ""
    scene: dict[str, Any] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)


def _compose_skill_markdown(frontmatter: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if value is None:
            continue
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
            lines.append(f"{key}: [{rendered}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(body.strip())
    return "\n".join(lines) + "\n"


def _validate_material_spec(spec: dict[str, Any]) -> list[str]:
    result = validate_contract("material-spec", spec)
    return [f"{item.path}: {item.message}" for item in result.errors]


def _write_prepared_bundle(
    prepared_dir: Path,
    *,
    instance_spec: dict[str, Any],
    generalized_spec: dict[str, Any],
    skill_output: dict[str, Any],
    generation_id: str,
    slot_id: str,
    slot_role: str,
    provenance: dict[str, Any],
    lint_log_path: Path,
    draft_dir: Path,
) -> None:
    if prepared_dir.exists():
        shutil.rmtree(prepared_dir)
    prepared_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = dict(skill_output.get("frontmatter") or {})
    frontmatter.setdefault("entryKind", "composition_pattern")
    frontmatter.setdefault("title", f"Composition pattern for {slot_role}")
    frontmatter.setdefault("category", "composition")
    frontmatter.setdefault("slotRoles", [slot_role])
    frontmatter.setdefault("summary", f"Reusable motion pattern for {slot_role}")
    frontmatter.setdefault("motionPattern", frontmatter.get("motionPattern") or "custom")
    frontmatter["lintPassed"] = "true"
    frontmatter["sourceGenerationId"] = generation_id
    frontmatter["sourceSlotId"] = slot_id
    frontmatter["generalizationStatus"] = "llm_generalized"

    skill_md = _compose_skill_markdown(frontmatter, str(skill_output.get("markdown") or ""))
    (prepared_dir / "composition-skill.md").write_text(skill_md, encoding="utf-8")
    (prepared_dir / "spec.template.json").write_text(
        json.dumps(generalized_spec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (prepared_dir / "spec.instance.json").write_text(
        json.dumps(instance_spec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    references_md = "- [MaterialSpec template](./spec.template.json)\n- [Instance snapshot](./spec.instance.json)"
    refs_dest = prepared_dir / "references"
    if refs_dest.is_dir():
        for ref_file in sorted(refs_dest.iterdir()):
            if ref_file.is_file():
                references_md += f"\n- [{ref_file.name}](./references/{ref_file.name})"

    meta = {
        "entryKind": "composition_pattern",
        "title": frontmatter.get("title"),
        "category": frontmatter.get("category"),
        "summary": frontmatter.get("summary"),
        "slotRoles": frontmatter.get("slotRoles"),
        "motionPattern": frontmatter.get("motionPattern"),
        "lintPassed": True,
        "generalizationStatus": "llm_generalized",
        "sourceGenerationId": generation_id,
        "sourceSlotId": slot_id,
    }
    (prepared_dir / "entry-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    updated_provenance = dict(provenance)
    updated_provenance["generalizationStatus"] = "llm_generalized"
    updated_provenance["preparedLintLogPath"] = "lint-log.json"
    (prepared_dir / "provenance.json").write_text(
        json.dumps(updated_provenance, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    shutil.copy2(lint_log_path, prepared_dir / "lint-log.json")
    refs_src = draft_dir / "references"
    if refs_src.is_dir():
        refs_dest = prepared_dir / "references"
        if refs_dest.exists():
            shutil.rmtree(refs_dest)
        shutil.copytree(refs_src, refs_dest)


def _lint_generalized_spec(
    spec: dict[str, Any],
    *,
    scratch_root: Path,
    hyperframes_cli,
    repo_root: Path,
) -> tuple[bool, Path, list[str]]:
    composition_dir = scratch_root / "composition"
    if composition_dir.exists():
        shutil.rmtree(composition_dir)
    build_composition(spec, composition_dir, project_root=repo_root)
    lint_log = scratch_root / "lint-log.json"
    lint_result = hyperframes_cli.lint(composition_dir, lint_log)
    errors = [str(item) for item in lint_result.get("errors", [])]
    if not lint_result.get("ok"):
        message = lint_result.get("stderr") or lint_result.get("stdout") or "lint failed"
        if message and message not in errors:
            errors.append(str(message))
    return bool(lint_result.get("ok")), lint_log, errors


def prepare_promoted_pattern_bundle(
    ctx: PromotePrepareContext,
    *,
    author_fn: PatternAuthorFn,
    hyperframes_cli,
    repo_root: Path | None = None,
) -> Path:
    draft_dir = composition_draft_dir(
        ctx.storage_root,
        project_id=ctx.project_id,
        generation_id=ctx.generation_id,
        slot_id=ctx.slot_id,
    )
    if not draft_dir.is_dir():
        raise PromoteRejected("draft_not_found")

    lint_log = draft_dir / "lint-log.json"
    if not lint_log_confirms_pass(lint_log):
        raise PromoteRejected("lint_not_passed")

    provenance_path = draft_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
    if not provenance.get("lintPassed"):
        raise PromoteRejected("lint_not_passed")

    # Draft deposit stores the render instance spec under this filename until promote
    # copies it to spec.instance.json and replaces spec.template.json with generalized output.
    instance_path = draft_dir / "spec.template.json"
    if not instance_path.is_file():
        raise PromoteRejected("draft_not_found")
    instance_spec = json.loads(instance_path.read_text(encoding="utf-8"))

    if not ctx.scene and not ctx.storyboard_summary:
        try:
            loaded = load_generation_plan_context(
                ctx.storage_root,
                project_id=ctx.project_id,
                generation_id=ctx.generation_id,
                slot_id=ctx.slot_id,
            )
            ctx.scene = loaded.get("scene") or {}
            ctx.storyboard_summary = str(loaded.get("storyboardSummary") or "")
            ctx.master_narration = str(loaded.get("masterNarration") or "")
            if not ctx.slot_role:
                ctx.slot_role = str(loaded.get("slotRole") or ctx.slot_id)
        except FileNotFoundError:
            pass

    slot_role = ctx.slot_role or ctx.slot_id
    sanitized = sanitize_instance_spec(
        instance_spec,
        scene=ctx.scene,
        master_narration=ctx.master_narration or None,
    )

    root = (repo_root or detect_repo_root()).resolve()
    scratch_root = draft_dir / ".prepare-scratch"
    if scratch_root.exists():
        shutil.rmtree(scratch_root)
    scratch_root.mkdir(parents=True, exist_ok=True)

    validation_errors = list(ctx.validation_errors)
    skill_output: dict[str, Any] | None = None
    generalized_spec: dict[str, Any] | None = None
    lint_ok = False
    lint_log_path = scratch_root / "lint-log.json"

    for attempt in range(2):
        skill_output = author_fn(
            material_spec=sanitized,
            instance_spec=instance_spec,
            slot={
                "slotId": ctx.slot_id,
                "role": slot_role,
                "storyboardSummary": ctx.storyboard_summary,
            },
            validation_errors=validation_errors,
        )
        generalized_spec = skill_output.get("materialSpec")
        if not isinstance(generalized_spec, dict):
            raise PromoteRejected("author_invalid_output")

        spec_errors = _validate_material_spec(generalized_spec)
        if spec_errors:
            validation_errors = spec_errors
            if attempt == 0:
                continue
            raise PromoteRejected("generalization_schema_failed")

        lint_ok, lint_log_path, lint_errors = _lint_generalized_spec(
            generalized_spec,
            scratch_root=scratch_root,
            hyperframes_cli=hyperframes_cli,
            repo_root=root,
        )
        if lint_ok:
            break
        validation_errors = lint_errors or ["lint failed"]
        if attempt == 1:
            raise PromoteRejected("generalization_lint_failed")

    assert skill_output is not None and generalized_spec is not None
    prepared_dir = draft_dir / "prepared"
    _write_prepared_bundle(
        prepared_dir,
        instance_spec=instance_spec,
        generalized_spec=generalized_spec,
        skill_output=skill_output,
        generation_id=ctx.generation_id,
        slot_id=ctx.slot_id,
        slot_role=slot_role,
        provenance=provenance,
        lint_log_path=lint_log_path,
        draft_dir=draft_dir,
    )
    if scratch_root.exists():
        shutil.rmtree(scratch_root, ignore_errors=True)
    return prepared_dir
