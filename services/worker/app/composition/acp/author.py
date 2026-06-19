from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from acp import PROTOCOL_VERSION, text_block
from acp.schema import ClientCapabilities, EnvVariable, Implementation, McpServerStdio
from acp.stdio import spawn_agent_process
from composition.author.forbidden_copy_guard import check_forbidden_copy_in_spec
from composition.author.payload import build_material_author_user_payload
from composition.mcp.context import McpSessionContext
from composition.mcp.handlers import lint_material_spec
from composition.paths import detect_repo_root
from composition.schema_loader import validate_contract
from composition.skills.bootstrap import build_bootstrap_system_prompt
from composition.types import AuthorRequest

from app.composition.acp.agent_registry import fake_agent_command, resolve_acp_agent_command, resolve_acp_agent_label
from app.composition.acp.fs_bridge import FsBridge
from app.composition.acp.headless_client import HeadlessCompositionClient, client_capabilities
from app.composition.acp.trace import AcpAuthorTraceRecorder
from knowledge.paths import validate_storage_segment


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


def acp_timeout_sec() -> float:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "600").strip()
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 600.0


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


def _build_prompt_text(request: AuthorRequest, repo_root: Path) -> tuple[str, str]:
    system = build_bootstrap_system_prompt(repo_root=repo_root)
    payload = build_material_author_user_payload(request)
    user = json.dumps(payload, ensure_ascii=False, indent=2)
    instructions = (
        "Author a HyperFrames MaterialSpec for this slot.\n"
        "Use the videomaker-composition MCP tools: skill_view, registry_list, composition_lint_draft, "
        "write_material_spec.\n"
        "You MUST finish by calling write_material_spec with lint-passing JSON.\n"
        "Do not write material-spec.json directly via filesystem tools.\n"
        "Do not paste brief text verbatim into visible DOM copy.\n\n"
        f"{user}"
    )
    return system, instructions


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
        EnvVariable(name="PYTHONPATH", value=pythonpath),
    ]
    if asset_root is not None:
        env.append(EnvVariable(name="VM_ASSET_ROOT", value=str(asset_root)))
    return env


def _validate_spec(spec: dict[str, Any], author_payload: dict[str, Any]) -> list[str]:
    result = validate_contract("material-spec", spec)
    errors = [f"{item.path}: {item.message}" for item in result.errors]
    errors.extend(check_forbidden_copy_in_spec(spec, author_payload))
    return errors


def _lint_spec_after_turn(
    spec: dict[str, Any],
    *,
    scratch_dir: Path,
    repo_root: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    asset_root: Path | None,
) -> list[str]:
    ctx = McpSessionContext(
        scratch_dir=scratch_dir,
        repo_root=repo_root,
        author_payload=author_payload,
        aspect_ratio=aspect_ratio,
        asset_root=asset_root,
    )
    return lint_material_spec(ctx, spec_json=spec)


async def _run_acp_session(
    *,
    client_impl: HeadlessCompositionClient,
    command: list[str],
    spawn_env: dict[str, str],
    repo_root: Path,
    mcp_server: McpServerStdio,
    system: str,
    user: str,
) -> None:
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
        prompt_response = await conn.prompt(
            [text_block(f"{system}\n\n{user}")],
            session.session_id,
        )
        _ = prompt_response
        try:
            await conn.close_session(session.session_id)
        except Exception:
            pass


async def _author_async(
    request: AuthorRequest,
    *,
    repo_root: Path,
    scratch_dir: Path,
    generated_root: Path | None,
    agent_command: list[str] | None = None,
    trace: AcpAuthorTraceRecorder | None = None,
) -> dict[str, Any]:
    ensure_acp_dependencies()
    repo_root = repo_root.resolve()
    scratch_dir = scratch_dir.resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)
    payload_path = scratch_dir / "task.json"
    author_payload = build_material_author_user_payload(request)
    payload_path.write_text(json.dumps(author_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    allowed_roots: list[Path] = [scratch_dir]
    if generated_root is not None:
        allowed_roots.append(generated_root.resolve())
    client_impl = HeadlessCompositionClient(
        fs_bridge=FsBridge(allowed_roots=allowed_roots),
        trace=trace,
    )

    command = agent_command or resolve_acp_agent_command()
    spawn_env = os.environ.copy()
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
            aspect_ratio=request.aspect_ratio,
            asset_root=generated_root,
        ),
    )

    system, user = _build_prompt_text(request, repo_root)
    if trace is not None:
        trace.record_session(
            {
                "agentCommand": command,
                "repoRoot": str(repo_root),
                "scratchDir": str(scratch_dir),
            }
        )
        trace.record_prompt(system=system, user=user)

    await asyncio.wait_for(
        _run_acp_session(
            client_impl=client_impl,
            command=command,
            spawn_env=spawn_env,
            repo_root=repo_root,
            mcp_server=mcp_server,
            system=system,
            user=user,
        ),
        timeout=acp_timeout_sec(),
    )

    spec_path = scratch_dir / "material-spec.json"
    if not spec_path.is_file():
        raise RuntimeError("acp_author_missing_material_spec")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise RuntimeError("acp_author_invalid_material_spec")

    errors = _validate_spec(spec, author_payload)
    errors.extend(
        _lint_spec_after_turn(
            spec,
            scratch_dir=scratch_dir,
            repo_root=repo_root,
            author_payload=author_payload,
            aspect_ratio=request.aspect_ratio,
            asset_root=generated_root,
        )
    )
    if errors:
        raise RuntimeError(f"acp_author_spec_invalid: {'; '.join(errors)}")
    return spec


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
    try:
        spec = _run_coro_sync(
            _author_async(
                request,
                repo_root=root,
                scratch_dir=scratch_dir,
                generated_root=generated_root,
                agent_command=agent_command,
                trace=trace,
            )
        )
        if trace is not None:
            trace.finalize(
                valid=True,
                validation_errors=[],
                total_latency_ms=(time.perf_counter() - started) * 1000,
                spec_path=str(scratch_dir / "material-spec.json"),
            )
        return spec
    except Exception as exc:
        if trace is not None:
            trace.finalize(
                valid=False,
                validation_errors=[str(exc)],
                total_latency_ms=(time.perf_counter() - started) * 1000,
            )
        raise


__all__ = [
    "AcpAuthorUnavailableError",
    "author_backend",
    "author_material_spec_via_acp",
    "ensure_acp_dependencies",
    "fake_agent_command",
    "resolve_acp_agent_label",
]
