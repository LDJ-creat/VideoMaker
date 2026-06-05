from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.index_builder import build_entry_meta
from knowledge.paths import category_slug, draft_dir, published_entry_dir, rel_uri, resolve_storage_path

from app.db.session import Database
from app.services.sample_analysis import load_sample_analysis_artifact
from app.services.task_events import now_iso

_DRAFT_META_FALLBACK_KEYS = ("hasBgm", "voPersona", "visualStyle", "rhetoricalPattern")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _looks_corrupted(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return all(char == "?" for char in text)


def _pick_text(*values: str | None, default: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and not _looks_corrupted(text):
            return text
    return default

class KnowledgeStore:
    def __init__(self, database: Database, storage_root: Path) -> None:
        self.database = database
        self.storage_root = storage_root

    def _entry_meta_path(self, entry: dict[str, Any]) -> Path | None:
        try:
            skill_path = resolve_storage_path(self.storage_root, entry["skillMdUri"])
        except ValueError:
            return None
        meta_path = skill_path.parent / "entry-meta.json"
        return meta_path if meta_path.is_file() else None

    def _parse_skill_frontmatter(self, entry: dict[str, Any]) -> dict[str, Any]:
        try:
            skill_path = resolve_storage_path(self.storage_root, entry["skillMdUri"])
        except ValueError:
            return {}
        return self._parse_skill_frontmatter_from_path(skill_path)

    def _parse_skill_frontmatter_from_path(self, skill_path: Path) -> dict[str, Any]:
        if not skill_path.is_file():
            return {}
        text = skill_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}
        meta: dict[str, Any] = {}
        for line in parts[1].splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            meta[key.strip()] = value.strip()
        return meta

    def _read_disk_meta(self, entry: dict[str, Any]) -> dict[str, Any]:
        meta_path = self._entry_meta_path(entry)
        disk_meta: dict[str, Any] = {}
        if meta_path is not None:
            disk_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        skill_meta = self._parse_skill_frontmatter(entry)
        merged = {**skill_meta, **disk_meta}
        for key, value in skill_meta.items():
            if _looks_corrupted(str(disk_meta.get(key, ""))) and value:
                merged[key] = value
        return merged

    def _persist_entry_display_fields(self, entry_id: str, fields: dict[str, Any]) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE knowledge_entries
                SET title = ?, category = ?, style = ?, summary = ?,
                    hook_type = ?, tempo = ?, duration_bucket = ?, slot_pattern = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    fields["title"],
                    fields["category"],
                    fields["style"],
                    fields["summary"],
                    fields.get("hookType"),
                    fields.get("tempo"),
                    fields.get("durationBucket"),
                    fields.get("slotPattern"),
                    now_iso(),
                    entry_id,
                ),
            )

    def _enrich_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        disk_meta = self._read_disk_meta(entry)
        if not disk_meta:
            return entry

        enriched = dict(entry)
        display_keys = (
            "title",
            "category",
            "style",
            "summary",
            "hookType",
            "tempo",
            "durationBucket",
            "slotPattern",
        )
        repaired = False
        for key in display_keys:
            disk_value = disk_meta.get(key)
            if disk_value is None:
                continue
            if _looks_corrupted(str(enriched.get(key, ""))):
                enriched[key] = disk_value
                repaired = True

        if repaired:
            meta_path = self._entry_meta_path(entry)
            if meta_path is not None:
                merged_meta = {**disk_meta}
                for key in display_keys:
                    if enriched.get(key) is not None:
                        merged_meta[key] = enriched[key]
                meta_path.write_text(
                    json.dumps(merged_meta, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            self._persist_entry_display_fields(enriched["id"], enriched)
        return enriched

    def _row_to_entry(self, row: Any) -> dict[str, Any]:
        entry = {
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
        return self._enrich_entry(entry)

    def list_entries(
        self,
        *,
        status: str = "published",
        category: str | None = None,
        style: str | None = None,
        hook_type: str | None = None,
        tempo: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["status = ?"]
        values: list[Any] = [status]
        if category:
            clauses.append("category = ?")
            values.append(category)
        if style:
            clauses.append("style = ?")
            values.append(style)
        if hook_type:
            clauses.append("hook_type = ?")
            values.append(hook_type)
        if tempo:
            clauses.append("tempo = ?")
            values.append(tempo)
        if query:
            clauses.append("(title LIKE ? OR summary LIKE ? OR category LIKE ? OR style LIKE ?)")
            pattern = f"%{query}%"
            values.extend([pattern, pattern, pattern, pattern])

        sql = f"""
            SELECT * FROM knowledge_entries
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC
        """
        with self.database.connect() as connection:
            rows = connection.execute(sql, values).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def read_skill_md(self, entry_id: str) -> str | None:
        entry = self.get_entry(entry_id)
        if entry is None:
            return None
        try:
            path = resolve_storage_path(self.storage_root, entry["skillMdUri"])
        except ValueError:
            return None
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def read_structure(self, entry_id: str) -> dict[str, Any] | None:
        entry = self.get_entry(entry_id)
        if entry is None:
            return None
        try:
            path = resolve_storage_path(self.storage_root, entry["structureJsonUri"])
        except ValueError:
            return None
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def find_published_by_source(self, project_id: str, sample_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM knowledge_entries
                WHERE source_project_id = ? AND source_sample_id = ? AND status = 'published'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id, sample_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def get_draft(self, project_id: str, sample_id: str) -> dict[str, Any] | None:
        root = draft_dir(self.storage_root, project_id, sample_id)
        skill_path = root / "structure-skill.md"
        if not skill_path.is_file():
            return None
        meta_path = root / "entry-meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        return {
            "projectId": project_id,
            "sampleId": sample_id,
            "skillMarkdown": skill_path.read_text(encoding="utf-8"),
            "entryMeta": meta,
            "skillMdUri": rel_uri(self.storage_root, skill_path),
            "structureJsonUri": rel_uri(self.storage_root, root / "video-structure.json"),
        }

    def promote_draft(
        self,
        *,
        project_id: str,
        sample_id: str,
        title: str,
        category: str,
        style: str,
        hook_type: str | None = None,
        summary_override: str | None = None,
        category_slug_override: str | None = None,
    ) -> dict[str, Any]:
        existing = self.find_published_by_source(project_id, sample_id)
        if existing is not None:
            return self._enrich_entry(existing)

        draft_root = draft_dir(self.storage_root, project_id, sample_id)
        skill_path = draft_root / "structure-skill.md"
        structure_path = draft_root / "video-structure.json"
        if not skill_path.is_file() or not structure_path.is_file():
            raise FileNotFoundError("Knowledge draft not found for sample")

        structure = json.loads(structure_path.read_text(encoding="utf-8"))
        quality_warnings = list((structure.get("analysisQuality") or {}).get("warnings") or [])
        if any(str(item).startswith("critical:") for item in quality_warnings):
            raise ValueError(
                "Cannot promote knowledge draft while critical structure quality warnings remain"
            )

        draft_meta_path = draft_root / "entry-meta.json"
        draft_meta = (
            json.loads(draft_meta_path.read_text(encoding="utf-8"))
            if draft_meta_path.is_file()
            else {}
        )
        skill_meta = self._parse_skill_frontmatter_from_path(skill_path)
        for key, value in skill_meta.items():
            if value and _looks_corrupted(str(draft_meta.get(key, ""))):
                draft_meta[key] = value
        title = _pick_text(title, draft_meta.get("title"), skill_meta.get("title"), default="结构经验")
        category = _pick_text(
            category,
            draft_meta.get("category"),
            skill_meta.get("category"),
            default="通用短视频",
        )
        style = _pick_text(style, draft_meta.get("style"), skill_meta.get("style"), default="标准结构")
        summary_override = _pick_text(
            summary_override,
            draft_meta.get("summary"),
            skill_meta.get("summary"),
            default=title,
        )
        hook_type = hook_type or draft_meta.get("hookType") or skill_meta.get("hookType")

        sample_analysis = load_sample_analysis_artifact(
            self.storage_root,
            project_id=project_id,
            sample_id=sample_id,
        )
        meta = build_entry_meta(
            structure,
            title=title,
            category=category,
            style=style,
            summary=summary_override or title,
            hook_type=hook_type,
            sample_analysis=sample_analysis,
        )
        for key in _DRAFT_META_FALLBACK_KEYS:
            draft_value = draft_meta.get(key)
            if draft_value is None:
                continue
            if key == "hasBgm" and meta.get("hasBgm"):
                continue
            if not meta.get(key):
                meta[key] = draft_value
        slug = category_slug_override or category_slug(category)
        entry_id = str(uuid.uuid4())
        target = published_entry_dir(self.storage_root, slug, entry_id)
        target.mkdir(parents=True, exist_ok=True)

        shutil.copy2(skill_path, target / "structure-skill.md")
        shutil.copy2(structure_path, target / "video-structure.json")
        (target / "entry-meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        created_at = now_iso()
        entry = {
            "id": entry_id,
            "status": "published",
            "title": title,
            "category": category,
            "categorySlug": slug,
            "style": style,
            "hookType": meta.get("hookType"),
            "tempo": meta.get("tempo"),
            "durationBucket": meta.get("durationBucket"),
            "slotPattern": meta.get("slotPattern", ""),
            "summary": summary_override or meta.get("summary") or title,
            "skillMdUri": rel_uri(self.storage_root, target / "structure-skill.md"),
            "structureJsonUri": rel_uri(self.storage_root, target / "video-structure.json"),
            "sourceProjectId": project_id,
            "sourceSampleId": sample_id,
            "version": 1,
            "createdAt": created_at,
            "updatedAt": created_at,
        }

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_entries (
                  id, status, title, category, category_slug, style, hook_type, tempo,
                  duration_bucket, slot_pattern, summary, skill_md_uri, structure_json_uri,
                  source_project_id, source_sample_id, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["id"],
                    entry["status"],
                    entry["title"],
                    entry["category"],
                    entry["categorySlug"],
                    entry["style"],
                    entry["hookType"],
                    entry["tempo"],
                    entry["durationBucket"],
                    entry["slotPattern"],
                    entry["summary"],
                    entry["skillMdUri"],
                    entry["structureJsonUri"],
                    entry["sourceProjectId"],
                    entry["sourceSampleId"],
                    entry["version"],
                    entry["createdAt"],
                    entry["updatedAt"],
                ),
            )
        return entry

    def get_selection(self, project_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT project_id, primary_entry_id, reference_entry_ids_json, mode,
                       applied_as_structure, recommendation_json, updated_at
                FROM project_knowledge_selection
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
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

    def save_selection(self, selection: dict[str, Any]) -> dict[str, Any]:
        updated_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_knowledge_selection (
                  project_id, primary_entry_id, reference_entry_ids_json, mode,
                  applied_as_structure, recommendation_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                  primary_entry_id = excluded.primary_entry_id,
                  reference_entry_ids_json = excluded.reference_entry_ids_json,
                  mode = excluded.mode,
                  applied_as_structure = excluded.applied_as_structure,
                  recommendation_json = excluded.recommendation_json,
                  updated_at = excluded.updated_at
                """,
                (
                    selection["projectId"],
                    selection.get("primaryEntryId"),
                    json.dumps(selection.get("referenceEntryIds") or [], ensure_ascii=False),
                    selection.get("mode", "auto"),
                    1 if selection.get("appliedAsStructure") else 0,
                    json.dumps(selection.get("recommendationSnapshot"), ensure_ascii=False)
                    if selection.get("recommendationSnapshot")
                    else None,
                    updated_at,
                ),
            )
        selection["updatedAt"] = updated_at
        return selection

    def apply_entry_to_project(
        self,
        *,
        project_id: str,
        entry_id: str,
        project_store: Any,
        allow_overwrite: bool = False,
    ) -> dict[str, Any]:
        if not allow_overwrite and self.has_analyzed_sample_structure(project_store, project_id):
            raise ValueError(
                "Project already has an analyzed sample structure; "
                "knowledge applies as reference only"
            )

        entry = self.get_entry(entry_id)
        if entry is None or entry.get("status") != "published":
            raise ValueError("Knowledge entry not found")

        structure = self.read_structure(entry_id)
        if structure is None:
            raise ValueError("Knowledge structure file missing")

        structure = json.loads(json.dumps(structure, ensure_ascii=False))
        structure["projectId"] = project_id
        structure["sourceVideoId"] = f"knowledge-{entry_id}"
        structure["id"] = f"video-structure-knowledge-{entry_id}"

        existing = None
        for sample in project_store.list_samples(project_id):
            if sample.get("sourceKind") == "knowledge":
                existing = sample
                break

        if existing is None:
            sample = project_store.create_sample(
                project_id=project_id,
                source_kind="knowledge",
                status="analyzed",
            )
            sample_id = sample["id"]
        else:
            sample_id = existing["id"]

        project_store.update_sample(
            sample_id,
            status="analyzed",
            structure=structure,
        )
        return {"sampleId": sample_id, "structure": structure, "entryId": entry_id}

    def has_analyzed_sample_structure(self, project_store: Any, project_id: str) -> bool:
        for sample in project_store.list_samples(project_id):
            if sample.get("structure") is not None and sample.get("sourceKind") != "knowledge":
                return True
        return False
