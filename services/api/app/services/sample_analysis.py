from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SAMPLE_ANALYSIS_PATH_KEYS = frozenset(
    {
        "metadataPath",
        "audioPath",
        "transcriptPath",
        "shotsPath",
        "keyframesPath",
        "sourcePath",
    }
)
_SLIM_AUDIO_PROFILE_KEYS = frozenset(
    {
        "hasVoiceover",
        "hasBgm",
        "onsetTimes",
        "metrics",
        "avgSpeechRate",
    }
)
_DIGEST_INDEX_KEYS = frozenset({"batchIndex", "startSec", "endSec", "digestRef"})
_INCLUDE_ALIASES = {
    "audioFull": "audioProfile",
    "digestFull": "keyframeBatchDigests",
}


def parse_sample_analysis_include(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    tokens = {part.strip() for part in raw.split(",") if part.strip()}
    expanded = set(tokens)
    for token in tokens:
        alias = _INCLUDE_ALIASES.get(token)
        if alias:
            expanded.add(alias)
    return frozenset(expanded)


def slim_sample_analysis_response(
    payload: dict[str, Any],
    *,
    include: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    result = dict(payload)
    for path_key in _SAMPLE_ANALYSIS_PATH_KEYS:
        result.pop(path_key, None)

    if "audioProfile" in result and "audioProfile" not in include:
        profile = result.get("audioProfile")
        if isinstance(profile, dict):
            result["audioProfile"] = {
                key: profile[key]
                for key in _SLIM_AUDIO_PROFILE_KEYS
                if key in profile
            }

    if "keyframeBatchDigests" in result and "keyframeBatchDigests" not in include:
        digests = result.get("keyframeBatchDigests")
        if isinstance(digests, list):
            slim_digests: list[dict[str, Any]] = []
            for item in digests:
                if not isinstance(item, dict):
                    continue
                entry = {key: item[key] for key in _DIGEST_INDEX_KEYS if key in item}
                if "digestRef" not in entry and "batchIndex" in entry:
                    entry["digestRef"] = (
                        f"batch-digests/batch-{int(entry['batchIndex'])}.json"
                    )
                slim_digests.append(entry)
            result["keyframeBatchDigests"] = slim_digests

    return result


def _expand_batch_digests(
    analysis_root: Path,
    digests: list[Any],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for item in digests:
        if not isinstance(item, dict):
            continue
        batch_index = item.get("batchIndex")
        digest_ref = str(
            item.get("digestRef")
            or (
                f"batch-digests/batch-{int(batch_index)}.json"
                if batch_index is not None
                else ""
            )
        ).strip()
        merged = dict(item)
        if digest_ref:
            merged.setdefault("digestRef", digest_ref)
            full_path = analysis_root / digest_ref
            if full_path.is_file():
                try:
                    body = json.loads(full_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    body = None
                if isinstance(body, dict):
                    merged.update(body)
        expanded.append(merged)
    return expanded


def build_sample_analysis_response(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
    payload: dict[str, Any],
    include: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    analysis_root = (
        storage_root / "projects" / project_id / "samples" / sample_id / "analysis"
    )
    working = dict(payload)
    if "audioProfile" in include:
        full_path = analysis_root / "audio-profile-full.json"
        if full_path.is_file():
            try:
                full_profile = json.loads(full_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                full_profile = None
            if isinstance(full_profile, dict):
                working["audioProfile"] = full_profile

    if "keyframeBatchDigests" in include:
        digests = working.get("keyframeBatchDigests")
        if isinstance(digests, list):
            working["keyframeBatchDigests"] = _expand_batch_digests(analysis_root, digests)

    return slim_sample_analysis_response(working, include=include)


def load_sample_analysis_artifact(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> dict[str, Any] | None:
    path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
        / "sample-analysis.json"
    )
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def load_sample_structure_artifact(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> dict[str, Any] | None:
    path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
        / "video-structure.json"
    )
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


SUPPORTED_STRUCTURE_VERSION = "p1-v3"


def structure_version_conflict_detail(version: str) -> str:
    label = version or "unknown"
    return (
        f"Sample structure version '{label}' is not supported. "
        "Only p1-v3 is readable. Re-analyze manually or run "
        "scripts/migrate-video-structure-v2-to-v3.ps1."
    )
