from __future__ import annotations

import json
import re
import shutil
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from app.pipelines.scene_timing import normalize_scene_start_end
from app.providers.base_media_resolver import is_finish_action

MaterialEditMode = Literal["edit", "full"]

VISUAL_MATERIAL_PROVIDERS = frozenset(
    {
        "asset_reuse",
        "stock_media_search",
        "image_generation",
        "video_generation",
        "hyperframes_material",
    }
)

ARCHIVE_DIR_NAME = "revise-material-archive"
MATERIAL_SPEC_FILENAME = "material-spec.json"

_CENTER_KEYWORDS = ("居中", "中心", "中部", "核心区域", "center", "centre", "middle")

NARRATION_PREVIEW_FILENAME = "narration-preview.json"
GENERATION_PLAN_FILENAME = "generation-plan.json"
_ROOT_DURATION_RE = re.compile(r'data-duration="([0-9.]+)"', re.IGNORECASE)
_ROOT_INNER_HTML_RE = re.compile(
    r'id="root"[^>]*>\s*(.*?)\s*</div>\s*<script>',
    re.DOTALL | re.IGNORECASE,
)
_STYLE_BLOCK_RE = re.compile(r"<style>(.*?)</style>", re.DOTALL | re.IGNORECASE)



class SlotChainKind(str, Enum):
    HF_ONLY = "hf_only"
    STOCK_THEN_HF = "stock_then_hf"
    REUSE_THEN_HF = "reuse_then_hf"
    IMAGE_ONLY = "image_only"
    VIDEO_ONLY = "video_only"
    IMAGE_THEN_HF = "image_then_hf"
    STOCK_ONLY = "stock_only"
    UNKNOWN = "unknown"


def actions_for_slot(actions: list[dict[str, Any]], slot_id: str) -> list[dict[str, Any]]:
    return [
        action
        for action in actions
        if isinstance(action, dict) and str(action.get("slotId") or "") == slot_id
    ]


def is_terminal_hf_action(action: dict[str, Any]) -> bool:
    provider = str(action.get("provider") or action.get("strategy") or "")
    action_id = str(action.get("id") or "")
    if provider == "hyperframes_material":
        return True
    return is_finish_action(action_id)


def classify_slot_material_chain(actions: list[dict[str, Any]], slot_id: str) -> SlotChainKind:
    slot_actions = actions_for_slot(actions, slot_id)
    if not slot_actions:
        return SlotChainKind.UNKNOWN

    providers = [
        str(action.get("provider") or action.get("strategy") or "") for action in slot_actions
    ]
    has_hf = any(is_terminal_hf_action(action) for action in slot_actions)
    has_stock = "stock_media_search" in providers
    has_reuse = "asset_reuse" in providers
    has_image = "image_generation" in providers
    has_video = "video_generation" in providers

    if has_stock and has_hf:
        return SlotChainKind.STOCK_THEN_HF
    if has_reuse and has_hf:
        return SlotChainKind.REUSE_THEN_HF
    if has_image and has_hf:
        return SlotChainKind.IMAGE_THEN_HF
    if has_stock and not has_hf:
        return SlotChainKind.STOCK_ONLY
    if has_image and not has_hf:
        return SlotChainKind.IMAGE_ONLY
    if has_video and not has_hf:
        return SlotChainKind.VIDEO_ONLY
    if has_hf:
        return SlotChainKind.HF_ONLY
    return SlotChainKind.UNKNOWN


def should_degrade_edit_to_full(chain_kind: SlotChainKind) -> bool:
    return chain_kind in {
        SlotChainKind.IMAGE_ONLY,
        SlotChainKind.VIDEO_ONLY,
        SlotChainKind.STOCK_ONLY,
    }


def resolve_effective_material_edit_mode(
    mode: str,
    chain_kind: SlotChainKind,
) -> MaterialEditMode:
    if mode == "full":
        return "full"
    if should_degrade_edit_to_full(chain_kind):
        return "full"
    return "edit"


def resolve_preserve_action_ids(
    actions: list[dict[str, Any]],
    slot_id: str,
    mode: str,
) -> set[str]:
    chain_kind = classify_slot_material_chain(actions, slot_id)
    effective = resolve_effective_material_edit_mode(mode, chain_kind)
    if effective == "full":
        return set()

    preserve: set[str] = set()
    for action in actions_for_slot(actions, slot_id):
        provider = str(action.get("provider") or action.get("strategy") or "")
        if provider not in VISUAL_MATERIAL_PROVIDERS:
            continue
        if is_terminal_hf_action(action):
            continue
        action_id = str(action.get("id") or "")
        if action_id:
            preserve.add(action_id)
    return preserve


