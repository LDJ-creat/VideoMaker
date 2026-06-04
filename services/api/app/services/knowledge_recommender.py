from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from knowledge.recommender import build_recommendation

from app.services.knowledge_store import KnowledgeStore
from app.services.pipeline_runner import SubprocessDemoPipeline
from app.services.project_store import ProjectStore


def _fixture_mode_enabled() -> bool:
    return os.getenv("VIDEOMAKER_FIXTURE_MODE", "true").lower() in ("1", "true", "yes")


class KnowledgeRecommender:
    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        project_store: ProjectStore,
        *,
        storage_root: Path | None = None,
        database_path: Path | None = None,
        api_base_url: str | None = None,
    ) -> None:
        self.knowledge_store = knowledge_store
        self.project_store = project_store
        self.storage_root = storage_root or knowledge_store.storage_root
        self.database_path = database_path or knowledge_store.database.path
        self.api_base_url = api_base_url

    def _validate_primary_entry(self, entry_id: str | None) -> None:
        if not entry_id:
            return
        entry = self.knowledge_store.get_entry(str(entry_id))
        if entry is None or entry.get("status") != "published":
            raise ValueError(f"Knowledge entry not found: {entry_id}")
        if self.knowledge_store.read_structure(str(entry_id)) is None:
            raise ValueError(f"Knowledge structure file missing: {entry_id}")

    def _optional_llm_rerank(
        self,
        *,
        project_id: str,
        brief: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[str] | None:
        if _fixture_mode_enabled() or not candidates:
            return None

        pipeline = SubprocessDemoPipeline(
            database_path=self.database_path,
            storage_root=self.storage_root,
            api_base_url=self.api_base_url,
        )
        try:
            result = pipeline.run_knowledge_selector(
                project_id=project_id,
                task_id=f"knowledge-select-{uuid.uuid4().hex[:8]}",
                user_brief=brief,
                candidates=candidates,
            )
        except (RuntimeError, FileNotFoundError, OSError):
            return None

        if not result.get("ok"):
            return None

        selection = result.get("selection") or {}
        ranked = selection.get("rankedEntryIds")
        if not isinstance(ranked, list):
            return None

        candidate_ids = {item["entryId"] for item in candidates}
        filtered = [str(entry_id) for entry_id in ranked if str(entry_id) in candidate_ids]
        return filtered or None

    def recommend(
        self,
        project_id: str,
        *,
        ranked_entry_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        brief = self.project_store.get_brief(project_id) or {
            "topic": "",
            "sellingPoints": [],
            "mustMention": [],
            "avoidMention": [],
        }
        structure = self.project_store.get_latest_analyzed_sample_structure(project_id)

        entries = self.knowledge_store.list_entries(status="published")
        stage_a = build_recommendation(
            project_id=project_id,
            entries=entries,
            brief=brief,
            structure=structure,
        )
        rerank_ids = ranked_entry_ids or self._optional_llm_rerank(
            project_id=project_id,
            brief=brief,
            candidates=stage_a.get("candidates", []),
        )
        if rerank_ids:
            return build_recommendation(
                project_id=project_id,
                entries=entries,
                brief=brief,
                structure=structure,
                ranked_entry_ids=rerank_ids,
            )
        return stage_a

    def ensure_selection(
        self,
        project_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any] | None:
        existing = self.knowledge_store.get_selection(project_id)
        if existing and existing.get("mode") == "user_override" and not force:
            return existing

        entries = self.knowledge_store.list_entries(status="published")
        if not entries:
            return existing

        recommendation = self.recommend(project_id)
        if not recommendation.get("candidates"):
            return existing

        primary_id = recommendation.get("suggestedPrimaryId")
        if primary_id:
            self._validate_primary_entry(str(primary_id))

        reference_ids = [
            item["entryId"]
            for item in recommendation.get("candidates", [])[1:3]
            if item.get("entryId") != primary_id
        ]

        applied_as_structure = False
        if primary_id and not self.knowledge_store.has_analyzed_sample_structure(
            self.project_store,
            project_id,
        ):
            self.knowledge_store.apply_entry_to_project(
                project_id=project_id,
                entry_id=str(primary_id),
                project_store=self.project_store,
            )
            applied_as_structure = True

        selection = {
            "projectId": project_id,
            "primaryEntryId": primary_id,
            "referenceEntryIds": reference_ids,
            "mode": "auto",
            "appliedAsStructure": applied_as_structure,
            "recommendationSnapshot": recommendation,
        }
        return self.knowledge_store.save_selection(selection)

    def update_selection(
        self,
        project_id: str,
        *,
        primary_entry_id: str | None,
        reference_entry_ids: list[str] | None = None,
        apply_structure: bool = False,
    ) -> dict[str, Any]:
        if primary_entry_id:
            self._validate_primary_entry(primary_entry_id)
        for ref_id in reference_entry_ids or []:
            self._validate_primary_entry(str(ref_id))

        if primary_entry_id and apply_structure:
            self.knowledge_store.apply_entry_to_project(
                project_id=project_id,
                entry_id=primary_entry_id,
                project_store=self.project_store,
            )
        selection = {
            "projectId": project_id,
            "primaryEntryId": primary_entry_id,
            "referenceEntryIds": reference_entry_ids or [],
            "mode": "user_override" if primary_entry_id else "none",
            "appliedAsStructure": bool(apply_structure),
        }
        return self.knowledge_store.save_selection(selection)

    def reset_selection(self, project_id: str) -> dict[str, Any] | None:
        return self.ensure_selection(project_id, force=True)
