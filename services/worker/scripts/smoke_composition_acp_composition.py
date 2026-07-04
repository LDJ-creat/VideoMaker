"""Live ACP smoke: full author + composition template (~5s hook visual)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKER = REPO / "services" / "worker"
for part in (WORKER, REPO / "services" / "composition", REPO / "services" / "shared"):
    sys.path.insert(0, str(part))

from app.composition.acp.author import author_material_spec_via_acp, resolve_acp_agent_label
from app.composition.acp.trace import AcpAuthorTraceRecorder
from app.composition.engine_factory import create_composition_engine
from composition.types import AuthorRequest, RenderPaths


def main() -> int:
    agent = os.environ.get("VIDEOMAKER_COMPOSITION_ACP_AGENT", "cursor").strip().lower()
    os.environ["VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND"] = "acp"
    os.environ["VIDEOMAKER_COMPOSITION_ACP_AGENT"] = agent
    os.environ["VIDEOMAKER_ACP_SMOKE_SIMPLE"] = "false"
    os.environ["VIDEOMAKER_ACP_SMOKE_FORCE_TEMPLATE"] = "composition"
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_LINT_CACHE", "true")
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX", "1")

    duration_sec = float(os.environ.get("VIDEOMAKER_ACP_SMOKE_DURATION_SEC", "5"))
    storage_root = REPO / "services" / "api" / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    run_id = os.environ.get("VIDEOMAKER_ACP_SMOKE_RUN_ID") or (
        f"{agent}-composition-{int(duration_sec)}s"
        + os.environ.get("VIDEOMAKER_ACP_SMOKE_RUN_SUFFIX", "")
    )
    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id="composition-acp-smoke",
        acp_agent=resolve_acp_agent_label(),
        task_id=f"smoke-{run_id}",
        generation_id=f"smoke-{run_id}",
    )
    scratch = storage_root / "smoke" / "acp-author" / run_id
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    slot = {
        "role": "hook_visual",
        "scriptIntent": "开场视觉钩子：5秒内用抽象几何与光效建立节奏，禁止口播原文上屏",
        "visualIntent": (
            "template=composition；纯形状/渐变/粒子动效；"
            "GSAP timeline 有明确入场与收束；禁止可读文案"
        ),
    }
    author_started = time.perf_counter()
    try:
        spec = author_material_spec_via_acp(
            AuthorRequest(
                project_id="composition-acp-smoke",
                slot=slot,
                aspect_ratio="9:16",
                brand_colors={"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
                task_id=f"smoke-{run_id}",
                generation_id=f"smoke-{run_id}",
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
        outcome_path = trace.trace_dir / "outcome.json"
        outcome = {}
        if outcome_path.is_file():
            outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "ok": False,
                    "backend": "acp",
                    "acpAgent": resolve_acp_agent_label(),
                    "error": str(exc),
                    "acpTraceDir": str(trace.trace_dir),
                    "scratchDir": str(scratch),
                    "outcome": outcome,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    author_sec = round(time.perf_counter() - author_started, 2)
    lint_passed_marker = scratch / "lint-draft" / ".lint-passed.json"
    lint_cached = lint_passed_marker.is_file()

    tmpdir = Path(tempfile.mkdtemp(prefix=f"hf-acp-{agent}-", dir=str(storage_root / "smoke")))
    clip = tmpdir / "hook_visual.mp4"
    engine = create_composition_engine(repo_root=REPO, storage_root=storage_root)
    render_started = time.perf_counter()
    result = engine.render_clip(
        spec,
        RenderPaths(
            project_root=tmpdir,
            output_dir=tmpdir / "composition",
            output_clip=clip,
            log_path=tmpdir / "render-log.json",
            aspect_ratio="9:16",
            lint_reuse_scratch=scratch,
        ),
    )
    render_sec = round(time.perf_counter() - render_started, 2)

    outcome = {}
    outcome_path = trace.trace_dir / "outcome.json"
    if outcome_path.is_file():
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))

    payload = {
        "ok": result.ok,
        "backend": "acp",
        "acpAgent": resolve_acp_agent_label(),
        "authorSec": author_sec,
        "renderSec": render_sec,
        "template": spec.get("template"),
        "durationSec": spec.get("durationSec"),
        "clip": str(clip),
        "clipBytes": clip.stat().st_size if clip.is_file() else 0,
        "compositionDir": str(result.composition_dir) if result.composition_dir else None,
        "lintPassed": result.lint_passed,
        "sessionLintMarker": str(lint_passed_marker) if lint_passed_marker.is_file() else None,
        "lintCachedInOutcome": outcome.get("lintCached"),
        "repairAttempt": outcome.get("repairAttempt"),
        "error": result.error,
        "tmpdir": str(tmpdir),
        "acpTraceDir": str(trace.trace_dir),
        "scratchDir": str(scratch),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
