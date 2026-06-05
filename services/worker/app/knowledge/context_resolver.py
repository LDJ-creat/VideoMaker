from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from knowledge.paths import resolve_storage_path
from knowledge.skill_sections import build_knowledge_context_payload


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_selection_from_db(database_path: Path, project_id: str) -> dict[str, Any] | None:
    if not database_path.is_file():
        return None
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """
            SELECT project_id, primary_entry_id, reference_entry_ids_json, mode,
                   applied_as_structure, recommendation_json, updated_at
            FROM project_knowledge_selection
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    refs = json.loads(row["reference_entry_ids_json"] or "[]")
    recommendation = (
        json.loads(row["recommendation_json"]) if row["recommendation_json"] else None
    )
    return {
        "projectId": row["project_id"],
        "primaryEntryId": row["primary_entry_id"],
        "referenceEntryIds": refs if isinstance(refs, list) else [],
        "mode": row["mode"],
        "appliedAsStructure": bool(row["applied_as_structure"]),
        "recommendationSnapshot": recommendation,
        "updatedAt": row["updated_at"],
    }


def load_entry_from_db(database_path: Path, entry_id: str) -> dict[str, Any] | None:
    if not database_path.is_file():
        return None
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM knowledge_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _row_to_entry(row)


def _row_to_entry(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "status": row["status"],
        "title": row["title"],
        "category": row["category"],
        "categorySlug": row["category_slug"],
        "style": row["style"],
        "hookType": row["hook_type"],
        "tempo": row["tempo"],
        "durationBucket": row["duration_bucket"],
        "slotPattern": row["slot_pattern"],
        "summary": row["summary"],
        "skillMdUri": row["skill_md_uri"],
        "structureJsonUri": row["structure_json_uri"],
        "sourceProjectId": row["source_project_id"],
        "sourceSampleId": row["source_sample_id"],
        "version": row["version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def resolve_knowledge_context(
    *,
    storage_root: Path,
    database_path: Path | None,
    project_id: str,
    level: int = 1,
    weak_slot_count: int = 0,
    video_structure: dict[str, Any] | None = None,
    sample_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if database_path is None:
        return build_knowledge_context_payload(
            primary_entry=None,
            primary_skill_md=None,
            reference_entries=[],
            reference_skill_mds=[],
            level=level,
            video_structure=video_structure,
            sample_analysis=sample_analysis,
        )

    selection = load_selection_from_db(database_path, project_id)
    if selection is None or not selection.get("primaryEntryId"):
        return build_knowledge_context_payload(
            primary_entry=None,
            primary_skill_md=None,
            reference_entries=[],
            reference_skill_mds=[],
            level=level,
            video_structure=video_structure,
            sample_analysis=sample_analysis,
        )

    effective_level = 2 if weak_slot_count >= 2 else level
    primary = load_entry_from_db(database_path, str(selection["primaryEntryId"]))
    if primary is None:
        return build_knowledge_context_payload(
            primary_entry=None,
            primary_skill_md=None,
            reference_entries=[],
            reference_skill_mds=[],
            level=effective_level,
            video_structure=video_structure,
            sample_analysis=sample_analysis,
        )

    primary_md = None
    if primary.get("skillMdUri"):
        try:
            primary_md = _read_text(
                resolve_storage_path(storage_root, str(primary["skillMdUri"]))
            )
        except ValueError:
            primary_md = None
    references: list[dict[str, Any]] = []
    reference_mds: list[str] = []
    for ref_id in selection.get("referenceEntryIds") or []:
        entry = load_entry_from_db(database_path, str(ref_id))
        if entry is None:
            continue
        references.append(entry)
        ref_md = ""
        if entry.get("skillMdUri"):
            try:
                ref_md = _read_text(
                    resolve_storage_path(storage_root, str(entry["skillMdUri"]))
                ) or ""
            except ValueError:
                ref_md = ""
        reference_mds.append(ref_md)

    return build_knowledge_context_payload(
        primary_entry=primary,
        primary_skill_md=primary_md,
        reference_entries=references,
        reference_skill_mds=reference_mds,
        level=effective_level,
        video_structure=video_structure,
        sample_analysis=sample_analysis,
    )


def load_structure_for_entry(storage_root: Path, entry: dict[str, Any]) -> dict[str, Any] | None:
    try:
        path = resolve_storage_path(storage_root, str(entry["structureJsonUri"]))
    except ValueError:
        return None
    return _read_json(path)
