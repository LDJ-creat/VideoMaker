from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from app.services.project_store import ProjectStore
from app.services.sample_selection_store import SampleSelectionStore
from app.services.task_events import now_iso
from app.services.upload_batch_store import UploadBatchStore


def _max_reference_samples() -> int:
    raw = os.getenv("VIDEOMAKER_MAX_REFERENCE_SAMPLES", "4")
    try:
        return max(0, int(raw))
    except ValueError:
        return 4


def _batch_gap_minutes() -> int:
    raw = os.getenv("VIDEOMAKER_SAMPLE_BATCH_GAP_MIN", "30")
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min


def _structure_summary(structure: dict[str, Any] | None) -> str:
    if not structure:
        return ""
    narrative = structure.get("narrative") or {}
    summary = narrative.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return ""


class SampleRecommender:
    def __init__(
        self,
        project_store: ProjectStore,
        selection_store: SampleSelectionStore,
        batch_store: UploadBatchStore,
    ) -> None:
        self.project_store = project_store
        self.selection_store = selection_store
        self.batch_store = batch_store

    def _list_real_samples(self, project_id: str) -> list[dict[str, Any]]:
        return [
            sample
            for sample in self.project_store.list_samples_with_meta(project_id)
            if sample.get("sourceKind") != "knowledge"
        ]

    def _virtual_batches(self, samples: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        if not samples:
            return []
        ordered = sorted(samples, key=lambda item: item.get("createdAt") or "")
        gap = _batch_gap_minutes()
        groups: list[list[dict[str, Any]]] = [[ordered[0]]]
        for sample in ordered[1:]:
            prev = groups[-1][-1]
            prev_time = _parse_iso(str(prev.get("createdAt") or ""))
            curr_time = _parse_iso(str(sample.get("createdAt") or ""))
            delta_min = abs((curr_time - prev_time).total_seconds()) / 60.0
            if delta_min > gap:
                groups.append([sample])
            else:
                groups[-1].append(sample)
        return groups

    def _resolve_active_batch_id(
        self,
        project_id: str,
        samples: list[dict[str, Any]],
    ) -> str | None:
        batches = self.batch_store.list_batches(project_id)
        if batches:
            return batches[0]["id"]
        groups = self._virtual_batches(samples)
        if not groups:
            return None
        latest_group = groups[-1]
        batch_ids = {s.get("uploadBatchId") for s in latest_group if s.get("uploadBatchId")}
        if len(batch_ids) == 1:
            return next(iter(batch_ids))
        return None

    def _samples_for_batch(
        self,
        project_id: str,
        batch_id: str | None,
        samples: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if batch_id:
            batch = self.batch_store.get_batch(batch_id)
            if batch:
                id_set = set(batch["sampleIds"])
                ordered = [s for s in samples if s["id"] in id_set]
                if ordered:
                    return ordered
        groups = self._virtual_batches(samples)
        return groups[-1] if groups else samples

    def recommend(self, project_id: str) -> dict[str, Any]:
        samples = self._list_real_samples(project_id)
        active_batch_id = self._resolve_active_batch_id(project_id, samples)
        batch_samples = self._samples_for_batch(project_id, active_batch_id, samples)

        candidates: list[dict[str, Any]] = []
        for index, sample in enumerate(batch_samples):
            has_structure = sample.get("structure") is not None
            score = 0.9 - (index * 0.05)
            if has_structure:
                score += 0.05
            reasons = ["latest_upload_batch"] if index == 0 else ["same_batch_reference"]
            if has_structure:
                reasons.append("analyzed")
            candidates.append(
                {
                    "sampleId": sample["id"],
                    "score": min(1.0, max(0.0, score)),
                    "reasons": reasons,
                    "summary": _structure_summary(sample.get("structure")),
                    "uploadBatchId": sample.get("uploadBatchId"),
                    "hasStructure": has_structure,
                    "status": sample.get("status") or "unknown",
                }
            )

        analyzed = [c for c in candidates if c["hasStructure"]]
        primary_pool = analyzed or candidates
        suggested_primary = primary_pool[0]["sampleId"] if primary_pool else ""
        max_refs = _max_reference_samples()
        suggested_refs = [
            c["sampleId"]
            for c in primary_pool[1 : 1 + max_refs]
            if c["sampleId"] != suggested_primary
        ]

        return {
            "projectId": project_id,
            "candidates": candidates,
            "suggestedPrimaryId": suggested_primary,
            "suggestedReferenceIds": suggested_refs,
            "computedAt": now_iso(),
        }

    def ensure_selection(
        self,
        project_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any] | None:
        existing = self.selection_store.get_selection(project_id)
        if existing and existing.get("mode") == "user_override" and not force:
            return existing

        samples = self._list_real_samples(project_id)
        if not samples:
            return existing

        recommendation = self.recommend(project_id)
        if not recommendation.get("suggestedPrimaryId"):
            return existing

        primary_id = recommendation["suggestedPrimaryId"]
        reference_ids = recommendation.get("suggestedReferenceIds") or []
        active_batch_id = self._resolve_active_batch_id(project_id, samples)

        selection = {
            "projectId": project_id,
            "primarySampleId": primary_id,
            "referenceSampleIds": reference_ids,
            "activeUploadBatchId": active_batch_id,
            "mode": "auto",
            "recommendationSnapshot": recommendation,
        }
        return self.selection_store.save_selection(selection)

    def update_selection(
        self,
        project_id: str,
        *,
        primary_sample_id: str | None,
        reference_sample_ids: list[str] | None = None,
        active_upload_batch_id: str | None = None,
    ) -> dict[str, Any]:
        if primary_sample_id:
            sample = self.project_store.get_sample(primary_sample_id)
            if sample is None or sample["projectId"] != project_id:
                raise ValueError(f"Sample not found in project: {primary_sample_id}")

        refs = reference_sample_ids or []
        for ref_id in refs:
            sample = self.project_store.get_sample(ref_id)
            if sample is None or sample["projectId"] != project_id:
                raise ValueError(f"Reference sample not found in project: {ref_id}")

        selection = {
            "projectId": project_id,
            "primarySampleId": primary_sample_id,
            "referenceSampleIds": [r for r in refs if r != primary_sample_id],
            "activeUploadBatchId": active_upload_batch_id,
            "mode": "user_override" if primary_sample_id else "none",
        }
        return self.selection_store.save_selection(selection)

    def reset_selection(self, project_id: str) -> dict[str, Any] | None:
        return self.ensure_selection(project_id, force=True)

    def resolve_effective_selection(
        self,
        project_id: str,
        *,
        override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if override and override.get("primarySampleId"):
            return {
                "projectId": project_id,
                "primarySampleId": override["primarySampleId"],
                "referenceSampleIds": override.get("referenceSampleIds") or [],
                "mode": "user_override",
                "updatedAt": now_iso(),
            }
        selection = self.selection_store.get_selection(project_id)
        if selection and selection.get("primarySampleId"):
            return selection
        ensured = self.ensure_selection(project_id)
        if ensured and ensured.get("primarySampleId"):
            return ensured
        latest = self.project_store.get_latest_analyzed_sample(project_id)
        if latest is None:
            raise ValueError("No analyzed sample available for project")
        return {
            "projectId": project_id,
            "primarySampleId": latest["id"],
            "referenceSampleIds": [],
            "mode": "auto",
            "updatedAt": now_iso(),
        }

    def load_structures_for_selection(
        self,
        selection: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        primary_id = selection.get("primarySampleId")
        if not primary_id:
            raise ValueError("Sample selection missing primarySampleId")

        primary_sample = self.project_store.get_sample(str(primary_id))
        if primary_sample is None:
            raise ValueError(f"Primary sample not found: {primary_id}")
        primary_structure = primary_sample.get("structure")
        if primary_structure is None:
            raise ValueError(
                f"Primary sample {primary_id} has no structure; run analysis first."
            )

        reference_structures: list[dict[str, Any]] = []
        for ref_id in selection.get("referenceSampleIds") or []:
            if str(ref_id) == str(primary_id):
                continue
            ref_sample = self.project_store.get_sample(str(ref_id))
            if ref_sample is None:
                continue
            ref_structure = ref_sample.get("structure")
            if ref_structure is not None:
                reference_structures.append(ref_structure)

        return primary_sample, primary_structure, reference_structures
