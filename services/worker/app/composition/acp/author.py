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
) -> str:
    enriched = enrich_lint_errors(errors)
    payload = {
        "turn": turn + 1,
        "validationErrors": errors,
        "hintCode": enriched["hintCode"],
        "fixRecipe": enriched["fixRecipe"],
        "allowedMedia": list_scratch_media(scratch_dir),
        "scratchDir": str(scratch_dir),
        "nextStep": "fix spec, run composition_lint_draft, then write_material_spec",
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
            "Workflow: required skill_view → draft JSON → composition_lint_draft → write_material_spec once passing.",
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


def _mcp_server_env(
    *,
    scratch_dir: Path,
    repo_root: Path,
    payload_path: Path,
    aspect_ratio: str,
    asset_root: Path | None,
) -> list[EnvVariable]:
    composition_root = repo_root / "services" / "composition"
    pythonpath = os.pathsep.join(
        [
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
        EnvVariable(name="PYTHONPATH", value=pythonpath),
    ]
    if asset_root is not None:
        env.append(EnvVariable(name="VM_ASSET_ROOT", value=str(asset_root)))
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


def _is_session_level_failure(exc: BaseException) -> bool:
    message = str(exc).lower()
    markers = (
        "connection closed",
        "connection reset",
        "broken pipe",
        "mcp",
        "tool list",
        "acp_author_missing_material_spec",
        "eof",
        "process exited",
    )
    return any(marker in message for marker in markers)


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
    trace: AcpAuthorTraceRecorder | None,
    observability: AcpAuthorObservabilityContext | None,
    author_started: float,
) -> tuple[dict[str, Any], int, bool, list[str]]:
    async with spawn_agent_process(
        lambda _agent: client_impl,
        command[0],
        *command[1:],
        env=spawn_env,
        cwd=str(repo_root),
    ) as (conn, process):
        _ = process
        await conn.initialize(
            PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities.model_validate(client_capabilities()),
            client_info=Implementation(name="videomaker-worker", version="0.1.0"),
        )
        session = await conn.new_session(
            cwd=str(repo_root),
            mcp_servers=[mcp_server],
        )

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

            await conn.prompt(
                [text_block(f"{system}\n\n{user}")],
                session.session_id,
            )

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

            if not lint_errors:
                break

            if turn >= max_turns:
                raise RuntimeError(f"acp_author_spec_invalid: {'; '.join(lint_errors)}")

            if observability is not None:
                observability.record_turn_followup(turn=turn, errors=lint_errors)
            user = _build_in_session_followup(
                lint_errors,
                turn,
                scratch_dir=scratch_dir,
                repo_root=repo_root,
            )

        try:
            await conn.close_session(session.session_id)
        except Exception:
            pass

    assert spec is not None
    repair_attempt = max(0, final_turn - 1)
    if observability is not None:
        observability.note_session_progress(repair_attempt=repair_attempt, lint_cached=lint_cached)
    return spec, repair_attempt, lint_cached, hint_codes


async def _author_async(
    request: AuthorRequest,
    *,
    repo_root: Path,
    scratch_dir: Path,
    generated_root: Path | None,
    agent_command: list[str] | None = None,
    trace: AcpAuthorTraceRecorder | None = None,
    observability: AcpAuthorObservabilityContext | None = None,
) -> tuple[dict[str, Any], int, bool, list[str]]:
    ensure_acp_dependencies()
    repo_root = repo_root.resolve()
    scratch_dir = scratch_dir.resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)

    staged_request = prepare_author_request_for_scratch(
        request,
        scratch_dir=scratch_dir,
        generated_root=generated_root,
    )
    asset_root = scratch_dir

    payload_path = scratch_dir / "task.json"
    author_payload = build_material_author_user_payload(staged_request)
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
        )

    author_started = time.time()
    last_exc: Exception | None = None
    hint_codes: list[str] = []

    for session_attempt in range(session_retry_max + 1):
        try:
            spec, repair_attempt, lint_cached, hint_codes = await asyncio.wait_for(
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
                    trace=trace,
                    observability=observability,
                    author_started=author_started,
                ),
                timeout=session_timeout,
            )
            return spec, repair_attempt, lint_cached, hint_codes
        except Exception as exc:
            last_exc = exc
            if not _is_session_level_failure(exc) or session_attempt >= session_retry_max:
                raise
            LOGGER.warning(
                "ACP session attempt %s/%s failed (%s); retrying new session",
                session_attempt + 1,
                session_retry_max + 1,
                exc,
            )
            if observability is not None:
                observability.record_session_retry(
                    attempt=session_attempt + 1,
                    error=str(exc),
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
    try:
        spec, repair_attempt, lint_cached, hint_codes = _run_coro_sync(
            _author_async(
                request,
                repo_root=root,
                scratch_dir=scratch_dir,
                generated_root=generated_root,
                agent_command=agent_command,
                trace=trace,
                observability=observability,
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
            )
        if observability is not None:
            observability.record_session_end(
                valid=True,
                latency_ms=(time.perf_counter() - started) * 1000,
                repair_attempt=repair_attempt,
                lint_cached=lint_cached,
                turn_count=repair_attempt + 1,
                hint_codes=hint_codes,
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
            )
        if observability is not None:
            observability.record_session_end(
                valid=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                validation_errors=[str(exc)],
                hint_codes=hint_codes,
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
