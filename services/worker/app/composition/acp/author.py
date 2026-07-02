from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from acp import PROTOCOL_VERSION, text_block
from acp.schema import ClientCapabilities, EnvVariable, Implementation, McpServerStdio
from acp.stdio import spawn_agent_process
from composition.author.lint_errors import enrich_lint_errors, primary_hint_code
from composition.author.normalize_acp_spec import is_smoke_empty_spec, normalize_acp_material_spec
from composition.author.payload import build_material_author_user_payload
from composition.lint_pipeline import LintContext, lint_material_spec_full, validate_spec_gate
from composition.mcp.context import McpSessionContext
from composition.paths import detect_repo_root
from composition.render.hyperframes_cli import resolve_hyperframes_argv
from composition.skills.bootstrap import build_bootstrap_system_prompt
from composition.types import AuthorRequest

from app.composition.acp.agent_registry import fake_agent_command, resolve_acp_agent_command, resolve_acp_agent_label
from app.composition.acp.fs_bridge import FsBridge
from app.composition.acp.headless_client import HeadlessCompositionClient, client_capabilities
from app.composition.acp.scratch_assets import (
    list_scratch_media,
    prepare_author_request_for_scratch,
)
from app.composition.acp.trace import AcpAuthorTraceRecorder
from app.observability.acp_author_recorder import AcpAuthorObservabilityContext
from knowledge.paths import validate_storage_segment

LOGGER = logging.getLogger(__name__)

_AGENT_STDERR_TAIL_CHARS = 4000
_AGENT_EXIT_WAIT_SEC = 1.0


class AcpAuthorUnavailableError(RuntimeError):
    pass


def author_backend() -> str:
    return os.getenv("VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND", "react").strip().lower()


def ensure_acp_dependencies() -> None:
    try:
        import acp  # noqa: F401
        import mcp  # noqa: F401
    except ImportError as exc:
        raise AcpAuthorUnavailableError(
            "ACP material author requires optional worker deps: pip install -e '.[acp]' "
            "and pip install -e '../composition[mcp]'"
        ) from exc
    try:
        import composition.mcp.server  # noqa: F401
    except ImportError as exc:
        raise AcpAuthorUnavailableError(
            "ACP material author requires composition MCP server: pip install -e '../composition[mcp]'"
        ) from exc


def acp_timeout_sec(*, composition_template: bool = False) -> float:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "").strip()
    if not raw:
        return 1800.0 if composition_template else 600.0
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 1800.0 if composition_template else 600.0


def acp_prompt_timeout_sec(*, composition_template: bool = False) -> float:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_PROMPT_TIMEOUT_SEC", "").strip()
    if not raw:
        return 600.0 if composition_template else 300.0
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 600.0


def acp_max_tool_calls_per_prompt() -> int:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_MAX_TOOL_CALLS_PER_PROMPT", "80").strip()
    try:
        return max(10, int(raw))
    except ValueError:
        return 80


def acp_max_turns() -> int:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    legacy = os.getenv("VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX", "").strip()
    if legacy:
        try:
            mapped = max(0, int(legacy)) + 1
            LOGGER.warning(
                "VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX is deprecated; "
                "use VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS (mapped to %s)",
                mapped,
            )
            return max(1, mapped)
        except ValueError:
            pass
    return 5


def acp_session_retry_max() -> int:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_SESSION_RETRY", "1").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def acp_lint_repair_max() -> int:
    """Deprecated alias: repair attempts = max_turns - 1."""
    return max(0, acp_max_turns() - 1)


def _mcp_write_skip_lint_default() -> str:
    explicit = os.getenv("VIDEOMAKER_MCP_WRITE_SKIP_LINT", "").strip().lower()
    if explicit:
        return explicit
    if os.getenv("VIDEOMAKER_MCP_WRITE_LINT_FOR_ACP", "true").strip().lower() in {"1", "true", "yes"}:
        return "false"
    return "false"


def _lint_spec_command(repo_root: Path, scratch_dir: Path) -> str:
    return (
        f"{sys.executable} -m composition.cli lint-spec "
        f"--scratch {scratch_dir} --repo-root {repo_root} --json"
    )


def _hyperframes_command_text(repo_root: Path) -> str:
    return " ".join(resolve_hyperframes_argv(repo_root=repo_root))