def clear_stock_search_query_for_slot(actions: list[dict[str, Any]], slot_id: str) -> None:
    for action in actions_for_slot(actions, slot_id):
        provider = str(action.get("provider") or action.get("strategy") or "")
        if provider == "stock_media_search":
            action.pop("stockSearchQuery", None)


def find_hf_action_for_slot(
    actions: list[dict[str, Any]],
    slot_id: str,
) -> dict[str, Any] | None:
    slot_actions = actions_for_slot(actions, slot_id)
    for action in slot_actions:
        if is_finish_action(str(action.get("id") or "")):
            return action
    for action in slot_actions:
        if str(action.get("provider") or action.get("strategy") or "") == "hyperframes_material":
            return action
    return None


def archive_dir_for_slot(generation_root: Path, slot_id: str) -> Path:
    return generation_root / ARCHIVE_DIR_NAME / slot_id


def persist_material_spec_after_render(
    *,
    spec: dict[str, Any],
    generated_root: Path,
    action_id: str,
) -> Path:
    target = generated_root / action_id / MATERIAL_SPEC_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _copy_file_if_exists(source: Path, dest: Path) -> bool:
    if not source.is_file() or source.stat().st_size <= 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return True


def load_narration_preview_timing(generation_root: Path, slot_id: str) -> dict[str, float] | None:
    preview_path = generation_root / NARRATION_PREVIEW_FILENAME
    if not preview_path.is_file():
        return None
    try:
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(preview, dict):
        return None
    scene_timing = preview.get("sceneTiming")
    if not isinstance(scene_timing, list):
        return None
    for entry in scene_timing:
        if not isinstance(entry, dict) or str(entry.get("slotId") or "") != slot_id:
            continue
        start, end, duration = normalize_scene_start_end(
            float(entry.get("startSec", 0.0)),
            float(entry.get("endSec", 0.0)),
        )
        return {"startSec": start, "endSec": end, "durationSec": duration}
    return None


def normalize_plan_storyboard_timing(
    plan: dict[str, Any],
    slot_ids: set[str] | None = None,
) -> None:
    storyboard = plan.get("storyboard")
    if not isinstance(storyboard, list):
        return
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId") or "")
        if slot_ids is not None and slot_id not in slot_ids:
            continue
        if "startSec" not in scene or "endSec" not in scene:
            continue
        start, end, _duration = normalize_scene_start_end(
            float(scene.get("startSec", 0.0)),
            float(scene.get("endSec", 0.0)),
        )
        scene["startSec"] = start
        scene["endSec"] = end


def apply_narration_preview_to_storyboard(
    generation_root: Path,
    plan: dict[str, Any],
    slot_ids: set[str],
) -> None:
    storyboard = plan.get("storyboard")
    if not isinstance(storyboard, list) or not slot_ids:
        return
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId") or "")
        if slot_id not in slot_ids:
            continue
        timing = load_narration_preview_timing(generation_root, slot_id)
        if timing is None:
            continue
        scene["startSec"] = timing["startSec"]
        scene["endSec"] = timing["endSec"]


def load_generation_plan(generation_root: Path) -> dict[str, Any] | None:
    plan_path = generation_root / GENERATION_PLAN_FILENAME
    if not plan_path.is_file():
        return None
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def resolve_slot_timing_from_storyboard(
    storyboard: list[Any],
    slot_id: str,
) -> dict[str, float] | None:
    for scene in storyboard:
        if not isinstance(scene, dict) or str(scene.get("slotId") or "") != slot_id:
            continue
        nested = scene.get("slotTiming")
        if isinstance(nested, dict):
            duration_raw = nested.get("durationSec")
            if isinstance(duration_raw, (int, float)) and float(duration_raw) > 0:
                start_raw = nested.get("startSec", scene.get("startSec", 0.0))
                end_raw = nested.get("endSec", scene.get("endSec", 0.0))
                start, end, duration = normalize_scene_start_end(
                    float(start_raw or 0.0),
                    float(end_raw if end_raw is not None else float(start_raw or 0.0) + float(duration_raw)),
                )
                return {"startSec": start, "endSec": end, "durationSec": duration}
        if "startSec" in scene or "endSec" in scene:
            start, end, duration = normalize_scene_start_end(
                float(scene.get("startSec", 0.0)),
                float(scene.get("endSec", 0.0)),
            )
            return {"startSec": start, "endSec": end, "durationSec": duration}
    return None


