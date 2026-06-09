from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from composition.author.react_agent import author_material_spec
from composition.build.composition_builder import build_composition
from composition.build.legacy_scaffold import MaterialScaffoldError
from composition.patterns.deposit import deposit_pattern_candidate, promote_pattern
from composition.patterns.resolver import pattern_l0_cards
from composition.paths import detect_repo_root
from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner
from composition.types import (
    AuthorRequest,
    BuildContext,
    LintResult,
    PatternDepositContext,
    PatternPromoteRequest,
    ProgressEmitter,
    RenderPaths,
    RenderResult,
    ToolGateway,
)


class CompositionEngine:
    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        storage_root: Path | None = None,
        gateway: ToolGateway | None = None,
        hyperframes_cli: HyperFramesCli | None = None,
        emit_progress: ProgressEmitter | None = None,
        fixture_spec: dict[str, Any] | None = None,
    ) -> None:
        self.repo_root = (repo_root or detect_repo_root()).resolve()
        self.storage_root = storage_root.resolve() if storage_root else None
        self.gateway = gateway
        self._cli = hyperframes_cli or HyperFramesCli(repo_root=self.repo_root)
        self._emit = emit_progress
        self._fixture_spec = fixture_spec

    @classmethod
    def fixture(cls, spec: dict[str, Any] | None = None, **kwargs: Any) -> CompositionEngine:
        if spec is not None:
            kwargs.setdefault("fixture_spec", spec)
        return cls(**kwargs)

    def author_material_spec(self, request: AuthorRequest) -> dict[str, Any]:
        if self._emit:
            self._emit("running_agent", "Authoring HyperFrames material spec")
        pattern_l0 = request.pattern_l0
        if not pattern_l0 and self.storage_root is not None:
            pattern_l0 = pattern_l0_cards(
                self.storage_root,
                project_id=request.project_id,
                slot_role=str(request.slot.get("role", "")),
            )
        enriched = AuthorRequest(
            slot=request.slot,
            project_id=request.project_id,
            brand_colors=request.brand_colors,
            variant_overrides=request.variant_overrides,
            asset_refs=request.asset_refs,
            aspect_ratio=request.aspect_ratio,
            pattern_l0=pattern_l0,
            validation_errors=request.validation_errors,
            task_id=request.task_id,
            generation_id=request.generation_id,
            react_trace=request.react_trace,
        )
        return author_material_spec(
            enriched,
            self.gateway,
            repo_root=self.repo_root,
            storage_root=self.storage_root,
            hyperframes_cli=self._cli,
            fixture_spec=self._fixture_spec,
            react_trace=enriched.react_trace,
        )

    def build_composition(self, spec: dict[str, Any], ctx: BuildContext) -> Path:
        return build_composition(
            spec,
            ctx.output_dir,
            asset_root=ctx.asset_root,
            project_root=ctx.project_root,
            aspect_ratio=ctx.aspect_ratio,
        )

    def lint_composition(self, composition_dir: Path, log_path: Path | None = None) -> LintResult:
        if os.getenv("VIDEOMAKER_COMPOSITION_SKIP_LINT", "").strip().lower() in {"1", "true", "yes"}:
            return LintResult(ok=True, skipped=True, composition_dir=composition_dir, log_path=log_path)
        payload = self._cli.lint(composition_dir, log_path)
        resolved_log = log_path if log_path and log_path.is_file() else None
        return LintResult(
            ok=bool(payload.get("ok")),
            skipped=False,
            errors=[str(item) for item in payload.get("errors", [])],
            composition_dir=composition_dir,
            log_path=resolved_log,
        )

    def render_clip(self, spec: dict[str, Any], paths: RenderPaths) -> RenderResult:
        if self._emit:
            self._emit("rendering_material", "Rendering HyperFrames material clip")
        try:
            composition_dir = build_composition(
                spec,
                paths.output_dir,
                asset_root=paths.asset_root,
                project_root=paths.project_root,
                aspect_ratio=paths.aspect_ratio,
            )
        except MaterialScaffoldError as exc:
            message = str(exc)
            code = "material_sandbox_violation" if "escapes project sandbox" in message else "material_scaffold_failed"
            return RenderResult(ok=False, error={"code": code, "message": message})

        lint_log = paths.lint_log_path or (paths.output_dir / "lint-log.json")
        lint = self.lint_composition(composition_dir, lint_log)
        lint_passed = lint.ok and not lint.skipped
        if not lint.ok and not lint.skipped and os.getenv("VIDEOMAKER_COMPOSITION_MODE", "hybrid") != "legacy":
            return RenderResult(
                ok=False,
                error={
                    "code": "composition_lint_failed",
                    "message": "; ".join(lint.errors) or "lint failed",
                    "retryable": True,
                },
                lint_passed=False,
                lint_skipped=lint.skipped,
                lint_log_path=lint.log_path,
            )

        paths.output_clip.parent.mkdir(parents=True, exist_ok=True)
        render_result = self._cli.render(composition_dir, paths.output_clip, paths.log_path)
        if not render_result.get("ok"):
            return RenderResult(
                ok=False,
                error=render_result.get("error"),
                lint_passed=lint_passed,
                lint_skipped=lint.skipped,
                lint_log_path=lint.log_path,
            )
        if not paths.output_clip.exists():
            return RenderResult(
                ok=False,
                error={"code": "material_render_missing_output", "message": "missing mp4"},
                lint_passed=lint_passed,
                lint_skipped=lint.skipped,
                lint_log_path=lint.log_path,
            )
        return RenderResult(
            ok=True,
            output_clip=paths.output_clip,
            composition_dir=composition_dir,
            duration_sec=float(spec.get("durationSec", 0)),
            lint_passed=lint_passed,
            lint_skipped=lint.skipped,
            lint_log_path=lint.log_path if lint_passed else None,
        )

    def deposit_pattern_candidate(self, ctx: PatternDepositContext) -> dict[str, str]:
        return deposit_pattern_candidate(ctx)

    def promote_pattern(self, request: PatternPromoteRequest) -> dict[str, Any]:
        return promote_pattern(request, hyperframes_cli=self._cli)
