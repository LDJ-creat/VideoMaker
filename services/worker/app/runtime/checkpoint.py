from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CHECKPOINT_VERSION = "p0-v1"

ANALYSIS_STAGES = (
    "downloading",
    "extracting_poster",
    "extracting_metadata",
    "extracting_audio",
    "transcribing",
    "analyzing_audio",
    "detecting_shots",
    "extracting_keyframes",
    "extracting_visual_facts",
    "consolidating",
    "extracting_structure_direct",
    "extracting_structure",
    "proposing_segments",
    "analyzing_segments",
    "compiling_structure",
    "critiquing_structure",
    "rendering_knowledge_draft",
)

GENERATION_STAGES = (
    "analyzing_assets",
    "mapping_slots",
    "drafting_master_script",
    "drafting_storyboard",
    "synthesizing_canonical_narration",
    "adapting_narration_density",
    "planning_completion",
    "generating_material",
    "assembling_final",
    "building_timeline",
    "rendering",
)

HUMAN_GATE_STAGES = frozenset({
    "awaiting_master_review",
    "awaiting_storyboard_review",
    "awaiting_material_review",
})


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


@dataclass
class AnalysisCheckpoint:
    version: str = CHECKPOINT_VERSION
    sampleId: str = ""
    completedStages: list[str] = field(default_factory=list)
    stageTimings: list[dict[str, Any]] = field(default_factory=list)
    failedStage: str | None = None
    videoPath: str | None = None
    analysisRoute: str | None = None
    updatedAt: str = field(default_factory=_utc_now_iso)
    _stage_started_at: str | None = field(default=None, repr=False)

    @classmethod
    def load(cls, path: Path) -> AnalysisCheckpoint:
        if not path.is_file():
            return cls()
        data = _read_json(path)
        if not isinstance(data, dict):
            return cls()
        return cls(
            version=str(data.get("version", CHECKPOINT_VERSION)),
            sampleId=str(data.get("sampleId", "")),
            completedStages=list(data.get("completedStages", [])),
            stageTimings=[
                item for item in (data.get("stageTimings") or []) if isinstance(item, dict)
            ],
            failedStage=data.get("failedStage"),
            videoPath=data.get("videoPath"),
            analysisRoute=data.get("analysisRoute"),
            updatedAt=str(data.get("updatedAt", _utc_now_iso())),
            _stage_started_at=data.get("_stageStartedAt"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updatedAt = _utc_now_iso()
        payload = asdict(self)
        payload.pop("_stage_started_at", None)
        if self._stage_started_at:
            payload["_stageStartedAt"] = self._stage_started_at
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def begin_stage(self, stage: str) -> None:
        now = _utc_now_iso()
        if self._stage_started_at is None and not self.stageTimings:
            self._stage_started_at = self.updatedAt or now
        if self._stage_started_at is None:
            self._stage_started_at = now

    def mark_stage_complete(self, stage: str) -> None:
        now = _utc_now_iso()
        started = self._stage_started_at or self.updatedAt or now
        started_dt = _parse_iso(started)
        ended_dt = _parse_iso(now)
        duration_ms = 0.0
        if started_dt and ended_dt:
            duration_ms = max(0.0, (ended_dt - started_dt).total_seconds() * 1000)
        self.stageTimings.append(
            {
                "stage": stage,
                "startedAt": started,
                "endedAt": now,
                "durationMs": round(duration_ms, 3),
                "status": "completed",
            }
        )
        self._stage_started_at = now
        if stage not in self.completedStages:
            self.completedStages.append(stage)
        self.failedStage = None

    def mark_failed(self, stage: str) -> None:
        self.failedStage = stage


@dataclass
class GenerationCheckpoint:
    version: str = CHECKPOINT_VERSION
    generationId: str = ""
    completedStages: list[str] = field(default_factory=list)
    stageTimings: list[dict[str, Any]] = field(default_factory=list)
    failedStage: str | None = None
    inputsHash: str | None = None
    awaitingGate: str | None = None
    generationStrategy: str | None = None
    humanReviewMode: bool = True
    updatedAt: str = field(default_factory=_utc_now_iso)
    _stage_started_at: str | None = field(default=None, repr=False)
    _open_human_gate: str | None = field(default=None, repr=False)
    _open_human_gate_started_at: str | None = field(default=None, repr=False)
    _material_slot_breakdown: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @classmethod
    def load(cls, path: Path) -> GenerationCheckpoint:
        if not path.is_file():
            return cls()
        data = _read_json(path)
        if not isinstance(data, dict):
            return cls()
        return cls(
            version=str(data.get("version", CHECKPOINT_VERSION)),
            generationId=str(data.get("generationId", "")),
            completedStages=list(data.get("completedStages", [])),
            stageTimings=[
                item for item in (data.get("stageTimings") or []) if isinstance(item, dict)
            ],
            failedStage=data.get("failedStage"),
            inputsHash=data.get("inputsHash"),
            awaitingGate=data.get("awaitingGate"),
            generationStrategy=data.get("generationStrategy"),
            humanReviewMode=bool(data.get("humanReviewMode", True)),
            updatedAt=str(data.get("updatedAt", _utc_now_iso())),
            _stage_started_at=data.get("_stageStartedAt"),
            _open_human_gate=data.get("_openHumanGate"),
            _open_human_gate_started_at=data.get("_openHumanGateStartedAt"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updatedAt = _utc_now_iso()
        payload = asdict(self)
        payload.pop("_stage_started_at", None)
        payload.pop("_open_human_gate", None)
        payload.pop("_open_human_gate_started_at", None)
        payload.pop("_material_slot_breakdown", None)
        if self._stage_started_at:
            payload["_stageStartedAt"] = self._stage_started_at
        if self._open_human_gate:
            payload["_openHumanGate"] = self._open_human_gate
        if self._open_human_gate_started_at:
            payload["_openHumanGateStartedAt"] = self._open_human_gate_started_at
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_human_gate(self, stage: str) -> None:
        now = _utc_now_iso()
        self._open_human_gate = stage
        self._open_human_gate_started_at = now
        self.stageTimings.append(
            {
                "stage": stage,
                "startedAt": now,
                "endedAt": None,
                "durationMs": 0.0,
                "status": "paused",
                "kind": "human_gate",
            }
        )

    def close_human_gate(self, stage: str | None = None) -> None:
        target = stage or self._open_human_gate
        if not target:
            return
        now = _utc_now_iso()
        for entry in reversed(self.stageTimings):
            if entry.get("stage") != target:
                continue
            if entry.get("endedAt") is not None:
                continue
            started = str(entry.get("startedAt") or self._open_human_gate_started_at or now)
            started_dt = _parse_iso(started)
            ended_dt = _parse_iso(now)
            duration_ms = 0.0
            if started_dt and ended_dt:
                duration_ms = max(0.0, (ended_dt - started_dt).total_seconds() * 1000)
            entry["endedAt"] = now
            entry["durationMs"] = round(duration_ms, 3)
            entry["status"] = "paused"
            entry["kind"] = "human_gate"
            break
        if self._open_human_gate == target:
            self._open_human_gate = None
            self._open_human_gate_started_at = None
        self._stage_started_at = now
        if target not in self.completedStages:
            self.completedStages.append(target)

    def record_material_slot_duration(self, slot_id: str, duration_ms: float) -> None:
        if not slot_id:
            return
        self._material_slot_breakdown.append(
            {"slotId": slot_id, "durationMs": round(max(0.0, duration_ms), 3)}
        )

    def begin_stage(self, stage: str) -> None:
        now = _utc_now_iso()
        if self._stage_started_at is None and not self.stageTimings:
            self._stage_started_at = self.updatedAt or now
        if self._stage_started_at is None:
            self._stage_started_at = now

    def mark_stage_complete(self, stage: str) -> None:
        if stage in HUMAN_GATE_STAGES:
            self.open_human_gate(stage)
            return

        now = _utc_now_iso()
        started = self._stage_started_at or self.updatedAt or now
        started_dt = _parse_iso(started)
        ended_dt = _parse_iso(now)
        duration_ms = 0.0
        if started_dt and ended_dt:
            duration_ms = max(0.0, (ended_dt - started_dt).total_seconds() * 1000)

        entry: dict[str, Any] = {
            "stage": stage,
            "startedAt": started,
            "endedAt": now,
            "durationMs": round(duration_ms, 3),
            "status": "completed",
        }
        if stage == "generating_material" and self._material_slot_breakdown:
            entry["breakdown"] = list(self._material_slot_breakdown)
            self._material_slot_breakdown = []
        self.stageTimings.append(entry)
        self._stage_started_at = now

        if stage not in self.completedStages:
            self.completedStages.append(stage)
        self.failedStage = None

    def mark_failed(self, stage: str) -> None:
        self.failedStage = stage


def analysis_artifact_root(project_root: Path, sample_id: str) -> Path:
    return project_root / "samples" / sample_id / "analysis"


def generation_artifact_root(project_root: Path, generation_id: str) -> Path:
    return project_root / "generations" / generation_id


def is_analysis_stage_done(stage: str, analysis_root: Path, *, metadata: dict[str, Any] | None = None) -> bool:
    if stage == "downloading":
        video = _read_json(analysis_root / "metadata.json")
        if video is not None:
            return True
        for name in ("original.mp4", "source.mp4"):
            candidate = analysis_root.parent / name
            if candidate.is_file() and candidate.stat().st_size > 0:
                return True
        checkpoint = AnalysisCheckpoint.load(analysis_root / "checkpoint.json")
        if checkpoint.videoPath and Path(checkpoint.videoPath).is_file():
            return True
        return False

    if stage == "extracting_poster":
        poster = analysis_root.parent / "poster.jpg"
        return poster.is_file() and poster.stat().st_size > 0

    if stage == "extracting_metadata":
        data = _read_json(analysis_root / "metadata.json")
        return isinstance(data, dict) and "durationSec" in data

    if stage == "extracting_audio":
        meta = metadata if metadata is not None else _read_json(analysis_root / "metadata.json")
        if isinstance(meta, dict) and not meta.get("hasAudio"):
            return True
        audio = analysis_root / "audio.wav"
        return audio.is_file() and audio.stat().st_size > 0

    if stage == "transcribing":
        data = _read_json(analysis_root / "transcript.json")
        return isinstance(data, dict) and "segments" in data

    if stage == "analyzing_audio":
        meta = metadata if metadata is not None else _read_json(analysis_root / "metadata.json")
        if isinstance(meta, dict) and not meta.get("hasAudio"):
            return True
        data = _read_json(analysis_root / "audio-profile.json")
        return isinstance(data, dict) and "metrics" in data

    if stage == "detecting_shots":
        data = _read_json(analysis_root / "shots.json")
        return isinstance(data, list)

    if stage == "extracting_keyframes":
        data = _read_json(analysis_root / "keyframes.json")
        keyframes_dir = analysis_root / "keyframes"
        return isinstance(data, list) and keyframes_dir.is_dir()

    if stage == "extracting_visual_facts":
        from app.perception.visual_facts_progress import is_visual_facts_stage_complete

        if is_visual_facts_stage_complete(analysis_root):
            return True
        data = _read_json(analysis_root / "sample-analysis.json")
        if isinstance(data, dict) and data.get("keyframeBatchDigests"):
            return True
        keyframes = _read_json(analysis_root / "keyframes.json")
        return isinstance(keyframes, list) and len(keyframes) <= 8

    if stage == "consolidating":
        data = _read_json(analysis_root / "sample-analysis.json")
        return isinstance(data, dict) and "metadata" in data

    if stage == "extracting_structure_direct":
        data = _read_json(analysis_root / "video-structure.json")
        if not isinstance(data, dict) or "slots" not in data:
            return False
        quality = data.get("analysisQuality")
        if not isinstance(quality, dict):
            return False
        warnings = list(quality.get("warnings") or [])
        return "analysis_route:direct_multimodal" in warnings

    if stage == "extracting_structure":
        data = _read_json(analysis_root / "video-structure.json")
        if not isinstance(data, dict) or "slots" not in data:
            return False
        quality = data.get("analysisQuality")
        return isinstance(quality, dict) and "warnings" in quality

    if stage == "proposing_segments":
        proposal = _read_json(analysis_root / "segment-proposal.json")
        return isinstance(proposal, dict) and bool(proposal.get("segments"))

    if stage == "analyzing_segments":
        analyses = _read_json(analysis_root / "segment-analyses.json")
        return isinstance(analyses, list) and len(analyses) > 0

    if stage == "compiling_structure":
        data = _read_json(analysis_root / "video-structure.json")
        return isinstance(data, dict) and bool(data.get("slots"))

    if stage == "critiquing_structure":
        data = _read_json(analysis_root / "video-structure.json")
        if not isinstance(data, dict):
            return False
        quality = data.get("analysisQuality")
        return isinstance(quality, dict) and "warnings" in quality

    if stage == "rendering_knowledge_draft":
        sample_id = analysis_root.parent.name
        project_root = analysis_root.parent.parent
        skill_path = project_root / "knowledge" / "drafts" / sample_id / "structure-skill.md"
        return skill_path.is_file()

    return False


def should_skip_analysis_stage(
    stage: str,
    checkpoint: AnalysisCheckpoint,
    analysis_root: Path,
    *,
    resume: bool,
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not resume:
        return False
    if stage not in checkpoint.completedStages:
        return False
    if checkpoint.analysisRoute == "direct_multimodal" and stage in {
        "extracting_visual_facts",
        "extracting_structure",
        "proposing_segments",
        "analyzing_segments",
        "compiling_structure",
        "critiquing_structure",
    }:
        return True
    if checkpoint.analysisRoute == "map_reduce" and stage == "extracting_structure_direct":
        return True
    if stage == "extracting_visual_facts":
        from app.perception.visual_facts_progress import has_pending_visual_facts_batches

        if has_pending_visual_facts_batches(analysis_root):
            return False
    return is_analysis_stage_done(stage, analysis_root, metadata=metadata)


def is_generation_stage_done(stage: str, generation_root: Path, *, render_root: Path | None = None) -> bool:
    if stage == "analyzing_assets":
        data = _read_json(generation_root / "asset-inventory.json")
        return isinstance(data, dict) and "assets" in data

    if stage == "mapping_slots":
        data = _read_json(generation_root / "slot-matches.json")
        return isinstance(data, dict) and "slotMatches" in data

    if stage == "drafting_master_script":
        draft = _read_json(generation_root / "script-draft.json")
        return (
            isinstance(draft, dict)
            and str(draft.get("masterNarration") or "").strip() != ""
        )

    if stage == "narration_preview":
        from app.pipelines.narration_scene_timing import narration_preview_is_current

        draft = _read_json(generation_root / "script-draft.json")
        structure = _read_json(generation_root / "structure-scaled.json")
        if not isinstance(draft, dict):
            return False
        return narration_preview_is_current(
            generation_root,
            draft,
            structure=structure if isinstance(structure, dict) else None,
            generation_id=str(draft.get("generationId") or generation_root.name),
        )

    if stage == "drafting_storyboard":
        draft = _read_json(generation_root / "script-draft.json")
        storyboard = draft.get("storyboard") if isinstance(draft, dict) else None
        return isinstance(storyboard, list) and len(storyboard) > 0

    if stage == "synthesizing_canonical_narration":
        from app.pipelines.narration_scene_timing import (
            load_narration_timing,
            narration_timing_is_current,
        )

        draft = _read_json(generation_root / "script-draft.json")
        structure = _read_json(generation_root / "structure-scaled.json")
        if not isinstance(draft, dict):
            return False
        timing = load_narration_timing(generation_root)
        if timing is None or timing.get("role") != "canonical":
            return False
        return narration_timing_is_current(
            generation_root,
            draft,
            structure=structure if isinstance(structure, dict) else None,
            generation_id=str(draft.get("generationId") or generation_root.name),
        )

    if stage == "adapting_narration_density":
        drift_path = generation_root / "narration" / "drift-report.json"
        if not drift_path.is_file():
            return False
        payload = _read_json(drift_path)
        return isinstance(payload, dict) and "slots" in payload

    if stage == "planning_completion":
        gap = _read_json(generation_root / "gap-report.json")
        plan = _read_json(generation_root / "generation-plan.json")
        return isinstance(gap, dict) and isinstance(plan, dict) and "timeline" in plan

    if stage == "generating_material":
        state = _read_json(generation_root / "material-state.json")
        return isinstance(state, dict) and "completedActionIds" in state

    if stage == "assembling_final":
        from app.pipelines.tts_mode import MASTER_TTS_WAV_NAME

        master_wav = generation_root / "generated" / MASTER_TTS_WAV_NAME
        return master_wav.is_file() and master_wav.stat().st_size > 0

    if stage == "building_timeline":
        plan = _read_json(generation_root / "generation-plan.json")
        timeline = plan.get("timeline") if isinstance(plan, dict) else None
        return isinstance(timeline, dict) and bool(timeline.get("tracks"))

    if stage == "rendering":
        root = render_root or generation_root.parent.parent / "renders"
        render_dir = root / generation_root.name if render_root is None else render_root
        output_mp4 = render_dir / "output.mp4"
        return output_mp4.is_file() and output_mp4.stat().st_size > 0

    return False


def should_skip_generation_stage(
    stage: str,
    checkpoint: GenerationCheckpoint,
    generation_root: Path,
    *,
    resume: bool,
    render_root: Path | None = None,
) -> bool:
    if not resume:
        return False
    if stage not in checkpoint.completedStages:
        return False
    return is_generation_stage_done(stage, generation_root, render_root=render_root)


def should_skip_mapping_slots_resumable(
    checkpoint: GenerationCheckpoint,
    generation_root: Path,
    *,
    resume: bool,
) -> bool:
    if not should_skip_generation_stage("mapping_slots", checkpoint, generation_root, resume=resume):
        return False
    return (
        (generation_root / "gap-report.json").is_file()
        and (generation_root / "slot-matches.json").is_file()
    )


def should_skip_planning_completion_resumable(
    checkpoint: GenerationCheckpoint,
    generation_root: Path,
    *,
    resume: bool,
) -> bool:
    if not should_skip_generation_stage(
        "planning_completion",
        checkpoint,
        generation_root,
        resume=resume,
    ):
        return False
    if not (
        (generation_root / "gap-report.json").is_file()
        and (generation_root / "generation-plan.json").is_file()
    ):
        return False
    from app.pipelines.narration_scene_timing import (
        load_narration_timing,
        narration_timing_is_current,
    )

    draft = _read_json(generation_root / "script-draft.json")
    structure = _read_json(generation_root / "structure-scaled.json")
    if not isinstance(draft, dict):
        return False
    timing = load_narration_timing(generation_root)
    if timing is None or timing.get("role") != "canonical":
        return False
    return narration_timing_is_current(
        generation_root,
        draft,
        structure=structure if isinstance(structure, dict) else None,
        generation_id=str(draft.get("generationId") or generation_root.name),
    )
