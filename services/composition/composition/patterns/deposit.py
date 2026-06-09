from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from knowledge.paths import (
    assert_under_storage_root,
    category_slug,
    published_entry_dir,
    rel_uri,
    validate_storage_segment,
)

from composition.patterns.lint_verify import lint_log_confirms_pass
from composition.types import PatternDepositContext, PatternPromoteRequest


LOGGER = logging.getLogger(__name__)


def composition_pattern_entry_id(generation_id: str, slot_id: str) -> str:
    gen = validate_storage_segment(generation_id, field="generation_id")
    slot = validate_storage_segment(slot_id, field="slot_id")
    return f"comp-{gen}-{slot}"


def composition_drafts_generation_dir(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
) -> Path:
    project = validate_storage_segment(project_id, field="project_id")
    generation = validate_storage_segment(generation_id, field="generation_id")
    path = (
        storage_root
        / "projects"
        / project
        / "knowledge"
        / "drafts"
        / "composition"
        / generation
    )
    return assert_under_storage_root(path, storage_root)


def composition_draft_dir(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    slot_id: str,
) -> Path:
    slot = validate_storage_segment(slot_id, field="slot_id")
    path = composition_drafts_generation_dir(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
    ) / slot
    return assert_under_storage_root(path, storage_root)


def prepared_pattern_dir(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    slot_id: str,
) -> Path:
    return composition_draft_dir(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        slot_id=slot_id,
    ) / "prepared"


def _copy_references(source_composition: Path, target: Path) -> None:
    refs_src = source_composition / "references"
    if not refs_src.is_dir():
        return
    refs_dest = target / "references"
    if refs_dest.exists():
        shutil.rmtree(refs_dest)
    shutil.copytree(refs_src, refs_dest)


def _write_pattern_files(
    target: Path,
    *,
    spec: dict[str, Any],
    slot_id: str,
    slot_role: str,
    generation_id: str,
    lint_passed: bool,
    composition_dir: Path,
    lint_log_path: Path | None,
    title: str | None = None,
) -> None:
    target.mkdir(parents=True, exist_ok=True)
    template_spec = json.loads(json.dumps(spec))
    composition = template_spec.pop("composition", None)
    if isinstance(composition, dict):
        template_spec["composition"] = composition
    (target / "spec.template.json").write_text(
        json.dumps(template_spec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    role_label = slot_role or slot_id
    skill_title = title or f"Composition pattern for {role_label}"
    references_md = "- [MaterialSpec template](./spec.template.json)"
    refs_dest = target / "references"
    if refs_dest.is_dir():
        for ref_file in sorted(refs_dest.iterdir()):
            if ref_file.is_file():
                references_md += f"\n- [{ref_file.name}](./references/{ref_file.name})"

    skill_md = f"""---
entryKind: composition_pattern
title: {skill_title}
slotRoles: [{role_label}]
lintPassed: {str(lint_passed).lower()}
sourceGenerationId: {generation_id}
---

## 适用场景
Auto-deposited from generation {generation_id} slot {slot_id} ({role_label}).

## References
{references_md}
"""
    (target / "composition-skill.md").write_text(skill_md, encoding="utf-8")
    meta = {
        "entryKind": "composition_pattern",
        "title": skill_title,
        "slotRoles": [role_label],
        "lintPassed": lint_passed,
        "sourceGenerationId": generation_id,
        "sourceSlotId": slot_id,
    }
    (target / "entry-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    provenance: dict[str, Any] = {
        "sourceGenerationId": generation_id,
        "sourceSlotId": slot_id,
        "sourceSlotRole": role_label,
        "lintPassed": lint_passed,
        "compositionDir": str(composition_dir),
    }
    if lint_log_path is not None and lint_log_path.is_file():
        draft_lint = target / "lint-log.json"
        shutil.copy2(lint_log_path, draft_lint)
        provenance["lintLogPath"] = "lint-log.json"
    (target / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


def deposit_pattern_candidate(ctx: PatternDepositContext) -> dict[str, str]:
    if not ctx.render_passed:
        raise ValueError("pattern deposit requires render success")
    if not ctx.lint_passed:
        raise ValueError("pattern deposit requires lint success (skip-lint renders cannot deposit)")
    if ctx.lint_log_path is not None and not lint_log_confirms_pass(ctx.lint_log_path):
        raise ValueError("pattern deposit requires lint log with ok=true")

    target = composition_draft_dir(
        ctx.storage_root,
        project_id=ctx.project_id,
        generation_id=ctx.generation_id,
        slot_id=ctx.slot_id,
    )
    _copy_references(ctx.composition_dir, target)
    _write_pattern_files(
        target,
        spec=ctx.spec,
        slot_id=ctx.slot_id,
        slot_role=ctx.slot_role,
        generation_id=ctx.generation_id,
        lint_passed=ctx.lint_passed,
        composition_dir=ctx.composition_dir,
        lint_log_path=ctx.lint_log_path,
    )
    return {
        "compositionSkillUri": rel_uri(ctx.storage_root, target / "composition-skill.md"),
        "specTemplateUri": rel_uri(ctx.storage_root, target / "spec.template.json"),
    }


class PromoteRejected(ValueError):
    pass


def promote_pattern(
    request: PatternPromoteRequest,
    *,
    entry_id: str | None = None,
    hyperframes_cli=None,
) -> dict[str, Any]:
    draft = composition_draft_dir(
        request.storage_root,
        project_id=request.project_id,
        generation_id=request.generation_id,
        slot_id=request.slot_id,
    )
    prepared = prepared_pattern_dir(
        request.storage_root,
        project_id=request.project_id,
        generation_id=request.generation_id,
        slot_id=request.slot_id,
    )
    if not prepared.is_dir():
        raise PromoteRejected("prepared_bundle_missing")
    if not draft.is_dir():
        raise PromoteRejected("draft_not_found")

    lint_log = prepared / "lint-log.json"
    if not lint_log_confirms_pass(lint_log):
        raise PromoteRejected("lint_not_passed")

    provenance_path = prepared / "provenance.json"
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("lintPassed") is False:
            raise PromoteRejected("lint_not_passed")

    meta_path = prepared / "entry-meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    if not meta.get("lintPassed", True):
        raise PromoteRejected("lint_not_passed")

    category = request.category or meta.get("category") or "composition"
    slug = category_slug(str(category))
    entry_id = entry_id or composition_pattern_entry_id(request.generation_id, request.slot_id)
    published = published_entry_dir(request.storage_root, slug, entry_id)
    if published.exists():
        shutil.rmtree(published)
    shutil.copytree(prepared, published)
    return {
        "entryId": entry_id,
        "categorySlug": slug,
        "publishedDir": str(published),
        "entryKind": "composition_pattern",
        "title": request.title or meta.get("title"),
        "summary": meta.get("summary"),
        "category": category,
    }