def _build_in_session_followup(
    errors: list[str],
    turn: int,
    *,
    scratch_dir: Path,
    repo_root: Path,
    include_review_step: bool = False,
) -> str:
    enriched = enrich_lint_errors(errors)
    next_step = (
        "fix spec, composition_lint_draft, render_material_preview, review_material_preview, write_material_spec"
        if include_review_step
        else "fix spec, run composition_lint_draft, then write_material_spec"
    )
    payload = {
        "turn": turn + 1,
        "validationErrors": errors,
        "hintCode": enriched["hintCode"],
        "fixRecipe": enriched["fixRecipe"],
        "allowedMedia": list_scratch_media(scratch_dir),
        "scratchDir": str(scratch_dir),
        "nextStep": next_step,
        "lintCommand": _lint_spec_command(repo_root, scratch_dir),
    }
    if enriched["hintCode"] == "sandbox_path":
        payload["fixRecipe"] = (
            "assetRefs.uri and video src must be basename only under scratch; "
            "never use generated/ or absolute paths"
        )
    return (
        "IN_SESSION_REPAIR: fix MaterialSpec from validation/lint errors below.\n"
        "Stay in this session; reuse prior skill_view context when possible.\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def _acp_in_session_review_enabled(author_payload: dict[str, Any] | None = None) -> bool:
    from app.pipelines.material_review import material_review_enabled

    if not material_review_enabled():
        return False

    if author_payload:
        gate = author_payload.get("materialGateRevise")
        if isinstance(gate, dict):
            raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE", "false").strip().lower()
            return raw in {"1", "true", "yes"}
        revise_ctx = author_payload.get("reviseContext")
        if isinstance(revise_ctx, dict):
            scope = str(
                revise_ctx.get("materialReviewScope")
                or revise_ctx.get("materialScope")
                or ""
            ).strip().lower()
            if scope in {"scoped", "slot"} or revise_ctx.get("sourceGenerationId"):
                raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE", "false").strip().lower()
                return raw in {"1", "true", "yes"}

    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION", "true").strip().lower()
    return raw not in {"0", "false", "no"}


def _load_revise_context_for_payload(generation_root: Path | None) -> dict[str, Any] | None:
    if generation_root is None:
        return None
    context_path = generation_root / "revise-context.json"
    if not context_path.is_file():
        return None
    try:
        payload = json.loads(context_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    snippet: dict[str, Any] = {}
    for key in (
        "sourceGenerationId",
        "materialScope",
        "materialReviewScope",
        "materialEditMode",
        "affectedSlotIds",
    ):
        if key in payload:
            snippet[key] = payload[key]
    gate = payload.get("materialGateRevise")
    if isinstance(gate, dict):
        snippet["materialGateRevise"] = gate
    return snippet or None


def _review_errors_from_report(report: dict[str, Any]) -> list[str]:
    if report.get("hardGateFailed"):
        issues = [str(item) for item in report.get("issues") or [] if str(item).strip()]
        return issues or ["material_review_hard_gate_failed"]
    if not report.get("approved", True):
        issues = [str(item) for item in report.get("issues") or [] if str(item).strip()]
        suggestions = [str(item) for item in report.get("suggestions") or [] if str(item).strip()]
        merged = issues + suggestions
        return merged or ["material_review_not_approved"]
    return []


def _build_review_followup(
    report: dict[str, Any],
    turn: int,
    *,
    scratch_dir: Path,
    repo_root: Path,
) -> str:
    from app.pipelines.material_review import build_repair_feedback

    feedback = build_repair_feedback(report)
    trace = report.get("trace") if isinstance(report.get("trace"), dict) else {}
    payload = {
        "turn": turn + 1,
        "reviewReport": {
            "approved": bool(report.get("approved")),
            "hardGateFailed": bool(report.get("hardGateFailed")),
            "issues": list(report.get("issues") or []),
            "suggestions": list(report.get("suggestions") or []),
            "reviewRoute": trace.get("reviewRoute"),
        },
        "hintCode": "hard_gate" if report.get("hardGateFailed") else "material_review",
        "fixRecipe": feedback
        or "Align durationSec/timeline with slotTiming, re-run render_material_preview and review_material_preview.",
        "allowedMedia": list_scratch_media(scratch_dir),
        "scratchDir": str(scratch_dir),
        "nextStep": (
            "fix spec, composition_lint_draft, render_material_preview, "
            "review_material_preview, write_material_spec"
        ),
        "lintCommand": _lint_spec_command(repo_root, scratch_dir),
    }
    return (
        "IN_SESSION_REPAIR: material preview review failed; fix MaterialSpec from the review report below.\n"
        "Stay in this session; reuse prior skill_view context when possible.\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def _resolve_template_mode(payload: dict[str, Any]) -> str:
    force = os.getenv("VIDEOMAKER_ACP_SMOKE_FORCE_TEMPLATE", "").strip().lower()
    if force in {"composition", "benefit-card"}:
        return force
    if isinstance(payload.get("compositionAuthorBrief"), dict):
        return "composition"
    finish = payload.get("finishBrief")
    if isinstance(finish, dict):
        if isinstance(finish.get("compositionAuthorBrief"), dict):
            return "composition"
        mode = str(finish.get("completionMode", "")).strip().lower()
        if mode in {"hf_native", "source_then_polish"}:
            return "composition"
    return "benefit-card"


def _template_requirement(template_mode: str) -> str:
    if template_mode == "composition":
        return (
            "template=composition with composition.bodyHtml/styles/timelineScript (GSAP via shell tl). "
            "Text-free on screen when renderPolicy.allowedDisplayCopy is empty."
        )
    return (
        "template=benefit-card with durationSec from slotTiming; empty title/bullets when allowedDisplayCopy is empty."
    )


def _lint_channel_note(agent: str) -> str:
    if agent.strip().lower() == "codex":
        return "Lint via terminal lint-spec only (MCP composition_lint_draft times out at 120s)."
    return "Lint via composition_lint_draft or terminal lint-spec (full lint once before submit)."


def _build_acp_task_instructions(
    *,
    scratch_dir: Path,
    repo_root: Path,
    template_mode: str,
    agent: str,
) -> str:
    lint_cmd = _lint_spec_command(repo_root, scratch_dir)
    schema_cmd = lint_cmd.replace(" --json", " --schema-only --json")
    hf_cmd = _hyperframes_command_text(repo_root)
    media = list_scratch_media(scratch_dir)
    media_note = (
        f"Scratch media (basename only): {', '.join(media) if media else '(none)'}"
    )
    return "\n".join(
        [
            "Author one MaterialSpec. User payload JSON below is the sole brief — do not infer from the repo.",
            "",
            "Workflow: required skill_view → draft JSON → composition_lint_draft → write_material_spec.",
            "Do NOT call review_material_preview unless the worker explicitly enables in-session review.",
            "Forbidden: shell/python -c calls to composition.mcp.handlers; use MCP tools only.",
            "Forbidden: exploring repo source, reading worker/composition packages, or autonomous multi-hour tool loops.",
            _lint_channel_note(agent),
            f"Schema lint: {schema_cmd}",
            f"Full lint: {lint_cmd}",
            f"HyperFrames CLI (lint only): {hf_cmd}",
            "",
            f"Template: {_template_requirement(template_mode)}",
            "Output fields only: template, durationSec, params|composition. No brief fields in the spec.",
            "No verbatim brief/copy on screen. Do not write material-spec.json via filesystem tools.",
            media_note,
            f"Scratch: {scratch_dir}",
            f"Submit: write_material_spec → {scratch_dir / 'material-spec.json'}",
        ]
    )


def _resolve_repo_root(explicit: Path | None) -> Path:
    return explicit.resolve() if explicit else detect_repo_root()


def _run_coro_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("author_material_spec_via_acp must be called from a sync worker context")


def _scratch_dir(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    slot_id: str,
) -> Path:
    validate_storage_segment(project_id, field="project_id")
    validate_storage_segment(generation_id, field="generation_id")
    validate_storage_segment(slot_id, field="slot_id")
    path = (
        storage_root
        / "projects"
        / project_id
        / "generations"
        / generation_id
        / "acp-author"
        / slot_id
    )
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _build_prompt_text(request: AuthorRequest, repo_root: Path, *, scratch_dir: Path) -> tuple[str, str, bool]:
    payload = build_material_author_user_payload(request)
    user = json.dumps(payload, ensure_ascii=False, indent=2)
    timing = payload.get("slotTiming") if isinstance(payload.get("slotTiming"), dict) else {}
    duration = timing.get("durationSec", 8)
    colors = payload.get("brandColors") if isinstance(payload.get("brandColors"), dict) else {}
    template_mode = _resolve_template_mode(payload)
    composition_template = template_mode == "composition"

    if os.getenv("VIDEOMAKER_ACP_SMOKE_SIMPLE", "false").strip().lower() in {"1", "true", "yes"}:
        spec_example = {
            "template": "benefit-card",
            "durationSec": duration,
            "params": {
                "title": "",
                "bullets": [],
                "colors": colors,
            },
        }
        system = "VideoMaker composition MCP smoke author."
        instructions = (
            "Use MCP tool mcp__videomaker-composition__write_material_spec exactly once.\n"
            "Do not call skill_view, registry_list, composition_lint_draft, shell, or read tools.\n"
            "Pass this spec_json verbatim:\n"
            f"{json.dumps(spec_example, ensure_ascii=False, indent=2)}\n"
            f"Scratch directory: {scratch_dir}\n\n"
            f"{user}"
        )
        return system, instructions, False

    system = build_bootstrap_system_prompt(repo_root=repo_root, acp_author=True)
    agent = os.getenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "").strip().lower()
    instructions = _build_acp_task_instructions(
        scratch_dir=scratch_dir,
        repo_root=repo_root,
        template_mode=template_mode,
        agent=agent,
    )
    if request.material_edit_mode == "edit" and isinstance(request.existing_material_spec, dict):
        instructions += (
            "\n\nScene edit mode: apply minimal diff on existingMaterialSpec in the user payload. "
            "Do not rewrite from scratch unless editInstruction requires it. "
            "Do not replace stock/base video — pipeline already preserved base media."
        )
    elif request.material_edit_mode == "full":
        instructions += (
            "\n\nScene full regen mode: you may rewrite the spec per editInstruction, "
            "but do not attempt to re-search or swap stock footage inside this session."
        )
    instructions += f"\n\n{user}"
    return system, instructions, composition_template


def _material_spec_search_roots(scratch_dir: Path, repo_root: Path) -> list[Path]:
    roots = [
        scratch_dir,
        repo_root / "storage" / "scratch",
        repo_root / "services" / "api" / "storage" / "smoke",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_dir():
            unique.append(resolved)
    return unique


def _harvest_material_spec(
    scratch_dir: Path,
    repo_root: Path,
    *,
    not_before: float,
) -> Path | None:
    primary = scratch_dir / "material-spec.json"
    if primary.is_file():
        return primary

    candidates: list[Path] = []
    for root in _material_spec_search_roots(scratch_dir, repo_root):
        for path in root.rglob("material-spec.json"):
            if path.resolve() == primary.resolve():
                continue
            try:
                if path.stat().st_mtime >= not_before:
                    candidates.append(path)
            except OSError:
                continue

    if not candidates:
        return None

    found = max(candidates, key=lambda item: item.stat().st_mtime)
    primary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(found, primary)
    lint_src = found.parent / "material-spec.lint-passed"
    if lint_src.is_file():
        shutil.copy2(lint_src, scratch_dir / "material-spec.lint-passed")
    return primary


def _try_accept_lint_passed_harvest(
    spec_path: Path,
    *,
    scratch_dir: Path,
    repo_root: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    asset_root: Path | None,
) -> dict[str, Any] | None:
    lint_marker = scratch_dir / "material-spec.lint-passed"
    if not spec_path.is_file() or not lint_marker.is_file():
        return None
    try:
        loaded = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    loaded = normalize_acp_material_spec(loaded, scratch_dir)
    if is_smoke_empty_spec(loaded):
        return None
    composition = loaded.get("composition")
    if str(loaded.get("template") or "") == "composition":
        if not isinstance(composition, dict) or not str(composition.get("bodyHtml") or "").strip():
            return None
    lint_errors, _cached = _lint_spec_after_turn(
        loaded,
        scratch_dir=scratch_dir,
        repo_root=repo_root,
        author_payload=author_payload,
        aspect_ratio=aspect_ratio,
        asset_root=asset_root,
    )
    if lint_errors:
        return None
    return loaded


def _mcp_server_env(
    *,
    scratch_dir: Path,
    repo_root: Path,
    payload_path: Path,
    aspect_ratio: str,
    asset_root: Path | None,
    database_path: str | Path | None = None,
    storage_root: Path | None = None,
    acp_observability_run_id: str | None = None,
    in_session_review: bool = True,
) -> list[EnvVariable]:
    composition_root = repo_root / "services" / "composition"
    worker_root = repo_root / "services" / "worker"
    pythonpath = os.pathsep.join(
        [
            str(worker_root),
            str(composition_root),
            str(repo_root / "services" / "shared"),
            os.environ.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)
    env = [
        EnvVariable(name="VM_ACP_SCRATCH_DIR", value=str(scratch_dir)),
        EnvVariable(name="VM_REPO_ROOT", value=str(repo_root)),
        EnvVariable(name="VM_AUTHOR_PAYLOAD_PATH", value=str(payload_path)),
        EnvVariable(name="VM_ASPECT_RATIO", value=aspect_ratio),
        EnvVariable(name="VM_ACP_FIXTURE_LINT", value=os.environ.get("VM_ACP_FIXTURE_LINT", "")),
        EnvVariable(name="VIDEOMAKER_MCP_WRITE_SKIP_LINT", value=_mcp_write_skip_lint_default()),
        EnvVariable(name="VIDEOMAKER_MATERIAL_REVIEW_ENABLED", value=os.environ.get("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")),
        EnvVariable(name="VM_ACP_IN_SESSION_REVIEW", value="true" if in_session_review else "false"),
        EnvVariable(name="PYTHONPATH", value=pythonpath),
    ]
    db_path = str(database_path).strip() if database_path else os.environ.get("VM_DATABASE_PATH", "").strip()
    storage = str(storage_root).strip() if storage_root else os.environ.get("VM_STORAGE_ROOT", "").strip()
    if db_path:
        env.append(EnvVariable(name="VM_DATABASE_PATH", value=db_path))
    if storage:
        env.append(EnvVariable(name="VM_STORAGE_ROOT", value=storage))
    if asset_root is not None:
        env.append(EnvVariable(name="VM_ASSET_ROOT", value=str(asset_root)))
    if acp_observability_run_id:
        env.append(EnvVariable(name="VM_ACP_OBSERVABILITY_RUN_ID", value=acp_observability_run_id))
    return env


def _validate_spec(spec: dict[str, Any], author_payload: dict[str, Any]) -> list[str]:
    return validate_spec_gate(spec, author_payload)


def _lint_spec_after_turn(
    spec: dict[str, Any],
    *,
    scratch_dir: Path,
    repo_root: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    asset_root: Path | None,
) -> tuple[list[str], bool]:
    ctx = McpSessionContext(
        scratch_dir=scratch_dir,
        repo_root=repo_root,
        author_payload=author_payload,
        aspect_ratio=aspect_ratio,
        asset_root=asset_root,
    )
    lint_ctx = LintContext.from_mcp(ctx)
    errors, result = lint_material_spec_full(spec, lint_ctx, skip_hf_if_cached=True)
    cached = bool(result and result.cached)
    return errors, cached


def _review_spec_after_turn(
    spec: dict[str, Any],
    *,
    scratch_dir: Path,
    repo_root: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    asset_root: Path | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    from composition.material_review.preview import render_material_preview_spec, run_review_via_worker
    from composition.material_review.session import write_review_marker

    render_result = render_material_preview_spec(
        spec,
        scratch_dir=scratch_dir,
        repo_root=repo_root,
        aspect_ratio=aspect_ratio,
        asset_root=asset_root,
    )
    if not render_result.get("ok"):
        error = render_result.get("error") if isinstance(render_result.get("error"), dict) else {}
        message = str(error.get("message") or "preview render failed")
        return None, [f"preview_render_failed:{message}"]

    preview_path = Path(str(render_result["previewPath"]))
    slot = author_payload.get("slot") if isinstance(author_payload.get("slot"), dict) else {}
    slot_id = str(slot.get("id") or author_payload.get("slotId") or "slot")
    generation_id = str(author_payload.get("generationId") or "generation")
    generation_root_raw = author_payload.get("generationRoot")
    generation_root = Path(str(generation_root_raw)) if generation_root_raw else None

    review_result = run_review_via_worker(
        preview_path=preview_path,
        spec=spec,
        author_payload=author_payload,
        slot_id=slot_id,
        generation_id=generation_id,
        generation_root=generation_root,
    )
    if not review_result.get("ok"):
        error = review_result.get("error") if isinstance(review_result.get("error"), dict) else {}
        code = str(error.get("code") or "review_failed")
        message = str(error.get("message") or "material review failed")
        return None, [f"{code}:{message}"]

    report = review_result.get("report")
    if not isinstance(report, dict):
        return None, ["review_failed:invalid_report"]

    write_review_marker(scratch_dir, spec=spec, report=report)
    return report, _review_errors_from_report(report)


async def _drain_stderr_tail(stream: asyncio.StreamReader | None, *, max_chars: int) -> str:
    if stream is None:
        return ""
    chunks: list[bytes] = []
    total = 0
    while total < max_chars:
        try:
            piece = await asyncio.wait_for(stream.read(4096), timeout=0.05)
        except asyncio.TimeoutError:
            break
        if not piece:
            break
        chunks.append(piece)
        total += len(piece)
    text = b"".join(chunks).decode("utf-8", errors="replace")
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


async def _terminate_agent_process(process: asyncio.subprocess.Process | None) -> None:
    if process is None or process.returncode is not None:
        return
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        try:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except Exception:
            pass
    except Exception:
        pass


async def _collect_agent_diagnostics(process: asyncio.subprocess.Process | None) -> dict[str, Any]:
    if process is None:
        return {}
    exit_code = process.returncode
    if exit_code is None:
        try:
            await asyncio.wait_for(process.wait(), timeout=_AGENT_EXIT_WAIT_SEC)
        except asyncio.TimeoutError:
            pass
        exit_code = process.returncode
    stderr_tail = await _drain_stderr_tail(process.stderr, max_chars=_AGENT_STDERR_TAIL_CHARS)
    diagnostics: dict[str, Any] = {}
    if exit_code is not None:
        diagnostics["agentExitCode"] = exit_code
    elif process.returncode is None:
        diagnostics["agentStillRunning"] = True
    if stderr_tail.strip():
        diagnostics["agentStderrTail"] = stderr_tail
    return diagnostics


def _is_session_level_failure(exc: BaseException) -> bool:
    message = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    markers = (
        "connection closed",
        "connection reset",
        "broken pipe",
        "mcp",
        "tool list",
        "acp_author_missing_material_spec",
        "eof",
        "process exited",
        "internal error",
        "requesterror",
    )
    return exc_type == "requesterror" or any(marker in message for marker in markers)


def _acp_failure_hint(trace: AcpAuthorTraceRecorder | None) -> str | None:
    if trace is None:
        return None
    log_path = trace.trace_dir / "tool_calls.jsonl"
    if not log_path.is_file():
        return None
    chunks: list[str] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        update = payload.get("update") if isinstance(payload, dict) else None
        if not isinstance(update, dict):
            continue
        content = update.get("content")
        if isinstance(content, dict):
            text = str(content.get("text", "")).strip()
            if text:
                chunks.append(text)
    joined = " ".join(chunks).strip()
    if not joined:
        return None
    if "upgrade your plan" in joined.lower():
        return "cursor agent reported plan/usage limit; try --model auto or check dashboard usage"
    return joined[:240]


async def _run_single_acp_session_turn_loop(
    *,
    client_impl: HeadlessCompositionClient,
    command: list[str],
    spawn_env: dict[str, str],
    repo_root: Path,
    mcp_server: McpServerStdio,
    system: str,
    initial_user: str,
    scratch_dir: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    asset_root: Path,
    max_turns: int,
    session_timeout: float,
    prompt_timeout: float,
    in_session_review: bool,
    trace: AcpAuthorTraceRecorder | None,
    observability: AcpAuthorObservabilityContext | None,
    author_started: float,
    agent_diagnostics_out: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int, bool, list[str], dict[str, Any]]:
    agent_diagnostics: dict[str, Any] = {}
    async with spawn_agent_process(
        lambda _agent: client_impl,
        command[0],
        *command[1:],
        env=spawn_env,
        cwd=str(repo_root),
    ) as (conn, process):
        try:
            await conn.initialize(
                PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities.model_validate(client_capabilities()),
                client_info=Implementation(name="videomaker-worker", version="0.1.0"),
            )
            session = await conn.new_session(
                cwd=str(repo_root),
                mcp_servers=[mcp_server],
            )

            mcp_tools: list[str] = []
            list_tools = getattr(conn, "list_mcp_tools", None) or getattr(conn, "list_tools", None)
            if callable(list_tools):
                try:
                    tool_result = await list_tools(session.session_id)
                    if isinstance(tool_result, list):
                        for item in tool_result:
                            name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
                            if name:
                                mcp_tools.append(str(name))
                except Exception as exc:
                    LOGGER.warning("ACP MCP tool list failed: %s", exc)
            required_tools = {"write_material_spec", "composition_lint_draft"}
            if mcp_tools:
                agent_diagnostics["mcpToolsAvailable"] = mcp_tools
                missing = sorted(required_tools - set(mcp_tools))
                if missing:
                    raise RuntimeError(f"acp_mcp_tools_missing:{','.join(missing)}")

            user = initial_user
            spec: dict[str, Any] | None = None
            lint_cached = False
            hint_codes: list[str] = []
            final_turn = 0
            last_errors: list[str] = []

            for turn in range(1, max_turns + 1):
                final_turn = turn
                if observability is not None:
                    observability.record_turn_start(turn=turn)
                if trace is not None and turn > 1:
                    trace.record_prompt(system=system, user=user)

                try:
                    await asyncio.wait_for(
                        conn.prompt(
                            [text_block(f"{system}\n\n{user}")],
                            session.session_id,
                        ),
                        timeout=prompt_timeout,
                    )
                except asyncio.TimeoutError:
                    LOGGER.warning(
                        "ACP prompt timed out turn=%s scratch=%s after %.0fs",
                        turn,
                        scratch_dir,
                        prompt_timeout,
                    )
                    spec_path = _harvest_material_spec(scratch_dir, repo_root, not_before=author_started - 5.0)
                    if spec_path is not None:
                        partial = _try_accept_lint_passed_harvest(
                            spec_path,
                            scratch_dir=scratch_dir,
                            repo_root=repo_root,
                            author_payload=author_payload,
                            aspect_ratio=aspect_ratio,
                            asset_root=asset_root,
                        )
                        if partial is not None:
                            agent_diagnostics["partialHarvestAccepted"] = True
                            agent_diagnostics["promptTimeoutSec"] = prompt_timeout
                            spec = partial
                            break
                    if turn >= max_turns:
                        raise RuntimeError(
                            f"acp_author_prompt_timeout: turn {turn} exceeded {prompt_timeout:.0f}s"
                        )
                    user = _build_in_session_followup(
                        [
                            f"Prompt exceeded {prompt_timeout:.0f}s budget. "
                            "Stop autonomous loops; run composition_lint_draft once and write_material_spec."
                        ],
                        turn,
                        scratch_dir=scratch_dir,
                        repo_root=repo_root,
                        include_review_step=False,
                    )
                    continue
                except Exception as prompt_exc:
                    hint = _acp_failure_hint(trace)
                    LOGGER.error(
                        "ACP prompt failed turn=%s scratch=%s agent=%s error=%s hint=%s",
                        turn,
                        scratch_dir,
                        command,
                        prompt_exc,
                        hint,
                        exc_info=True,
                    )
                    agent_diagnostics = await _collect_agent_diagnostics(process)
                    if agent_diagnostics:
                        LOGGER.error("ACP agent diagnostics after prompt failure: %s", agent_diagnostics)
                    raise

                spec_path = _harvest_material_spec(scratch_dir, repo_root, not_before=author_started - 5.0)
                if spec_path is None or not spec_path.is_file():
                    last_errors = ["acp_author_missing_material_spec"]
                    hint_codes.append("missing_spec")
                    if turn < max_turns:
                        if observability is not None:
                            observability.record_turn_followup(turn=turn, errors=last_errors)
                        user = _build_in_session_followup(
                            last_errors,
                            turn,
                            scratch_dir=scratch_dir,
                            repo_root=repo_root,
                        )
                        continue
                    hint = _acp_failure_hint(trace)
                    message = "acp_author_missing_material_spec"
                    if hint:
                        message = f"{message}: {hint}"
                    raise RuntimeError(message)

                loaded = json.loads(spec_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise RuntimeError("acp_author_invalid_material_spec")

                loaded = normalize_acp_material_spec(loaded, scratch_dir)
                if is_smoke_empty_spec(loaded):
                    last_errors = ["empty smoke benefit-card spec rejected"]
                    hint_codes.append("missing_spec")
                    if turn < max_turns:
                        if observability is not None:
                            observability.record_turn_followup(turn=turn, errors=last_errors)
                        user = _build_in_session_followup(
                            last_errors,
                            turn,
                            scratch_dir=scratch_dir,
                            repo_root=repo_root,
                        )
                        continue
                    raise RuntimeError("acp_author_spec_invalid: empty smoke benefit-card spec rejected")

                spec = loaded
                lint_started = time.perf_counter()
                lint_errors, lint_cached = _lint_spec_after_turn(
                    spec,
                    scratch_dir=scratch_dir,
                    repo_root=repo_root,
                    author_payload=author_payload,
                    aspect_ratio=aspect_ratio,
                    asset_root=asset_root,
                )
                last_errors = lint_errors
                if lint_errors:
                    hint_codes.append(primary_hint_code(lint_errors))

                if observability is not None:
                    observability.record_turn_lint_gate(
                        turn=turn,
                        errors=lint_errors,
                        lint_cached=lint_cached,
                        latency_ms=(time.perf_counter() - lint_started) * 1000,
                    )

                if lint_errors:
                    if turn >= max_turns:
                        raise RuntimeError(f"acp_author_spec_invalid: {'; '.join(lint_errors)}")

                    if observability is not None:
                        observability.record_turn_followup(turn=turn, errors=lint_errors)
                    user = _build_in_session_followup(
                        lint_errors,
                        turn,
                        scratch_dir=scratch_dir,
                        repo_root=repo_root,
                        include_review_step=in_session_review,
                    )
                    continue

                if in_session_review:
                    review_started = time.perf_counter()
                    review_report, review_errors = _review_spec_after_turn(
                        spec,
                        scratch_dir=scratch_dir,
                        repo_root=repo_root,
                        author_payload=author_payload,
                        aspect_ratio=aspect_ratio,
                        asset_root=asset_root,
                    )
                    if review_errors:
                        last_errors = review_errors
                        hint_codes.append(
                            "hard_gate" if review_report and review_report.get("hardGateFailed") else "material_review"
                        )
                        if observability is not None:
                            observability.record_turn_review_gate(
                                turn=turn,
                                errors=review_errors,
                                hard_gate_failed=bool(
                                    review_report and review_report.get("hardGateFailed")
                                ),
                                approved=bool(review_report and review_report.get("approved")),
                                latency_ms=(time.perf_counter() - review_started) * 1000,
                            )
                        if turn >= max_turns:
                            raise RuntimeError(f"acp_author_spec_invalid: {'; '.join(review_errors)}")

                        if observability is not None:
                            observability.record_turn_followup(turn=turn, errors=review_errors)
                        user = _build_review_followup(
                            review_report
                            or {
                                "approved": False,
                                "hardGateFailed": True,
                                "issues": review_errors,
                                "suggestions": ["Fix preview render before creative review."],
                            },
                            turn,
                            scratch_dir=scratch_dir,
                            repo_root=repo_root,
                        )
                        continue

                    if observability is not None:
                        observability.record_turn_review_gate(
                            turn=turn,
                            errors=[],
                            hard_gate_failed=False,
                            approved=True,
                            latency_ms=(time.perf_counter() - review_started) * 1000,
                        )

                break

            try:
                await conn.close_session(session.session_id)
            except Exception:
                pass
        finally:
            await _terminate_agent_process(process)
            agent_diagnostics = await _collect_agent_diagnostics(process)
            if agent_diagnostics_out is not None:
                agent_diagnostics_out.clear()
                agent_diagnostics_out.update(agent_diagnostics)

    assert spec is not None
    repair_attempt = max(0, final_turn - 1)
    if observability is not None:
        observability.note_session_progress(repair_attempt=repair_attempt, lint_cached=lint_cached)
    return spec, repair_attempt, lint_cached, hint_codes, agent_diagnostics


async def _author_async(
    request: AuthorRequest,
    *,
    repo_root: Path,
    scratch_dir: Path,
    generated_root: Path | None,
    agent_command: list[str] | None = None,
    trace: AcpAuthorTraceRecorder | None = None,
    observability: AcpAuthorObservabilityContext | None = None,
    storage_root: Path | None = None,
    database_path: str | Path | None = None,
    last_agent_diagnostics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int, bool, list[str], dict[str, Any]]:
    ensure_acp_dependencies()
    repo_root = repo_root.resolve()
    scratch_dir = scratch_dir.resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)

    staged_request, base_video_diagnostics = prepare_author_request_for_scratch(
        request,
        scratch_dir=scratch_dir,
        generated_root=generated_root,
    )
    asset_root = scratch_dir

    payload_path = scratch_dir / "task.json"
    author_payload = build_material_author_user_payload(staged_request)
    if generated_root is not None:
        author_payload["generationRoot"] = str(generated_root)
    revise_context = _load_revise_context_for_payload(generated_root)
    if revise_context:
        author_payload["reviseContext"] = revise_context
        gate = revise_context.get("materialGateRevise")
        if isinstance(gate, dict):
            author_payload["materialGateRevise"] = gate
    if base_video_diagnostics:
        author_payload["baseVideoDiagnostics"] = base_video_diagnostics
    in_session_review = _acp_in_session_review_enabled(author_payload)
    payload_path.write_text(json.dumps(author_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    allowed_roots: list[Path] = [scratch_dir]
    client_impl = HeadlessCompositionClient(
        fs_bridge=FsBridge(allowed_roots=allowed_roots),
        trace=trace,
        observability=observability,
    )

    command = agent_command or resolve_acp_agent_command()
    spawn_env = os.environ.copy()
    claude_model = os.getenv("VIDEOMAKER_CLAUDE_ACP_MODEL", "").strip()
    if claude_model:
        spawn_env["ANTHROPIC_MODEL"] = claude_model
    spawn_env.setdefault("VM_ACP_SCRATCH_DIR", str(scratch_dir))
    worker_root = Path(__file__).resolve().parents[3]
    composition_root = repo_root / "services" / "composition"
    shared_root = repo_root / "services" / "shared"
    pythonpath = os.pathsep.join(
        [
            str(worker_root),
            str(composition_root),
            str(shared_root),
            spawn_env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)
    if pythonpath:
        spawn_env["PYTHONPATH"] = pythonpath

    mcp_server = McpServerStdio(
        name="videomaker-composition",
        command=sys.executable,
        args=["-m", "composition.mcp.server"],
        env=_mcp_server_env(
            scratch_dir=scratch_dir,
            repo_root=repo_root,
            payload_path=payload_path,
            aspect_ratio=staged_request.aspect_ratio,
            asset_root=asset_root,
            database_path=database_path,
            storage_root=storage_root,
            acp_observability_run_id=observability.run_id if observability is not None else None,
            in_session_review=in_session_review,
        ),
    )

    system, base_user, composition_template = _build_prompt_text(
        staged_request,
        repo_root,
        scratch_dir=scratch_dir,
    )
    max_turns = acp_max_turns()
    repair_max = acp_lint_repair_max()
    session_retry_max = acp_session_retry_max()
    session_timeout = acp_timeout_sec(composition_template=composition_template)
    prompt_timeout = acp_prompt_timeout_sec(composition_template=composition_template)

    if trace is not None:
        trace.record_session(
            {
                "agentCommand": command,
                "repoRoot": str(repo_root),
                "scratchDir": str(scratch_dir),
                "assetRoot": str(asset_root),
                "maxTurns": max_turns,
                "lintRepairMax": repair_max,
                "sessionRetryMax": session_retry_max,
                "acpTimeoutSec": session_timeout,
                "promptTimeoutSec": prompt_timeout,
                "inSessionReviewEnabled": in_session_review,
                "baseVideoReencoded": bool(base_video_diagnostics and base_video_diagnostics.get("reencoded")),
                "compositionTemplate": composition_template,
            },
            observability_run_id=observability.run_id if observability is not None else None,
        )
        trace.record_prompt(system=system, user=base_user)

    if observability is not None:
        observability.record_session_start(
            agent_command=command,
            acp_timeout_sec=session_timeout,
            composition_template=composition_template,
            lint_repair_max=repair_max,
            max_turns=max_turns,
            prompt_timeout_sec=prompt_timeout,
            in_session_review_enabled=in_session_review,
        )

    author_started = time.time()
    last_exc: Exception | None = None
    hint_codes: list[str] = []
    session_diagnostics: dict[str, Any] = {}

    for session_attempt in range(session_retry_max + 1):
        session_diagnostics.clear()
        try:
            spec, repair_attempt, lint_cached, hint_codes, session_diag = await asyncio.wait_for(
                _run_single_acp_session_turn_loop(
                    client_impl=client_impl,
                    command=command,
                    spawn_env=spawn_env,
                    repo_root=repo_root,
                    mcp_server=mcp_server,
                    system=system,
                    initial_user=base_user,
                    scratch_dir=scratch_dir,
                    author_payload=author_payload,
                    aspect_ratio=staged_request.aspect_ratio,
                    asset_root=asset_root,
                    max_turns=max_turns,
                    session_timeout=session_timeout,
                    prompt_timeout=prompt_timeout,
                    in_session_review=in_session_review,
                    trace=trace,
                    observability=observability,
                    author_started=author_started,
                    agent_diagnostics_out=session_diagnostics,
                ),
                timeout=session_timeout,
            )
            if last_agent_diagnostics is not None:
                last_agent_diagnostics.clear()
                last_agent_diagnostics.update(session_diag)
            return spec, repair_attempt, lint_cached, hint_codes, session_diag
        except Exception as exc:
            last_exc = exc
            if last_agent_diagnostics is not None and session_diagnostics:
                last_agent_diagnostics.clear()
                last_agent_diagnostics.update(session_diagnostics)
            if not _is_session_level_failure(exc) or session_attempt >= session_retry_max:
                raise
            LOGGER.warning(
                "ACP session attempt %s/%s failed (%s); retrying new session diagnostics=%s",
                session_attempt + 1,
                session_retry_max + 1,
                exc,
                session_diagnostics or None,
            )
            if observability is not None:
                observability.record_session_retry(
                    attempt=session_attempt + 1,
                    error=str(exc),
                    agent_diagnostics=session_diagnostics or None,
                )

    assert last_exc is not None
    raise last_exc


def author_material_spec_via_acp(
    request: AuthorRequest,
    *,
    repo_root: Path | None = None,
    storage_root: Path | None = None,
    scratch_dir: Path | None = None,
    generated_root: Path | None = None,
    slot_id: str = "",
    agent_command: list[str] | None = None,
    trace: AcpAuthorTraceRecorder | None = None,
    observability: AcpAuthorObservabilityContext | None = None,
) -> dict[str, Any]:
    ensure_acp_dependencies()
    root = _resolve_repo_root(repo_root)
    if scratch_dir is None:
        if storage_root is None or not request.project_id or not request.generation_id or not slot_id:
            raise ValueError("scratch_dir or storage_root/project/generation/slot_id required for ACP author")
        scratch_dir = _scratch_dir(
            storage_root,
            project_id=request.project_id,
            generation_id=request.generation_id,
            slot_id=slot_id,
        )

    started = time.perf_counter()
    hint_codes: list[str] = []
    agent_diagnostics: dict[str, Any] = {}
    try:
        spec, repair_attempt, lint_cached, hint_codes, agent_diagnostics = _run_coro_sync(
            _author_async(
                request,
                repo_root=root,
                scratch_dir=scratch_dir,
                generated_root=generated_root,
                agent_command=agent_command,
                trace=trace,
                observability=observability,
                storage_root=storage_root,
                database_path=os.environ.get("VM_DATABASE_PATH"),
                last_agent_diagnostics=agent_diagnostics,
            )
        )
        if trace is not None:
            trace.finalize(
                valid=True,
                validation_errors=[],
                total_latency_ms=(time.perf_counter() - started) * 1000,
                spec_path=str(scratch_dir / "material-spec.json"),
                repair_attempt=repair_attempt,
                lint_cached=lint_cached,
                turn_count=repair_attempt + 1,
                hint_codes=hint_codes,
                agent_diagnostics=agent_diagnostics or None,
            )
        if observability is not None:
            observability.record_session_end(
                valid=True,
                latency_ms=(time.perf_counter() - started) * 1000,
                repair_attempt=repair_attempt,
                lint_cached=lint_cached,
                turn_count=repair_attempt + 1,
                hint_codes=hint_codes,
                agent_diagnostics=agent_diagnostics or None,
            )
        return spec
    except Exception as exc:
        hint = primary_hint_code([str(exc)])
        if hint and hint not in hint_codes:
            hint_codes.append(hint)
        if trace is not None:
            trace.finalize(
                valid=False,
                validation_errors=[str(exc)],
                total_latency_ms=(time.perf_counter() - started) * 1000,
                hint_codes=hint_codes,
                hint_code=hint or None,
                agent_diagnostics=agent_diagnostics or None,
            )
        if observability is not None:
            observability.record_session_end(
                valid=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                validation_errors=[str(exc)],
                hint_codes=hint_codes,
                agent_diagnostics=agent_diagnostics or None,
            )
        raise


__all__ = [
    "AcpAuthorUnavailableError",
    "acp_max_turns",
    "acp_session_retry_max",
    "author_backend",
    "author_material_spec_via_acp",
    "ensure_acp_dependencies",
    "fake_agent_command",
    "resolve_acp_agent_label",
]
