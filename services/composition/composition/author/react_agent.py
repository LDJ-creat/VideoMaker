from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from composition.author.coercer import fallback_legacy_spec
from composition.author.react_trace import NullReactTraceRecorder, ReactTraceRecorder
from composition.author.tools import CompositionToolExecutor, tool_definitions
from composition.paths import detect_repo_root
from composition.render.hyperframes_cli import HyperFramesCli
from composition.schema_loader import validate_contract
from composition.skills.bootstrap import build_bootstrap_system_prompt
from composition.skills.runtime import SkillRuntime
from composition.types import AuthorRequest, BuildContext, ToolGateway
from model_gateway.chat_messages import normalize_tool_call_for_api


def _agent_mode() -> str:
    return os.getenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react").strip().lower()


def _max_turns() -> int:
    return int(os.getenv("VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS", "5"))


def _validate_spec(spec: dict[str, Any]) -> list[str]:
    result = validate_contract("material-spec", spec)
    if result.valid:
        return []
    return [f"{item.path}: {item.message}" for item in result.errors]


def _append_assistant_tool_call(messages: list[dict[str, Any]], call: dict[str, Any]) -> None:
    messages.append(
        {
            "role": "assistant",
            "tool_calls": [normalize_tool_call_for_api(call)],
        }
    )


def author_material_spec(
    request: AuthorRequest,
    gateway: ToolGateway | None,
    *,
    repo_root: Path | None = None,
    storage_root: Path | None = None,
    lint_scratch_dir: Path | None = None,
    hyperframes_cli: HyperFramesCli | None = None,
    fixture_spec: dict[str, Any] | None = None,
    react_trace: ReactTraceRecorder | None = None,
) -> dict[str, Any]:
    root = repo_root or detect_repo_root()
    trace = react_trace or NullReactTraceRecorder()
    started = time.perf_counter()
    last_response: dict[str, Any] | None = None
    validation_errors: list[str] = []

    if fixture_spec is not None:
        return fixture_spec
    if _agent_mode() in {"legacy", "single_shot"} or gateway is None:
        if gateway is not None:
            payload = gateway.complete_json(
                "material_author",
                {
                    "systemPrompt": build_bootstrap_system_prompt(
                        repo_root=root,
                        pattern_l0=request.pattern_l0,
                    ),
                    "inputs": {
                        "slot": request.slot,
                        "brandColors": request.brand_colors,
                        "variantOverrides": request.variant_overrides,
                        "assetRefs": request.asset_refs,
                        "validationErrors": request.validation_errors,
                        **(
                            {"visualStyleBible": request.visual_style_bible}
                            if isinstance(request.visual_style_bible, dict)
                            and request.visual_style_bible.get("summary")
                            else {}
                        ),
                    },
                },
                "material-spec",
            )
            errors = _validate_spec(payload)
            if not errors:
                return payload
        return fallback_legacy_spec(request.slot)

    scratch = lint_scratch_dir or (root / "services" / "composition" / ".pytest-tmp" / "react-scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    runtime = SkillRuntime(repo_root=root, storage_root=storage_root)
    build_ctx = BuildContext(
        project_root=root,
        output_dir=scratch,
        asset_root=None,
        aspect_ratio=request.aspect_ratio,
    )
    executor = CompositionToolExecutor(
        skill_runtime=runtime,
        build_ctx=build_ctx,
        lint_root=scratch,
        hyperframes_cli=hyperframes_cli,
        repo_root=root,
    )
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_bootstrap_system_prompt(
                repo_root=root,
                pattern_l0=request.pattern_l0,
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "slot": request.slot,
                    "brandColors": request.brand_colors,
                    "variantOverrides": request.variant_overrides,
                    "assetRefs": request.asset_refs,
                    "validationErrors": request.validation_errors,
                    **(
                        {"visualStyleBible": request.visual_style_bible}
                        if isinstance(request.visual_style_bible, dict)
                        and request.visual_style_bible.get("summary")
                        else {}
                    ),
                },
                ensure_ascii=False,
            ),
        },
    ]
    tools = tool_definitions()
    submitted: dict[str, Any] | None = None
    skill_view_count = 0

    try:
        for turn in range(1, _max_turns() + 1):
            turn_started = time.perf_counter()
            response = gateway.complete_with_tools(messages, tools, task="material_author")
            last_response = response
            trace.on_turn(
                turn,
                response=response,
                latency_ms=(time.perf_counter() - turn_started) * 1000,
            )
            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                content = response.get("content")
                if isinstance(content, dict):
                    errors = _validate_spec(content)
                    validation_errors = errors
                    if not errors:
                        submitted = content
                        break
                break
            for call in tool_calls:
                name = str(call.get("name", ""))
                args = call.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args)
                if name == "skill_view":
                    skill_view_count += 1
                if name == "submit_material_spec" and skill_view_count < 1:
                    observation = json.dumps(
                        {
                            "accepted": False,
                            "error": "skill_usage_rule: call skill_view at least once before submit_material_spec",
                        },
                        ensure_ascii=False,
                    )
                    _append_assistant_tool_call(messages, call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", name),
                            "content": observation,
                        }
                    )
                    trace.on_tool_result(turn, tool_name=name, observation=observation)
                    continue
                observation = executor.execute(name, args)
                _append_assistant_tool_call(messages, call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "content": observation,
                    }
                )
                trace.on_tool_result(turn, tool_name=name, observation=observation)
                if name == "submit_material_spec":
                    spec = args.get("spec_json")
                    if isinstance(spec, dict):
                        errors = _validate_spec(spec)
                        validation_errors = errors
                        if not errors:
                            submitted = spec
                        else:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": json.dumps({"validationErrors": errors}, ensure_ascii=False),
                                }
                            )
        if submitted is not None:
            trace.finalize(
                valid=True,
                submitted=True,
                validation_errors=[],
                total_latency_ms=(time.perf_counter() - started) * 1000,
                messages=messages,
            )
            return submitted
        trace.finalize(
            valid=False,
            submitted=False,
            validation_errors=validation_errors,
            total_latency_ms=(time.perf_counter() - started) * 1000,
            messages=messages,
        )
        return fallback_legacy_spec(request.slot)
    except Exception as exc:
        trace.record_failure(exc, messages=messages, last_response=last_response)
        trace.finalize(
            valid=False,
            submitted=False,
            validation_errors=[str(exc)],
            total_latency_ms=(time.perf_counter() - started) * 1000,
            messages=messages,
        )
        raise

