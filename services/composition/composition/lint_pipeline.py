from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from composition.author.forbidden_copy_guard import check_forbidden_copy_in_spec
from composition.build.composition_builder import build_composition
from composition.build.html_safety import HtmlSafetyError, validate_composition_fragment
from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner, resolve_hyperframes_argv
from composition.schema_loader import validate_contract

LINT_DRAFT_SUBDIR = "lint-draft"
LINT_PASSED_FILENAME = ".lint-passed.json"


@dataclass(frozen=True)
class LintContext:
    scratch_dir: Path
    repo_root: Path
    author_payload: dict[str, Any]
    aspect_ratio: str
    asset_root: Path | None = None

    @classmethod
    def from_mcp(cls, ctx: Any) -> LintContext:
        return cls(
            scratch_dir=ctx.scratch_dir,
            repo_root=ctx.repo_root,
            author_payload=ctx.author_payload,
            aspect_ratio=ctx.aspect_ratio,
            asset_root=ctx.asset_root,
        )


@dataclass
class LintStages:
    validate_ms: float = 0.0
    build_ms: float = 0.0
    lint_ms: float = 0.0


@dataclass
class SpecLintResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    draft_dir: Path | None = None
    spec_hash: str = ""
    cached: bool = False
    hyperframes_command: list[str] = field(default_factory=list)
    stages: LintStages = field(default_factory=LintStages)


def lint_cache_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_LINT_CACHE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def lint_draft_dir(ctx: LintContext) -> Path:
    return ctx.scratch_dir.resolve() / LINT_DRAFT_SUBDIR


def lint_passed_path(ctx: LintContext) -> Path:
    return lint_draft_dir(ctx) / LINT_PASSED_FILENAME


def compute_spec_content_hash(spec: dict[str, Any], ctx: LintContext) -> str:
    canonical = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    parts = [canonical, ctx.aspect_ratio.strip() or "9:16"]
    if ctx.asset_root is not None:
        parts.append(str(ctx.asset_root.resolve()))
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest


def validate_spec_gate(spec: dict[str, Any], author_payload: dict[str, Any]) -> list[str]:
    result = validate_contract("material-spec", spec)
    errors = [f"{item.path}: {item.message}" for item in result.errors]
    errors.extend(check_forbidden_copy_in_spec(spec, author_payload))

    if str(spec.get("template", "")) == "composition":
        composition = spec.get("composition")
        if isinstance(composition, dict):
            body_html = str(composition.get("bodyHtml", "")).strip()
            if body_html:
                try:
                    validate_composition_fragment(
                        body_html=body_html,
                        styles=str(composition.get("styles") or ""),
                        timeline_script=str(composition.get("timelineScript") or ""),
                    )
                except HtmlSafetyError as exc:
                    errors.append(str(exc))
            elif not errors:
                errors.append("composition.bodyHtml is required")
    return errors


def hyperframes_cli_for_repo(repo_root: Path) -> HyperFramesCli:
    if os.getenv("VM_ACP_FIXTURE_LINT", "").strip().lower() in {"1", "true", "yes"}:
        return HyperFramesCli(command_runner=fixture_command_runner(), repo_root=repo_root)
    return HyperFramesCli(repo_root=repo_root)


def _read_lint_passed_record(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def lint_passed_for_hash(ctx: LintContext, spec_hash: str) -> bool:
    if not lint_cache_enabled():
        return False
    record = _read_lint_passed_record(lint_passed_path(ctx))
    if record is None:
        return False
    if str(record.get("specHash", "")) != spec_hash:
        return False
    draft_dir = record.get("draftDir")
    if not isinstance(draft_dir, str) or not draft_dir.strip():
        return False
    composition_dir = Path(draft_dir)
    return composition_dir.is_dir() and (composition_dir / "index.html").is_file()


def record_lint_passed(
    ctx: LintContext,
    *,
    spec_hash: str,
    draft_dir: Path,
    hyperframes_command: list[str],
) -> None:
    draft_dir = draft_dir.resolve()
    draft_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "specHash": spec_hash,
        "draftDir": str(draft_dir),
        "hyperframesCommand": hyperframes_command,
        "recordedAt": time.time(),
    }
    marker = lint_passed_path(ctx)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_lint_passed_marker(draft_dir, spec_hash=spec_hash, hyperframes_command=hyperframes_command)


