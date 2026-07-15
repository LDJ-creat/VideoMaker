from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from composition.author.coercer import build_author_fallback_spec
from composition.author.forbidden_copy_guard import check_forbidden_copy_in_spec
from composition.author.payload import build_material_author_user_payload
from composition.author.react_review import (
    material_review_max_rounds,
    material_review_repair_followup_max,
    react_author_scratch_dir,
    react_in_session_review_enabled,
    run_react_session_review,
    write_exhausted_review_marker,
)
from composition.author.react_trace import NullReactTraceRecorder, ReactTraceRecorder
from composition.author.tools import CompositionToolExecutor, tool_definitions
from composition.paths import detect_repo_root
from composition.render.hyperframes_cli import HyperFramesCli
from composition.schema_loader import validate_contract
from composition.skills.bootstrap import build_bootstrap_system_prompt
from composition.skills.runtime import SkillRuntime
from composition.skills.usage_requirements import (
    record_skill_view,
    skill_view_requirement_error,
)
from composition.types import AuthorRequest, BuildContext, ToolGateway
from model_gateway.chat_messages import normalize_tool_call_for_api


def _agent_mode() -> str:
    return os.getenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react").strip().lower()


def _max_turns() -> int:
    return int(os.getenv("VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS", "16"))


def _skill_view_max() -> int:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_REACT_SKILL_VIEW_MAX", "6").strip()
    try:
        return max(2, int(raw))
    except ValueError:
        return 6


def _validate_spec(spec: dict[str, Any]) -> list[str]:
    result = validate_contract("material-spec", spec)
    if result.valid:
        return []
    return [f"{item.path}: {item.message}" for item in result.errors]


def _resolve_review_gateway(request: AuthorRequest, gateway: ToolGateway | None) -> Any | None:
    if request.review_gateway is not None:
        return request.review_gateway
    underlying = getattr(gateway, "underlying_gateway", None)
    if underlying is not None:
        return underlying
    return None