def resolve_slot_timing_from_generation_plan(
    generation_root: Path,
    slot_id: str,
) -> dict[str, float] | None:
    plan = load_generation_plan(generation_root)
    if not isinstance(plan, dict):
        return None
    storyboard = plan.get("storyboard")
    if not isinstance(storyboard, list):
        return None
    return resolve_slot_timing_from_storyboard(storyboard, slot_id)


def resolve_slot_timing_for_material_author(
    generation_root: Path,
    slot_id: str,
    *,
    storyboard_fallback: list[Any] | None = None,
    existing_spec: dict[str, Any] | None = None,
    finish_brief: dict[str, Any] | None = None,
) -> dict[str, float]:
    timing = resolve_slot_timing_from_generation_plan(generation_root, slot_id)
    if timing is None:
        preview_timing = load_narration_preview_timing(generation_root, slot_id)
        if preview_timing is not None:
            timing = preview_timing
    if timing is None and storyboard_fallback:
        timing = resolve_slot_timing_from_storyboard(storyboard_fallback, slot_id)
    if timing is None:
        timing = {"startSec": 0.0, "endSec": 4.0, "durationSec": 4.0}

    prefer_duration: float | None = None
    if isinstance(existing_spec, dict) and existing_spec.get("durationSec") is not None:
        prefer_duration = float(existing_spec["durationSec"])
    elif isinstance(finish_brief, dict) and finish_brief.get("durationSec") is not None:
        prefer_duration = float(finish_brief["durationSec"])

    if prefer_duration is not None and prefer_duration > timing["durationSec"]:
        timing = dict(timing)
        timing["durationSec"] = round(max(0.5, prefer_duration), 3)
        timing["endSec"] = round(timing["startSec"] + timing["durationSec"], 3)
    return timing


def resolve_slot_timing_for_revise(
    generation_root: Path,
    storyboard: list[Any],
    slot_id: str,
    *,
    existing_spec: dict[str, Any] | None = None,
    finish_brief: dict[str, Any] | None = None,
) -> dict[str, float]:
    return resolve_slot_timing_for_material_author(
        generation_root,
        slot_id,
        storyboard_fallback=storyboard,
        existing_spec=existing_spec,
        finish_brief=finish_brief,
    )


