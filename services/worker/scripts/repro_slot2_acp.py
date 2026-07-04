"""Reproduce ACP author for generation 21fbf28a slot-2 using on-disk task.json."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKER = REPO / "services" / "worker"
for part in (WORKER, REPO / "services" / "composition", REPO / "services" / "shared"):
    part_str = str(part)
    if part_str not in sys.path:
        sys.path.insert(0, part_str)

os.environ.setdefault("VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND", "acp")
os.environ.setdefault("VIDEOMAKER_COMPOSITION_ACP_AGENT", "cursor")

STORAGE = REPO / "services" / "api" / "storage"
PROJECT = "7bed327a-f272-4887-a294-938d30b98723"
GENERATION = "21fbf28a-b79b-4876-b4d5-e43cbe6f10c4"
SLOT = "slot-2"
SCRATCH = (
    STORAGE
    / "projects"
    / PROJECT
    / "generations"
    / GENERATION
    / "acp-author"
    / SLOT
)


def main() -> int:
    from app.composition.acp.author import author_material_spec_via_acp, resolve_acp_agent_label
    from app.composition.acp.trace import AcpAuthorTraceRecorder
    from composition.author.payload import build_material_author_user_payload
    from composition.types import AuthorRequest

    task_path = SCRATCH / "task.json"
    if not task_path.is_file():
        print(json.dumps({"ok": False, "error": f"missing {task_path}"}, indent=2))
        return 1

    payload = json.loads(task_path.read_text(encoding="utf-8"))
    slot = payload.get("slot") if isinstance(payload.get("slot"), dict) else {}
    request = AuthorRequest(
        project_id=PROJECT,
        slot=slot,
        brand_colors=payload.get("brandColors") if isinstance(payload.get("brandColors"), dict) else {},
        variant_overrides=payload.get("variantOverrides") if isinstance(payload.get("variantOverrides"), dict) else {},
        asset_refs=payload.get("assetRefs"),
        aspect_ratio=str((payload.get("renderTarget") or {}).get("aspectRatio") or "9:16"),
        slot_timing=payload.get("slotTiming") if isinstance(payload.get("slotTiming"), dict) else None,
        visual_style_bible=payload.get("visualStyleBible") if isinstance(payload.get("visualStyleBible"), dict) else None,
        finish_brief=payload.get("finishBrief") if isinstance(payload.get("finishBrief"), dict) else None,
        task_id=str(payload.get("taskId") or "repro-task"),
        generation_id=GENERATION,
        generation_root=Path(str(payload.get("generationRoot") or SCRATCH.parents[2])),
        material_edit_mode=str(payload.get("materialEditMode") or "full"),
        edit_instruction=str(payload.get("editInstruction") or ""),
    )

    trace = AcpAuthorTraceRecorder.create(
        STORAGE,
        project_id=PROJECT,
        acp_agent=resolve_acp_agent_label(),
        task_id=str(payload.get("taskId") or "repro-task"),
        generation_id=GENERATION,
    )
    db_path = STORAGE / "videomaker.sqlite3"
    if db_path.is_file():
        os.environ["VM_DATABASE_PATH"] = str(db_path)
    os.environ["VM_STORAGE_ROOT"] = str(STORAGE)

    started = time.perf_counter()
    try:
        spec = author_material_spec_via_acp(
            request,
            repo_root=REPO,
            storage_root=STORAGE,
            scratch_dir=SCRATCH,
            generated_root=SCRATCH.parents[2] / "generated",
            slot_id=SLOT,
            trace=trace,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "authorSec": round(time.perf_counter() - started, 2),
                    "template": spec.get("template"),
                    "acpTraceDir": str(trace.trace_dir),
                    "specPath": str(SCRATCH / "material-spec.json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        outcome = {}
        outcome_path = trace.trace_dir / "outcome.json"
        if outcome_path.is_file():
            outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "ok": False,
                    "authorSec": round(time.perf_counter() - started, 2),
                    "error": str(exc),
                    "errorType": type(exc).__name__,
                    "acpTraceDir": str(trace.trace_dir),
                    "outcome": outcome,
                    "hasToolCalls": (trace.trace_dir / "tool_calls.jsonl").is_file(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