def _append_assistant_tool_turn(
    messages: list[dict[str, Any]],
    response: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> None:
    """Append one assistant message for a tool-calling turn.

    DeepSeek thinking mode requires the original ``reasoning_content`` to be
    echoed on this assistant message when the next request includes tool results.
    Multiple tool_calls from one completion must stay on a single assistant
    message (OpenAI-compatible multi-tool turn), not one assistant per call.
    """
    assistant: dict[str, Any] = {
        "role": "assistant",
        "tool_calls": [normalize_tool_call_for_api(call) for call in tool_calls],
    }
    content = response.get("content")
    if isinstance(content, (dict, list)):
        assistant["content"] = json.dumps(content, ensure_ascii=False)
    elif content is None:
        assistant["content"] = None
    else:
        assistant["content"] = content
    reasoning = response.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning:
        assistant["reasoning_content"] = reasoning
    messages.append(assistant)


def _append_tool_result(
    messages: list[dict[str, Any]],
    call: dict[str, Any],
    observation: str,
) -> None:
    name = str(call.get("name", ""))
    messages.append(
        {
            "role": "tool",
            "tool_call_id": call.get("id", name),
            "content": observation,
        }
    )


def _append_user_nudge(messages: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    messages.append(
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        }
    )


def _align_spec_duration(spec: dict[str, Any], author_payload: dict[str, Any]) -> dict[str, Any]:
    """Force durationSec to authoritative slotTiming (hard-gate drift prevention)."""
    timing = author_payload.get("slotTiming")
    if not isinstance(timing, dict):
        return spec
    raw = timing.get("durationSec")
    try:
        duration = float(raw)
    except (TypeError, ValueError):
        return spec
    if duration <= 0:
        return spec
    aligned = dict(spec)
    aligned["durationSec"] = duration
    return aligned


def _parse_spec_arg(args: dict[str, Any]) -> dict[str, Any] | None:
    spec = args.get("spec_json")
    if isinstance(spec, str) and spec.strip():
        try:
            spec = json.loads(spec)
        except json.JSONDecodeError:
            return None
    return spec if isinstance(spec, dict) else None


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
                    "inputs": build_material_author_user_payload(request),
                },
                "material-spec",
            )
            errors = _validate_spec(payload)
            if not errors:
                return payload
        return build_author_fallback_spec(
            request.slot,
            asset_refs=request.asset_refs,
        )

    slot_id = str((request.slot or {}).get("id") or "").strip() or "slot"
    gen_root: Path | None = Path(request.generation_root) if request.generation_root else None
    if gen_root is not None and gen_root.name == "generated":
        gen_root = gen_root.parent
    resolved_scratch = lint_scratch_dir or react_author_scratch_dir(gen_root, slot_id)
    scratch = resolved_scratch or (
        root / "services" / "composition" / ".pytest-tmp" / "react-scratch"
    )
    scratch.mkdir(parents=True, exist_ok=True)
    author_payload = build_material_author_user_payload(request)
    # Ensure review/promote can locate generation + slot.
    if gen_root is not None:
        author_payload["generationRoot"] = str(gen_root)
    author_payload.setdefault("slotId", slot_id)
    if isinstance(author_payload.get("slot"), dict):
        author_payload["slot"] = {**author_payload["slot"], "id": slot_id}
    runtime = SkillRuntime(repo_root=root, storage_root=storage_root)
    build_ctx = BuildContext(
        project_root=root,
        output_dir=scratch,
        asset_root=None,
        aspect_ratio=request.aspect_ratio,
    )
    review_gateway = _resolve_review_gateway(request, gateway)
    executor = CompositionToolExecutor(
        skill_runtime=runtime,
        build_ctx=build_ctx,
        lint_root=scratch,
        hyperframes_cli=hyperframes_cli,
        repo_root=root,
        author_payload=author_payload,
        review_gateway=review_gateway,
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
                author_payload,
                ensure_ascii=False,
            ),
        },
    ]
    tools = tool_definitions()
    submitted: dict[str, Any] | None = None
    skill_views_seen: set[str] = set()
    skill_view_calls = 0
    skill_view_max = _skill_view_max()
    lint_ok_pending_submit = False
    review_rounds_used = 0
    repair_followups_sent = 0
    last_review_report: dict[str, Any] | None = None
    session_review = react_in_session_review_enabled()
    review_max = material_review_max_rounds()
    repair_max = material_review_repair_followup_max()
    has_visual_style_bible = bool(
        isinstance(request.visual_style_bible, dict)
        and str(request.visual_style_bible.get("summary") or "").strip()
    )

    def _accept_candidate_after_session_review(candidate: dict[str, Any]) -> bool:
        """Worker vision review (author-session). Returns True if candidate is final."""
        nonlocal review_rounds_used, repair_followups_sent, last_review_report, submitted
        nonlocal validation_errors
        if not session_review:
            submitted = candidate
            return True

        if review_rounds_used >= review_max:
            write_exhausted_review_marker(
                scratch,
                spec=candidate,
                report=last_review_report,
                review_rounds_used=review_rounds_used,
            )
            submitted = candidate
            validation_errors = [
                f"review_rounds_exhausted:{review_rounds_used}",
                *([str(i) for i in (last_review_report or {}).get("issues") or []][:5]),
            ]
            return True

        outcome = run_react_session_review(
            spec=candidate,
            scratch_dir=scratch,
            repo_root=root,
            author_payload=author_payload,
            aspect_ratio=request.aspect_ratio,
            review_gateway=review_gateway,
            agent_review_round=review_rounds_used + 1,
            hyperframes_cli=hyperframes_cli,
        )
        last_review_report = outcome.report
        if outcome.vision_billed:
            review_rounds_used += 1

        if outcome.approved:
            submitted = candidate
            return True

        can_repair = repair_followups_sent < repair_max
        if can_repair and outcome.repair_feedback:
            repair_followups_sent += 1
            _append_user_nudge(
                messages,
                {
                    "authorSessionReview": {
                        "approved": False,
                        "agentReviewRound": review_rounds_used,
                        "reviewMaxRounds": review_max,
                        "repairFollowup": repair_followups_sent,
                        "repairFollowupMax": repair_max,
                        "report": {
                            "issues": outcome.report.get("issues"),
                            "suggestions": outcome.report.get("suggestions"),
                            "scores": outcome.report.get("scores"),
                            "hardGateFailed": outcome.report.get("hardGateFailed"),
                        },
                    },
                    "systemNudge": (
                        "Author-session vision review rejected this MaterialSpec. "
                        "Apply the fixes below, re-run composition_lint_draft, then "
                        "submit_material_spec again. durationSec must equal slotTiming.durationSec."
                    ),
                    "repairFeedback": outcome.repair_feedback,
                },
            )
            return False

        write_exhausted_review_marker(
            scratch,
            spec=candidate,
            report=outcome.report,
            review_rounds_used=review_rounds_used,
        )
        submitted = candidate
        validation_errors = [
            "review_not_approved",
            *[str(i) for i in (outcome.report.get("issues") or [])[:5]],
        ]
        return True

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
                        candidate = _align_spec_duration(content, author_payload)
                        if _accept_candidate_after_session_review(candidate):
                            break
                        continue
                break
            _append_assistant_tool_turn(messages, response, tool_calls)
            stop_after_tools = False
            for call in tool_calls:
                name = str(call.get("name", ""))
                args = call.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                if not isinstance(args, dict):
                    args = {}

                if name == "skill_view":
                    if skill_view_calls >= skill_view_max:
                        observation = json.dumps(
                            {
                                "ok": False,
                                "error": "skill_view_cap_exceeded",
                                "skillViewCalls": skill_view_calls,
                                "skillViewMax": skill_view_max,
                                "hint": (
                                    "Stop reading skills. Draft MaterialSpec, "
                                    "composition_lint_draft, then submit_material_spec."
                                ),
                            },
                            ensure_ascii=False,
                        )
                        _append_tool_result(messages, call, observation)
                        trace.on_tool_result(turn, tool_name=name, observation=observation)
                        continue
                    record_skill_view(skill_views_seen, str(args.get("location") or ""))
                    skill_view_calls += 1

                if name == "submit_material_spec":
                    requirement_error = skill_view_requirement_error(
                        skill_views_seen,
                        has_visual_style_bible=has_visual_style_bible,
                    )
                    if requirement_error:
                        observation = json.dumps(
                            {"accepted": False, "error": requirement_error},
                            ensure_ascii=False,
                        )
                        _append_tool_result(messages, call, observation)
                        trace.on_tool_result(turn, tool_name=name, observation=observation)
                        continue

                try:
                    observation = executor.execute(name, args)
                except Exception as exc:
                    observation = json.dumps(
                        {"ok": False, "error": str(exc)},
                        ensure_ascii=False,
                    )
                _append_tool_result(messages, call, observation)
                trace.on_tool_result(turn, tool_name=name, observation=observation)

                if name == "composition_lint_draft":
                    try:
                        lint_payload = json.loads(observation)
                    except json.JSONDecodeError:
                        lint_payload = {}
                    if isinstance(lint_payload, dict) and lint_payload.get("ok") is True:
                        lint_ok_pending_submit = True
                        timing = author_payload.get("slotTiming") if isinstance(author_payload, dict) else None
                        duration_hint = None
                        if isinstance(timing, dict):
                            duration_hint = timing.get("durationSec")
                        _append_user_nudge(
                            messages,
                            {
                                "systemNudge": (
                                    "composition_lint_draft returned ok=true. "
                                    "On the NEXT turn you MUST call submit_material_spec "
                                    "with the same MaterialSpec object. "
                                    "Worker will run vision review after submit "
                                    "(author-session); fix if rejected. "
                                    "Set durationSec exactly to slotTiming.durationSec. "
                                    "Do not skill_view or re-lint unless submit is rejected."
                                ),
                                "nextTool": "submit_material_spec",
                                "requiredDurationSec": duration_hint,
                            },
                        )

                if name == "submit_material_spec":
                    lint_ok_pending_submit = False
                    try:
                        submit_payload = json.loads(observation)
                    except json.JSONDecodeError:
                        submit_payload = {}
                    accepted = bool(isinstance(submit_payload, dict) and submit_payload.get("accepted"))
                    spec = _parse_spec_arg(args)
                    if isinstance(spec, dict):
                        spec = _align_spec_duration(spec, author_payload)
                        errors = _validate_spec(spec)
                        copy_errors = check_forbidden_copy_in_spec(spec, author_payload)
                        errors = errors + copy_errors
                        validation_errors = errors
                        if not errors and accepted:
                            if _accept_candidate_after_session_review(spec):
                                stop_after_tools = True
                                break
                        elif not errors and not accepted:
                            _append_user_nudge(
                                messages,
                                {
                                    "submitRejected": submit_payload.get("error")
                                    or observation[:300],
                                    "hint": (
                                        "Fix validation/marker issues, re-lint if needed, "
                                        "then submit_material_spec again. "
                                        "durationSec must equal slotTiming.durationSec."
                                    ),
                                    "requiredDurationSec": (
                                        (author_payload.get("slotTiming") or {}).get("durationSec")
                                        if isinstance(author_payload.get("slotTiming"), dict)
                                        else None
                                    ),
                                },
                            )
                        else:
                            _append_user_nudge(
                                messages,
                                {"validationErrors": errors},
                            )
                    elif accepted and isinstance(submit_payload.get("spec"), dict):
                        candidate = _align_spec_duration(submit_payload["spec"], author_payload)
                        if _accept_candidate_after_session_review(candidate):
                            stop_after_tools = True
                            break

            if stop_after_tools or submitted is not None:
                break
            if lint_ok_pending_submit and turn >= _max_turns():
                break

        if submitted is not None:
            # If session review was on and last marker is approved → valid success.
            # If rejected/exhausted we still return the last candidate for gate promote
            # (status becomes agent_failed via marker), matching ACP harvest behavior.
            review_ok = True
            if session_review and last_review_report is not None:
                review_ok = bool(last_review_report.get("approved")) and not last_review_report.get(
                    "hardGateFailed"
                )
            trace.finalize(
                valid=review_ok,
                submitted=True,
                validation_errors=[] if review_ok else validation_errors,
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
        return build_author_fallback_spec(
            request.slot,
            asset_refs=request.asset_refs,
        )
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
