"""Smoke: ACP external agent material author + HyperFrames render (Layer C extension)."""
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
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND", "acp")
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_ACP_AGENT", "cursor")
    duration_sec = float(os.environ.get("VIDEOMAKER_ACP_SMOKE_DURATION_SEC", "8"))
    storage_root = REPO / "services" / "api" / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id="composition-acp-smoke",
        acp_agent=resolve_acp_agent_label(),
        task_id="smoke-acp",
        generation_id="smoke-acp-gen",
    )
    scratch = storage_root / "smoke" / "acp-author" / "benefit-card"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    slot = {
        "role": "benefit_card",
        "scriptIntent": "展示三大核心卖点：轻量、续航、画质",
        "visualIntent": "三张卡片依次弹入；纯图标+进度条动效，禁止任何可读中英文文案",
    }
    author_started = time.perf_counter()
    spec = author_material_spec_via_acp(
        AuthorRequest(
            project_id="composition-acp-smoke",
            slot=slot,
            aspect_ratio="9:16",
            brand_colors={"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
            task_id="smoke-acp",
            generation_id="smoke-acp-gen",
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
    author_sec = round(time.perf_counter() - author_started, 2)

    tmpdir = Path(tempfile.mkdtemp(prefix="hf-acp-live-", dir=str(storage_root / "smoke")))
    clip = tmpdir / "benefit_card.mp4"
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

    payload = {
        "ok": result.ok,
        "backend": "acp",
        "acpAgent": resolve_acp_agent_label(),
        "authorSec": author_sec,
        "renderSec": render_sec,
        "template": spec.get("template"),
        "clip": str(clip),
        "clipBytes": clip.stat().st_size if clip.is_file() else 0,
        "compositionDir": str(result.composition_dir) if result.composition_dir else None,
        "lintPassed": result.lint_passed,
        "error": result.error,
        "tmpdir": str(tmpdir),
        "acpTraceDir": str(trace.trace_dir),
        "scratchDir": str(scratch),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
