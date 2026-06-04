from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CHECKPOINT_VERSION = "p0-v1"

ANALYSIS_STAGES = (
    "downloading",
    "extracting_metadata",
    "extracting_audio",
    "transcribing",
    "detecting_shots",
    "extracting_keyframes",
    "consolidating",
    "extracting_structure",
    "rendering_knowledge_draft",
)

GENERATION_STAGES = (
    "analyzing_assets",
    "mapping_slots",
    "planning_completion",
    "building_timeline",
    "rendering",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
    failedStage: str | None = None
    videoPath: str | None = None
    updatedAt: str = field(default_factory=_utc_now_iso)

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
            failedStage=data.get("failedStage"),
            videoPath=data.get("videoPath"),
            updatedAt=str(data.get("updatedAt", _utc_now_iso())),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updatedAt = _utc_now_iso()
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_stage_complete(self, stage: str) -> None:
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
    failedStage: str | None = None
    inputsHash: str | None = None
    updatedAt: str = field(default_factory=_utc_now_iso)

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
            failedStage=data.get("failedStage"),
            inputsHash=data.get("inputsHash"),
            updatedAt=str(data.get("updatedAt", _utc_now_iso())),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updatedAt = _utc_now_iso()
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_stage_complete(self, stage: str) -> None:
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

    if stage == "detecting_shots":
        data = _read_json(analysis_root / "shots.json")
        return isinstance(data, list)

    if stage == "extracting_keyframes":
        data = _read_json(analysis_root / "keyframes.json")
        keyframes_dir = analysis_root / "keyframes"
        return isinstance(data, list) and keyframes_dir.is_dir()

    if stage == "consolidating":
        data = _read_json(analysis_root / "sample-analysis.json")
        return isinstance(data, dict) and "metadata" in data

    if stage == "extracting_structure":
        data = _read_json(analysis_root / "video-structure.json")
        return isinstance(data, dict) and "slots" in data

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
    return is_analysis_stage_done(stage, analysis_root, metadata=metadata)


def is_generation_stage_done(stage: str, generation_root: Path, *, render_root: Path | None = None) -> bool:
    if stage == "analyzing_assets":
        data = _read_json(generation_root / "asset-inventory.json")
        return isinstance(data, dict) and "assets" in data

    if stage == "mapping_slots":
        data = _read_json(generation_root / "slot-matches.json")
        return isinstance(data, dict) and "slotMatches" in data

    if stage == "planning_completion":
        gap = _read_json(generation_root / "gap-report.json")
        plan = _read_json(generation_root / "generation-plan.json")
        return isinstance(gap, dict) and isinstance(plan, dict) and "timeline" in plan

    if stage == "building_timeline":
        plan = _read_json(generation_root / "generation-plan.json")
        timeline = plan.get("timeline") if isinstance(plan, dict) else None
        return isinstance(timeline, dict) and bool(timeline.get("tracks"))

    if stage == "rendering":
        root = render_root or generation_root.parent.parent / "renders"
        preview = root / generation_root.name / "preview.html" if render_root is None else render_root / "preview.html"
        return preview.is_file()

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