def write_lint_passed_marker(
    composition_dir: Path,
    *,
    spec_hash: str,
    hyperframes_command: list[str],
) -> None:
    composition_dir = composition_dir.resolve()
    composition_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "specHash": spec_hash,
        "draftDir": str(composition_dir),
        "hyperframesCommand": hyperframes_command,
        "recordedAt": time.time(),
    }
    (composition_dir / ".lint-passed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_lint_passed_marker(composition_dir: Path) -> dict[str, Any] | None:
    return _read_lint_passed_record(composition_dir / ".lint-passed.json")


def composition_dir_matches_hash(composition_dir: Path, spec_hash: str) -> bool:
    record = read_lint_passed_marker(composition_dir)
    if record is None:
        return False
    if str(record.get("specHash", "")) != spec_hash:
        return False
    return composition_dir.is_dir() and (composition_dir / "index.html").is_file()


def try_reuse_composition_dir(spec: dict[str, Any], ctx: LintContext) -> Path | None:
    if not lint_cache_enabled():
        return None
    spec_hash = compute_spec_content_hash(spec, ctx)
    if not lint_passed_for_hash(ctx, spec_hash):
        return None
    record = _read_lint_passed_record(lint_passed_path(ctx))
    if record is None:
        return None
    draft_dir = Path(str(record.get("draftDir", "")))
    if draft_dir.is_dir() and (draft_dir / "index.html").is_file():
        return draft_dir.resolve()
    return None


def build_and_lint_spec(
    spec: dict[str, Any],
    ctx: LintContext,
    *,
    cli: HyperFramesCli | None = None,
) -> SpecLintResult:
    started = time.perf_counter()
    spec_hash = compute_spec_content_hash(spec, ctx)
    hf_cli = cli or hyperframes_cli_for_repo(ctx.repo_root)
    hf_command = resolve_hyperframes_argv(repo_root=ctx.repo_root)
    draft_dir = lint_draft_dir(ctx)
    draft_dir.mkdir(parents=True, exist_ok=True)
    stages = LintStages()

    validate_started = time.perf_counter()
    gate_errors = validate_spec_gate(spec, ctx.author_payload)
    stages.validate_ms = round((time.perf_counter() - validate_started) * 1000, 2)
    if gate_errors:
        return SpecLintResult(
            ok=False,
            errors=gate_errors,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            draft_dir=draft_dir,
            spec_hash=spec_hash,
            hyperframes_command=hf_command,
            stages=stages,
        )

    build_started = time.perf_counter()
    try:
        build_composition(
            spec,
            draft_dir,
            asset_root=ctx.asset_root,
            project_root=ctx.scratch_dir,
            aspect_ratio=ctx.aspect_ratio,
        )
    except Exception as exc:
        stages.build_ms = round((time.perf_counter() - build_started) * 1000, 2)
        return SpecLintResult(
            ok=False,
            errors=[str(exc)],
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            draft_dir=draft_dir,
            spec_hash=spec_hash,
            hyperframes_command=hf_command,
            stages=stages,
        )
    stages.build_ms = round((time.perf_counter() - build_started) * 1000, 2)

    lint_started = time.perf_counter()
    lint_payload = hf_cli.lint(draft_dir, draft_dir / "lint-log.json")
    stages.lint_ms = round((time.perf_counter() - lint_started) * 1000, 2)
    ok = bool(lint_payload.get("ok"))
    errors = [str(item) for item in lint_payload.get("errors", [])]
    if not ok and not errors:
        stderr = str(lint_payload.get("stderr", "")).strip()
        stdout = str(lint_payload.get("stdout", "")).strip()
        errors = [stderr or stdout or "lint failed"]

    result = SpecLintResult(
        ok=ok,
        errors=errors,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        draft_dir=draft_dir,
        spec_hash=spec_hash,
        hyperframes_command=hf_command,
        stages=stages,
    )
    if ok:
        record_lint_passed(
            ctx,
            spec_hash=spec_hash,
            draft_dir=draft_dir,
            hyperframes_command=hf_command,
        )
    return result


def lint_material_spec_full(
    spec: dict[str, Any],
    ctx: LintContext,
    *,
    schema_only: bool = False,
    skip_hf_if_cached: bool = False,
    cli: HyperFramesCli | None = None,
) -> tuple[list[str], SpecLintResult | None]:
    spec_hash = compute_spec_content_hash(spec, ctx)
    validate_started = time.perf_counter()
    gate_errors = validate_spec_gate(spec, ctx.author_payload)
    validate_ms = round((time.perf_counter() - validate_started) * 1000, 2)
    if gate_errors:
        return gate_errors, SpecLintResult(
            ok=False,
            errors=gate_errors,
            spec_hash=spec_hash,
            stages=LintStages(validate_ms=validate_ms),
        )

    if schema_only:
        return [], SpecLintResult(
            ok=True,
            spec_hash=spec_hash,
            stages=LintStages(validate_ms=validate_ms),
        )

    if skip_hf_if_cached and lint_passed_for_hash(ctx, spec_hash):
        return [], SpecLintResult(
            ok=True,
            spec_hash=spec_hash,
            cached=True,
            draft_dir=try_reuse_composition_dir(spec, ctx),
            stages=LintStages(validate_ms=validate_ms),
        )

    result = build_and_lint_spec(spec, ctx, cli=cli)
    result.stages.validate_ms = validate_ms
    if result.ok:
        return [], result
    return result.errors, result


def spec_lint_result_to_json(result: SpecLintResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "errors": result.errors,
        "durationMs": result.duration_ms,
        "draftDir": str(result.draft_dir) if result.draft_dir else None,
        "specHash": result.spec_hash,
        "cached": result.cached,
        "hyperframesCommand": result.hyperframes_command,
        "stages": {
            "validateMs": result.stages.validate_ms,
            "buildMs": result.stages.build_ms,
            "lintMs": result.stages.lint_ms,
        },
    }
