from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.sample_seed_service import import_sample_from_knowledge_entry


class KnowledgeTemplateBootstrapError(ValueError):
    pass


def _validate_entry_ids(
    *,
    primary_entry_id: str,
    reference_entry_ids: list[str],
) -> None:
    if len(reference_entry_ids) > 2:
        raise KnowledgeTemplateBootstrapError("最多选择 2 个参考模板")
    if primary_entry_id in reference_entry_ids:
        raise KnowledgeTemplateBootstrapError("主模板不能同时作为参考模板")
    if len(set(reference_entry_ids)) != len(reference_entry_ids):
        raise KnowledgeTemplateBootstrapError("参考模板不能重复")


def _load_entry_or_raise(knowledge_store: Any, entry_id: str) -> dict[str, Any]:
    entry = knowledge_store.get_entry(entry_id)
    if entry is None or entry.get("status") != "published":
        raise KnowledgeTemplateBootstrapError(f"Knowledge entry not found: {entry_id}")
    if (entry.get("entryKind") or "structure") != "structure":
        raise KnowledgeTemplateBootstrapError(f"Entry is not a structure template: {entry_id}")
    return entry


def create_project_from_knowledge_template(
    *,
    name: str,
    category_slug: str,
    primary_entry_id: str,
    reference_entry_ids: list[str],
    storage_root: Path,
    project_store: Any,
    knowledge_store: Any,
    sample_selection_store: Any,
) -> dict[str, Any]:
    refs = [str(item) for item in reference_entry_ids if str(item).strip()]
    _validate_entry_ids(primary_entry_id=primary_entry_id, reference_entry_ids=refs)

    ordered_entry_ids = [primary_entry_id, *refs]
    entries = [_load_entry_or_raise(knowledge_store, entry_id) for entry_id in ordered_entry_ids]

    for entry in entries:
        slug = str(entry.get("categorySlug") or "")
        if slug != category_slug:
            raise KnowledgeTemplateBootstrapError("所选模板不属于同一分类")
        importable, reason = knowledge_store.assess_entry_importable(entry, project_store)
        if not importable:
            raise KnowledgeTemplateBootstrapError(reason or "模板不可导入")

    project = project_store.create_project(name.strip())
    project_id = str(project["id"])
    imported_samples: list[dict[str, Any]] = []
    sample_id_by_entry: dict[str, str] = {}

    try:
        for entry in entries:
            new_sample_id = import_sample_from_knowledge_entry(
                storage_root,
                project_store,
                knowledge_store,
                target_project_id=project_id,
                entry=entry,
            )
            sample_id_by_entry[str(entry["id"])] = new_sample_id
            imported_samples.append(
                {
                    "sampleId": new_sample_id,
                    "entryId": entry["id"],
                    "title": entry.get("title"),
                }
            )

        primary_sample_id = sample_id_by_entry[primary_entry_id]
        reference_sample_ids = [sample_id_by_entry[item] for item in refs]

        sample_selection = sample_selection_store.save_selection(
            {
                "projectId": project_id,
                "primarySampleId": primary_sample_id,
                "referenceSampleIds": reference_sample_ids,
                "mode": "user_override",
            }
        )
        knowledge_selection = knowledge_store.save_selection(
            {
                "projectId": project_id,
                "primaryEntryId": primary_entry_id,
                "referenceEntryIds": refs,
                "mode": "user_override",
                "appliedAsStructure": False,
            }
        )
    except Exception as exc:
        project_store.delete_project(project_id, storage_root=storage_root)
        if isinstance(exc, KnowledgeTemplateBootstrapError):
            raise
        raise KnowledgeTemplateBootstrapError(str(exc)) from exc

    return {
        "project": {
            "id": project_id,
            "name": project["name"],
            "createdAt": project["createdAt"],
        },
        "importedSamples": imported_samples,
        "sampleSelection": sample_selection,
        "knowledgeSelection": knowledge_selection,
    }
