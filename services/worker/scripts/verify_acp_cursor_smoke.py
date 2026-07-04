"""Verify Cursor ACP material author produces a real material-spec.json (not pipeline fallback).

Preflight: acp/mcp imports + Cursor agent binary.
Author: one benefit-card slot via ACP + MCP write_material_spec.
Pass: material-spec.json exists and is not the empty-params legacy fallback scaffold.

Usage (from repo root or services/worker):

    cd services/worker
    $env:VIDEOMAKER_COMPOSITION_ACP_AGENT = "cursor"
    python scripts/verify_acp_cursor_smoke.py

Optional:
    VIDEOMAKER_ACP_SMOKE_SIMPLE=false   # full author workflow (slower)
    VIDEOMAKER_ACP_SMOKE_DURATION_SEC=6
    VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS=1   # serial slots (smoke default path)
    VIDEOMAKER_MAX_CONCURRENT_GENERATIONS=2      # API queue cap (when run via run-dev)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
WORKER = REPO / "services" / "worker"
for part in (WORKER, REPO / "services" / "composition", REPO / "services" / "shared"):
    part_str = str(part)
    if part_str not in sys.path:
        sys.path.insert(0, part_str)


def looks_like_pipeline_fallback(spec: dict[str, Any]) -> bool:
    """Match build_author_fallback_spec / fallback_legacy_spec shapes used on author failure."""
    template = str(spec.get("template", "")).strip()
    params = spec.get("params") if isinstance(spec.get("params"), dict) else {}

    if template == "composition":
        composition = spec.get("composition")
        if isinstance(composition, dict) and str(composition.get("bodyHtml", "")).strip():
            return False
        return True

    if template == "ken-burns":
        refs = params.get("assetRefs")
        return not (isinstance(refs, list) and len(refs) > 0)

    if not params:
        return True

    title = str(params.get("title", "")).strip()
    bullets = params.get("bullets") if isinstance(params.get("bullets"), list) else []
    if title == "VideoMaker" and not bullets:
        return True

    return False


def preflight() -> dict[str, Any]:
    checks: dict[str, Any] = {"ok": True, "errors": []}

    try:
        import acp  # noqa: F401
        import mcp  # noqa: F401
    except ImportError as exc:
        checks["ok"] = False
        checks["errors"].append(f"missing_acp_deps: {exc}")
        return checks

    cursor_bin = os.getenv("VIDEOMAKER_CURSOR_AGENT_BIN", "").strip()
    if cursor_bin:
        agent_path = Path(cursor_bin)
    else:
        local_app = os.getenv("LOCALAPPDATA", "")
        agent_path = Path(local_app) / "cursor-agent" / "agent.cmd" if local_app else Path()
    checks["cursorAgentPath"] = str(agent_path)
    if not agent_path.is_file():
        checks["ok"] = False
        checks["errors"].append(f"cursor_agent_missing: {agent_path}")

    return checks


def main() -> int:
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND", "acp")
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_ACP_AGENT", "cursor")
    os.environ.setdefault("VIDEOMAKER_ACP_SMOKE_SIMPLE", "true")
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE", "true")

    pre = preflight()
    if not pre["ok"]:
        print(json.dumps({"ok": False, "stage": "preflight", **pre}, ensure_ascii=False, indent=2))
        return 1

    from app.composition.acp.author import author_material_spec_via_acp, resolve_acp_agent_label
    from app.composition.acp.trace import AcpAuthorTraceRecorder
    from composition.types import AuthorRequest

    duration_sec = float(os.environ.get("VIDEOMAKER_ACP_SMOKE_DURATION_SEC", "6"))
    storage_root = REPO / "services" / "api" / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    run_suffix = str(int(time.time()))
    project_id = "composition-acp-smoke"
    generation_id = f"verify-cursor-{run_suffix}"
    scratch = storage_root / "smoke" / "acp-author" / f"verify-cursor-{run_suffix}"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id=project_id,
        acp_agent=resolve_acp_agent_label(),
        task_id=f"verify-cursor-{run_suffix}",
        generation_id=generation_id,
    )

    slot = {
        "role": "benefit_card",
        "scriptIntent": "展示三大核心卖点：轻量、续航、画质；允许短标题与要点列表",
        "visualIntent": "竖屏卡片动效，品牌蓝主色，禁止占位文案 VideoMaker",
    }

    author_started = time.perf_counter()
    error: str | None = None
    spec: dict[str, Any] | None = None
    try:
        spec = author_material_spec_via_acp(
            AuthorRequest(
                project_id=project_id,
                slot=slot,
                aspect_ratio="9:16",
                brand_colors={"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
                task_id=f"verify-cursor-{run_suffix}",
                generation_id=generation_id,
                slot_timing={
                    "startSec": 0.0,
                    "endSec": duration_sec,
                    "durationSec": duration_sec,
                },
            ),
            repo_root=REPO,
            scratch_dir=scratch,
            trace=trace,
        )
    except Exception as exc:
        error = str(exc)

    author_sec = round(time.perf_counter() - author_started, 2)
    spec_path = scratch / "material-spec.json"
    spec_on_disk = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.is_file() else None
    resolved_spec = spec if isinstance(spec, dict) else spec_on_disk

    is_fallback = looks_like_pipeline_fallback(resolved_spec) if isinstance(resolved_spec, dict) else True
    passed = error is None and spec_path.is_file() and isinstance(resolved_spec, dict) and not is_fallback

    payload = {
        "ok": passed,
        "stage": "author",
        "acpAgent": resolve_acp_agent_label(),
        "authorSec": author_sec,
        "materialSpecPath": str(spec_path),
        "materialSpecExists": spec_path.is_file(),
        "isPipelineFallback": is_fallback,
        "template": resolved_spec.get("template") if isinstance(resolved_spec, dict) else None,
        "paramsKeys": sorted(resolved_spec.get("params", {}).keys())
        if isinstance(resolved_spec, dict) and isinstance(resolved_spec.get("params"), dict)
        else [],
        "acpTraceDir": str(trace.trace_dir),
        "scratchDir": str(scratch),
        "error": error,
        "specPreview": resolved_spec if isinstance(resolved_spec, dict) else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