def _load_json_spec(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def reconstruct_spec_from_composition_dir(
    composition_dir: Path,
    *,
    duration_sec: float | None = None,
) -> dict[str, Any] | None:
    index_path = composition_dir / "index.html"
    if not index_path.is_file():
        return None
    try:
        html = index_path.read_text(encoding="utf-8")
    except OSError:
        return None
    resolved_duration = duration_sec
    if resolved_duration is None:
        duration_match = _ROOT_DURATION_RE.search(html)
        if not duration_match:
            return None
        resolved_duration = max(0.5, float(duration_match.group(1)))
    body_match = _ROOT_INNER_HTML_RE.search(html)
    body_html = body_match.group(1).strip() if body_match else ""
    style_match = _STYLE_BLOCK_RE.search(html)
    styles = style_match.group(1).strip() if style_match else ""
    if not body_html:
        return None
    composition: dict[str, Any] = {"bodyHtml": body_html}
    if styles:
        composition["styles"] = styles
    return {
        "template": "composition",
        "durationSec": round(max(0.5, float(resolved_duration)), 3),
        "composition": composition,
    }


def discover_material_spec_for_slot(
    *,
    generation_root: Path,
    generated_root: Path,
    slot_id: str,
    hf_action_id: str | None,
) -> dict[str, Any] | None:
    preview_duration = load_narration_preview_timing(generation_root, slot_id)
    preferred_duration = preview_duration["durationSec"] if preview_duration else None

    if hf_action_id:
        spec = _load_json_spec(generated_root / hf_action_id / MATERIAL_SPEC_FILENAME)
        if spec is not None:
            if preferred_duration is not None and float(spec.get("durationSec") or 0) < preferred_duration:
                spec = dict(spec)
                spec["durationSec"] = preferred_duration
            return spec
    spec = _load_json_spec(generation_root / "acp-author" / slot_id / MATERIAL_SPEC_FILENAME)
    if spec is not None:
        if preferred_duration is not None and float(spec.get("durationSec") or 0) < preferred_duration:
            spec = dict(spec)
            spec["durationSec"] = preferred_duration
        return spec
    if hf_action_id:
        return reconstruct_spec_from_composition_dir(
            generated_root / hf_action_id / "composition",
            duration_sec=preferred_duration,
        )
    return None


def _rewrite_generation_id_in_value(value: Any, old_id: str, new_id: str) -> Any:
    if isinstance(value, str):
        updated = value.replace(f"/generations/{old_id}/", f"/generations/{new_id}/")
        if value == old_id:
            return new_id
        return updated
    if isinstance(value, dict):
        return {key: _rewrite_generation_id_in_value(item, old_id, new_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_generation_id_in_value(item, old_id, new_id) for item in value]
    return value


def rebind_plan_to_generation(
    plan: dict[str, Any],
    *,
    source_generation_id: str,
    target_generation_id: str,
) -> dict[str, Any]:
    if source_generation_id == target_generation_id:
        rebound = dict(plan)
        rebound["id"] = target_generation_id
        return rebound
    rebound = _rewrite_generation_id_in_value(plan, source_generation_id, target_generation_id)
    if not isinstance(rebound, dict):
        rebound = dict(plan)
    rebound["id"] = target_generation_id
    return rebound


def resolve_spec_duration_sec(
    spec: dict[str, Any],
    fallback_duration_sec: float,
    *,
    prefer_duration_sec: float | None = None,
) -> float:
    spec_duration = spec.get("durationSec")
    base = float(spec_duration) if spec_duration is not None else float(fallback_duration_sec)
    if prefer_duration_sec is not None:
        base = max(base, float(prefer_duration_sec))
    return round(max(0.5, base), 3)


def archive_slot_material(
    *,
    generation_root: Path,
    generated_root: Path,
    actions: list[dict[str, Any]],
    slot_id: str,
) -> Path | None:
    hf_action = find_hf_action_for_slot(actions, slot_id)
    archive_dir = archive_dir_for_slot(generation_root, slot_id)
    if archive_dir.exists():
        shutil.rmtree(archive_dir, ignore_errors=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_any = False

    if hf_action is not None:
        action_id = str(hf_action.get("id") or "")
        if action_id:
            spec_path = generated_root / action_id / MATERIAL_SPEC_FILENAME
            if spec_path.is_file():
                shutil.copy2(spec_path, archive_dir / MATERIAL_SPEC_FILENAME)
                archived_any = True
            else:
                discovered = discover_material_spec_for_slot(
                    generation_root=generation_root,
                    generated_root=generated_root,
                    slot_id=slot_id,
                    hf_action_id=action_id,
                )
                if discovered is not None:
                    (archive_dir / MATERIAL_SPEC_FILENAME).write_text(
                        json.dumps(discovered, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    archived_any = True
            composition_dir = generated_root / action_id / "composition"
            if composition_dir.is_dir():
                shutil.copytree(composition_dir, archive_dir / "composition", dirs_exist_ok=True)
                archived_any = True

    for filename in (f"{slot_id}-stock.mp4", f"{slot_id}-reuse.mp4"):
        if _copy_file_if_exists(generated_root / filename, archive_dir / filename):
            archived_any = True

    stock_action = next(
        (
            action
            for action in actions_for_slot(actions, slot_id)
            if str(action.get("provider") or action.get("strategy") or "") == "stock_media_search"
        ),
        None,
    )
    if isinstance(stock_action, dict) and stock_action.get("stockAttribution"):
        (archive_dir / "stock-attribution.json").write_text(
            json.dumps(stock_action["stockAttribution"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        archived_any = True

    return archive_dir if archived_any else None


def load_archived_material_spec(generation_root: Path, slot_id: str) -> dict[str, Any] | None:
    spec_path = archive_dir_for_slot(generation_root, slot_id) / MATERIAL_SPEC_FILENAME
    if not spec_path.is_file():
        return None
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def restore_archived_upstream_media(
    *,
    generation_root: Path,
    generated_root: Path,
    slot_id: str,
) -> bool:
    archive_dir = archive_dir_for_slot(generation_root, slot_id)
    restored = False
    for filename in (f"{slot_id}-stock.mp4", f"{slot_id}-reuse.mp4"):
        archived = archive_dir / filename
        target = generated_root / filename
        if not target.is_file() and archived.is_file():
            generated_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archived, target)
            restored = True
    return restored


def _instruction_implies_center(instruction: str) -> bool:
    lower = instruction.lower()
    return any(keyword in instruction or keyword in lower for keyword in _CENTER_KEYWORDS)


def build_edit_finish_brief(
    finish_brief: dict[str, Any] | None,
    *,
    instruction: str,
) -> dict[str, Any]:
    brief = dict(finish_brief) if isinstance(finish_brief, dict) else {}
    trimmed = instruction.strip()
    brief["editInstruction"] = trimmed

    if _instruction_implies_center(trimmed):
        brief["layoutDirective"] = (
            "Place primary overlay content in the vertical and horizontal center of the safe area. "
            "Do not keep lower-third or bottom-aligned placement."
        )
        composition_brief = brief.get("compositionAuthorBrief")
        if isinstance(composition_brief, dict):
            composition_brief = dict(composition_brief)
        else:
            composition_brief = {}
        composition_brief["layoutAnchor"] = "center"
        brief["compositionAuthorBrief"] = composition_brief

    composition_brief = brief.get("compositionAuthorBrief")
    if isinstance(composition_brief, dict):
        composition_brief = dict(composition_brief)
        prompt = str(
            composition_brief.get("authorPrompt") or composition_brief.get("visualGoal") or ""
        ).strip()
        suffix = f"修改要求：{trimmed}"
        composition_brief["authorPrompt"] = f"{prompt}\n{suffix}".strip() if prompt else suffix
        brief["compositionAuthorBrief"] = composition_brief
    elif trimmed:
        brief["compositionAuthorBrief"] = {
            "authorPrompt": f"修改要求：{trimmed}",
        }

    return brief


_MATERIAL_GATE_REVISE_KEY = "materialGateRevise"


def normalize_material_edit_context(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Merge top-level and materialGateRevise nested fields for material author/revise."""
    gate = raw.get(_MATERIAL_GATE_REVISE_KEY)
    gate_dict = gate if isinstance(gate, dict) else {}

    mode = str(raw.get("materialEditMode") or gate_dict.get("materialEditMode") or "").strip()
    if mode not in {"edit", "full"}:
        return None

    normalized: dict[str, Any] = {"materialEditMode": mode}
    instruction = str(
        raw.get("editInstruction") or gate_dict.get("editInstruction") or ""
    ).strip()
    if instruction:
        normalized["editInstruction"] = instruction

    for key in ("slotChainKinds", "affectedSlotIds", "source"):
        value = raw.get(key)
        if value is None:
            value = gate_dict.get(key)
        if value is not None:
            normalized[key] = value

    return normalized


def material_edit_context_applies_to_slot(context: dict[str, Any], slot_id: str) -> bool:
    affected = context.get("affectedSlotIds")
    if not isinstance(affected, list) or not affected:
        return True
    return slot_id in {str(item) for item in affected}


def load_revise_material_edit_context(generation_root: Path) -> dict[str, Any] | None:
    path = generation_root / "revise-context.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return normalize_material_edit_context(payload)


def material_edit_mode_for_slot(context: dict[str, Any], slot_id: str) -> MaterialEditMode:
    mode = str(context.get("materialEditMode") or "full")
    chain_kinds = context.get("slotChainKinds")
    chain_kind = SlotChainKind.UNKNOWN
    if isinstance(chain_kinds, dict):
        raw = chain_kinds.get(slot_id)
        if raw:
            try:
                chain_kind = SlotChainKind(str(raw))
            except ValueError:
                chain_kind = SlotChainKind.UNKNOWN
    return resolve_effective_material_edit_mode(mode, chain_kind)


def edit_instruction_from_context(context: dict[str, Any]) -> str:
    return str(context.get("editInstruction") or "").strip()


def collect_seed_invalidate_plan(
    *,
    actions: list[dict[str, Any]],
    slot_ids: set[str],
    material_edit_mode: str,
) -> tuple[set[str], dict[str, str]]:
    preserve_ids: set[str] = set()
    chain_kinds: dict[str, str] = {}
    for slot_id in sorted(slot_ids):
        chain_kind = classify_slot_material_chain(actions, slot_id)
        chain_kinds[slot_id] = chain_kind.value
        effective = resolve_effective_material_edit_mode(material_edit_mode, chain_kind)
        if effective == "full":
            clear_stock_search_query_for_slot(actions, slot_id)
        else:
            preserve_ids.update(resolve_preserve_action_ids(actions, slot_id, material_edit_mode))
    return preserve_ids, chain_kinds
