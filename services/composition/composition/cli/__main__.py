from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from composition.lint_pipeline import (
    LintContext,
    lint_material_spec_full,
    spec_lint_result_to_json,
)
from composition.paths import detect_repo_root


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _resolve_repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("VM_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return detect_repo_root()


def _build_context(args: argparse.Namespace) -> tuple[LintContext, dict[str, Any]]:
    scratch = Path(args.scratch).resolve()
    if not scratch.is_dir():
        raise ValueError(f"scratch directory not found: {scratch}")

    repo_root = _resolve_repo_root(args.repo_root)
    spec_path = Path(args.spec).resolve() if args.spec else scratch / "material-spec.json"
    if not spec_path.is_file():
        raise ValueError(f"material spec not found: {spec_path}")

    payload_path = Path(args.payload).resolve() if args.payload else scratch / "task.json"
    author_payload: dict[str, Any] = {}
    if payload_path.is_file():
        author_payload = _load_json(payload_path)

    aspect_ratio = (
        args.aspect_ratio
        or os.environ.get("VM_ASPECT_RATIO", "").strip()
        or "9:16"
    )
    asset_root_raw = args.asset_root or os.environ.get("VM_ASSET_ROOT", "").strip()
    asset_root = Path(asset_root_raw).resolve() if asset_root_raw else None

    spec = _load_json(spec_path)
    ctx = LintContext(
        scratch_dir=scratch,
        repo_root=repo_root,
        author_payload=author_payload,
        aspect_ratio=aspect_ratio,
        asset_root=asset_root,
    )
    return ctx, spec


def cmd_lint_spec(args: argparse.Namespace) -> int:
    try:
        ctx, spec = _build_context(args)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2

    errors, result = lint_material_spec_full(
        spec,
        ctx,
        schema_only=args.schema_only,
        skip_hf_if_cached=False,
    )
    if result is None:
        payload = {"ok": False, "errors": errors or ["lint failed"]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        return 1

    payload = spec_lint_result_to_json(result)
    payload["ok"] = not errors
    if errors:
        payload["errors"] = errors

    if args.json or True:
        print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="composition.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    lint_spec = sub.add_parser("lint-spec", help="Validate and lint a MaterialSpec JSON")
    lint_spec.add_argument("--scratch", required=True, help="ACP scratch directory")
    lint_spec.add_argument("--spec", help="Path to material-spec.json")
    lint_spec.add_argument("--repo-root", help="VideoMaker repo root")
    lint_spec.add_argument("--payload", help="Author payload JSON (task.json)")
    lint_spec.add_argument("--aspect-ratio", default=None)
    lint_spec.add_argument("--asset-root", default=None)
    lint_spec.add_argument("--schema-only", action="store_true")
    lint_spec.add_argument("--json", action="store_true", default=True)
    lint_spec.set_defaults(func=cmd_lint_spec)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
