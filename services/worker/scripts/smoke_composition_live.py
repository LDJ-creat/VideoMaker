"""Smoke: live ReAct material author + real HyperFrames render (Layer C)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKER = REPO / "services" / "worker"
for part in (WORKER, REPO / "services" / "composition", REPO / "services" / "shared"):
    sys.path.insert(0, str(part))

from app.composition.engine_factory import create_composition_engine
from app.gateway.config import GatewayConfig
from app.gateway.model_gateway import ModelGateway
from composition.author.react_trace import FileReactTraceRecorder
from composition.types import AuthorRequest, RenderPaths
from model_gateway.store import ModelGatewayStore


def main() -> int:
    os.environ.setdefault("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    storage_root = REPO / "services" / "api" / "storage"
    db_path = storage_root / "videomaker.sqlite3"
    if not db_path.is_file():
        print(json.dumps({"ok": False, "error": f"database not found: {db_path}"}))
        return 1

    store = ModelGatewayStore(db_path, storage_root)
    config = GatewayConfig.from_store(store)
    gateway = ModelGateway(config=config)
    trace = FileReactTraceRecorder.create(
        storage_root,
        project_id="composition-smoke",
        task_id="smoke-react",
        generation_id="smoke-gen",
    )
    engine = create_composition_engine(gateway=gateway, repo_root=REPO, storage_root=storage_root)

    slot = {
        "role": "benefit_card",
        "scriptIntent": "展示三大核心卖点：轻量、续航、画质",
        "visualIntent": "卡片依次弹入，强调标题与 bullet",
    }
    author_started = time.perf_counter()
    spec = engine.author_material_spec(
        AuthorRequest(
            project_id="composition-smoke",
            slot=slot,
            aspect_ratio="9:16",
            brand_colors={"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
            task_id="smoke-react",
            generation_id="smoke-gen",
            react_trace=trace,
        )
    )
    author_sec = round(time.perf_counter() - author_started, 2)

    smoke_dir = storage_root / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="hf-live-", dir=str(smoke_dir)))
    clip = tmpdir / "benefit_card.mp4"
    render_started = time.perf_counter()
    result = engine.render_clip(
        spec,
        RenderPaths(
            project_root=tmpdir,
            output_dir=tmpdir / "composition",
            output_clip=clip,
            log_path=tmpdir / "render-log.json",
            aspect_ratio="9:16",
        ),
    )
    render_sec = round(time.perf_counter() - render_started, 2)

    payload = {
        "ok": result.ok,
        "authorSec": author_sec,
        "renderSec": render_sec,
        "template": spec.get("template"),
        "clip": str(clip),
        "clipBytes": clip.stat().st_size if clip.is_file() else 0,
        "compositionDir": str(result.composition_dir) if result.composition_dir else None,
        "lintPassed": result.lint_passed,
        "error": result.error,
        "tmpdir": str(tmpdir),
        "agentMode": os.getenv("VIDEOMAKER_COMPOSITION_AGENT_MODE"),
        "reactTraceDir": str(trace.trace_dir),
        "reactSummaryExists": (trace.trace_dir / "material-author-react-summary.json").is_file(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
