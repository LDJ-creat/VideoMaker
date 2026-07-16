#!/usr/bin/env python3
"""Summarize ACP composition-author traces from on-disk VideoMaker storage.

Examples (from repo root):

  python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py \\
    --project-id 7bed327a-f272-4887-a294-938d30b98723 --list

  python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py \\
    --project-id 7bed327a-f272-4887-a294-938d30b98723 \\
    --generation-id edcae35e-1184-47d4-8b4e-735c79851580 --slot slot-5

  python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py \\
    --project-id 7bed327a-f272-4887-a294-938d30b98723 --run-id 4ba6260fb75e --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MCP_TOOL_NAMES = (
    "composition_lint_draft",
    "composition_validate_draft",
    "composition_lint_scratch_file",
    "write_material_spec",
    "skill_view",
    "read_author_brief",
    "registry_list",
    "review_material_preview",
    "render_material_preview",
)

SHELL_MARKERS = (
    "python -c",
    "inspect.getsource",
    "composition.mcp",
    "_invoke_mcp",
    "from composition.mcp",
)

READ_TITLES = {"read file", "read"}
SEARCH_TITLES = {"find", "grep", "search"}
EDIT_TITLES = {"edit file", "edit", "delete file"}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _default_storage_candidates(repo_root: Path) -> list[Path]:
    return [
        repo_root / "services" / "api" / "storage",
        repo_root / "storage",
    ]


def resolve_storage_root(explicit: Path | None, repo_root: Path) -> Path:
    if explicit is not None:
        return explicit.resolve()
    for candidate in _default_storage_candidates(repo_root):
        if candidate.is_dir():
            return candidate.resolve()
    return _default_storage_candidates(repo_root)[0].resolve()


def project_root(storage_root: Path, project_id: str) -> Path:
    return storage_root / "projects" / project_id


def acp_trace_root(project_dir: Path) -> Path:
    return project_dir / "logs" / "composition-author" / "acp"


_GEN_IN_PATH = re.compile(
    r"[\\/]generations[\\/]([0-9a-fA-F-]{36})[\\/]",
)
_SLOT_IN_PATH = re.compile(
    r"[\\/]acp-author[\\/](slot-[^\\/]+)(?:[\\/]|$)",
)


def parse_generation_id(*paths: str | None) -> str | None:
    for value in paths:
        if not value:
            continue
        match = _GEN_IN_PATH.search(str(value).replace("/", "\\"))
        if match:
            return match.group(1)
        match = _GEN_IN_PATH.search(str(value))
        if match:
            return match.group(1)
    return None


def parse_slot_id(*paths: str | None) -> str | None:
    for value in paths:
        if not value:
            continue
        match = _SLOT_IN_PATH.search(str(value).replace("/", "\\"))
        if match:
            return match.group(1)
        match = _SLOT_IN_PATH.search(str(value))
        if match:
            return match.group(1)
    return None


@dataclass
class ToolStats:
    sessionUpdateLines: int = 0
    toolCallEvents: int = 0
    byKind: dict[str, int] = field(default_factory=dict)
    byTitle: dict[str, int] = field(default_factory=dict)
    readCount: int = 0
    searchCount: int = 0
    editCount: int = 0
    executeCount: int = 0
    nativeMcpToolCalls: int = 0
    listMcpResources: int = 0
    shellBypassCount: int = 0
    shellMarkers: dict[str, int] = field(default_factory=dict)
    mcpNameMentionsInShell: dict[str, int] = field(default_factory=dict)
    policyViolations: int = 0
    permissions: int = 0
    hasToolCallsFile: bool = False

    @property
    def behaviorClass(self) -> str:
        if not self.hasToolCallsFile:
            return "no_tool_calls"
        if self.nativeMcpToolCalls > 0 and self.shellBypassCount == 0:
            return "mcp_clean"
        if self.nativeMcpToolCalls > 0 and self.shellBypassCount > 0:
            return "mcp_mixed_shell"
        if self.shellBypassCount > 0:
            return "shell_bypass"
        if self.readCount + self.searchCount > 0:
            return "exploration_only"
        return "sparse"


def analyze_tool_calls(path: Path) -> ToolStats:
    stats = ToolStats(hasToolCallsFile=path.is_file())
    if not path.is_file():
        return stats

    kind_counter: Counter[str] = Counter()
    title_counter: Counter[str] = Counter()
    shell_marker_counter: Counter[str] = Counter()
    mcp_in_shell: Counter[str] = Counter()

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        kind = str(obj.get("kind") or "")
        if kind == "policy_violation":
            stats.policyViolations += 1
            continue
        if kind == "permission":
            stats.permissions += 1
            continue
        if kind != "session_update":
            continue
        stats.sessionUpdateLines += 1
        update = obj.get("update")
        if not isinstance(update, dict):
            continue
        session_update = str(update.get("sessionUpdate") or "")
        if session_update not in {"tool_call", "tool_call_update"}:
            continue
        if session_update != "tool_call":
            continue

        stats.toolCallEvents += 1
        tool_kind = str(update.get("kind") or "unknown")
        kind_counter[tool_kind] += 1
        title = str(update.get("title") or "")
        title_key = title if len(title) <= 60 else title[:57] + "..."
        if title:
            title_counter[title_key] += 1

        title_l = title.strip().lower()
        raw = json.dumps(update, ensure_ascii=False)
        is_shell_like = tool_kind == "execute" or title.strip().startswith("`")

        if title_l == "list mcp resources" or "list mcp" in title_l:
            stats.listMcpResources += 1

        if not is_shell_like:
            if tool_kind == "other" and (
                title_l.startswith("mcp:")
                or title_l == "mcp: tool"
                or title_l.startswith("mcp__")
                or "videomaker-composition" in title_l
            ):
                stats.nativeMcpToolCalls += 1
            elif any(title_l == name or title_l.endswith(name) for name in MCP_TOOL_NAMES):
                stats.nativeMcpToolCalls += 1

        if tool_kind == "read" or title_l in READ_TITLES:
            stats.readCount += 1
        if tool_kind == "search" or title_l in SEARCH_TITLES:
            stats.searchCount += 1
        if tool_kind in {"edit", "delete"} or title_l in EDIT_TITLES:
            stats.editCount += 1

        if is_shell_like:
            stats.executeCount += 1
            shellish = False
            for marker in SHELL_MARKERS:
                if marker in raw:
                    shell_marker_counter[marker] += 1
                    shellish = True
            if shellish or "python" in raw.lower():
                stats.shellBypassCount += 1
                for name in MCP_TOOL_NAMES:
                    if name in raw:
                        mcp_in_shell[name] += 1
            elif tool_kind == "execute":
                # Non-python shell still counts as execute exploration
                pass

    stats.byKind = dict(kind_counter)
    stats.byTitle = dict(title_counter.most_common(20))
    stats.shellMarkers = dict(shell_marker_counter)
    stats.mcpNameMentionsInShell = dict(mcp_in_shell)
    return stats


@dataclass
class RunSummary:
    runId: str
    traceDir: str
    valid: bool | None = None
    totalLatencyMs: float | None = None
    recordedAt: str | None = None
    validationErrors: list[str] = field(default_factory=list)
    generationId: str | None = None
    slotId: str | None = None
    repairAttempt: int | None = None
    turnCount: int | None = None
    hintCodes: list[str] = field(default_factory=list)
    acpAgent: str | None = None
    inSessionReviewEnabled: bool | None = None
    reviewMaxRounds: int | None = None
    compositionTemplate: bool | None = None
    scratchDir: str | None = None
    agentExitCode: int | None = None
    mcpToolsAvailable: list[str] | None = None
    toolStats: dict[str, Any] = field(default_factory=dict)
    behaviorClass: str | None = None
    materialReview: dict[str, Any] | None = None
    scratchArtifacts: dict[str, Any] | None = None


def summarize_run(trace_dir: Path) -> RunSummary:
    outcome = _load_json(trace_dir / "outcome.json") or {}
    session = _load_json(trace_dir / "session.json") or {}
    diagnostics = outcome.get("agentDiagnostics") if isinstance(outcome.get("agentDiagnostics"), dict) else {}

    scratch = session.get("scratchDir")
    spec_path = outcome.get("specPath")
    generation_id = parse_generation_id(
        str(scratch) if scratch else None,
        str(spec_path) if spec_path else None,
        str(outcome.get("generationId") or "") or None,
    )
    slot_id = parse_slot_id(
        str(scratch) if scratch else None,
        str(spec_path) if spec_path else None,
    )

    tool_stats = analyze_tool_calls(trace_dir / "tool_calls.jsonl")
    mcp_available = diagnostics.get("mcpToolsAvailable")
    if not isinstance(mcp_available, list):
        mcp_available = None

    summary = RunSummary(
        runId=trace_dir.name,
        traceDir=str(trace_dir),
        valid=outcome.get("valid") if "valid" in outcome else None,
        totalLatencyMs=outcome.get("totalLatencyMs"),
        recordedAt=outcome.get("recordedAt"),
        validationErrors=list(outcome.get("validationErrors") or []),
        generationId=generation_id,
        slotId=slot_id,
        repairAttempt=outcome.get("repairAttempt"),
        turnCount=outcome.get("turnCount"),
        hintCodes=list(outcome.get("hintCodes") or []),
        acpAgent=outcome.get("acpAgent") or session.get("acpAgent"),
        inSessionReviewEnabled=session.get("inSessionReviewEnabled"),
        reviewMaxRounds=session.get("reviewMaxRounds"),
        compositionTemplate=session.get("compositionTemplate"),
        scratchDir=str(scratch) if scratch else None,
        agentExitCode=diagnostics.get("agentExitCode"),
        mcpToolsAvailable=[str(x) for x in mcp_available] if mcp_available is not None else None,
        toolStats=asdict(tool_stats),
        behaviorClass=tool_stats.behaviorClass,
    )
    return summary


def list_runs(
    project_dir: Path,
    *,
    generation_id: str | None = None,
    slot_id: str | None = None,
    limit: int = 30,
) -> list[RunSummary]:
    root = acp_trace_root(project_dir)
    if not root.is_dir():
        return []
    runs: list[RunSummary] = []
    for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not child.is_dir():
            continue
        if not (child / "outcome.json").is_file():
            continue
        summary = summarize_run(child)
        if generation_id and summary.generationId != generation_id:
            continue
        if slot_id and summary.slotId != slot_id:
            continue
        runs.append(summary)
        if len(runs) >= limit:
            break
    return runs


def attach_generation_context(project_dir: Path, summary: RunSummary) -> RunSummary:
    if not summary.generationId or not summary.slotId:
        return summary
    gen_root = project_dir / "generations" / summary.generationId
    scratch = gen_root / "acp-author" / summary.slotId
    report_path = gen_root / "material-reviews" / summary.slotId / "report.json"
    marker_path = scratch / "material-review-marker.json"
    spec_path = scratch / "material-spec.json"
    task_path = scratch / "task.json"

    artifacts: dict[str, Any] = {
        "scratchDir": str(scratch) if scratch.is_dir() else None,
        "hasMaterialSpec": spec_path.is_file(),
        "hasTaskJson": task_path.is_file(),
        "hasReviewMarker": marker_path.is_file(),
        "hasReport": report_path.is_file(),
    }
    task = _load_json(task_path)
    if task:
        artifacts["hasMaterialGateRevise"] = isinstance(task.get("materialGateRevise"), dict)
        contract = task.get("authorContract") if isinstance(task.get("authorContract"), dict) else {}
        artifacts["mustChangeSpec"] = contract.get("mustChangeSpec")
        artifacts["existingSpecHash"] = task.get("existingSpecHash") or contract.get("existingSpecHash")
    if spec_path.is_file():
        try:
            text = spec_path.read_text(encoding="utf-8")
            artifacts["specBytes"] = len(text.encode("utf-8"))
            artifacts["specHasChineseQuoteHint"] = any(
                token in text for token in ("价值对等", "长久往来", "copy-layer")
            )
        except OSError:
            pass

    report = _load_json(report_path)
    if report:
        summary.materialReview = {
            "note": "current generation artifact (not a per-run snapshot)",
            "approved": report.get("approved"),
            "reviewPhase": report.get("reviewPhase"),
            "reviewBypass": report.get("reviewBypass"),
            "reviewUnavailable": report.get("reviewUnavailable"),
            "mode": (report.get("reviewInputs") or {}).get("mode")
            if isinstance(report.get("reviewInputs"), dict)
            else None,
            "issues": list(report.get("issues") or [])[:8],
            "traceRoute": (report.get("trace") or {}).get("reviewRoute")
            if isinstance(report.get("trace"), dict)
            else None,
        }

    revise = _load_json(gen_root / "revise-context.json")
    if revise:
        artifacts["hasReviseContext"] = True
        artifacts["reviseHasMaterialGateRevise"] = isinstance(revise.get("materialGateRevise"), dict)

    summary.scratchArtifacts = artifacts
    return summary


def format_text(runs: list[RunSummary]) -> str:
    lines: list[str] = []
    for run in runs:
        lines.append("=" * 72)
        lines.append(f"runId={run.runId}  valid={run.valid}  latencyMs={run.totalLatencyMs}")
        lines.append(f"recordedAt={run.recordedAt}")
        lines.append(f"generationId={run.generationId}  slotId={run.slotId}")
        lines.append(
            f"inSessionReview={run.inSessionReviewEnabled}  "
            f"turns={run.turnCount}  repair={run.repairAttempt}  "
            f"behavior={run.behaviorClass}"
        )
        if run.validationErrors:
            lines.append(f"errors={run.validationErrors}")
        ts = run.toolStats
        lines.append(
            "tools: "
            f"nativeMcp={ts.get('nativeMcpToolCalls')}  "
            f"shellBypass={ts.get('shellBypassCount')}  "
            f"read={ts.get('readCount')}  search={ts.get('searchCount')}  "
            f"edit={ts.get('editCount')}  execute={ts.get('executeCount')}  "
            f"policyViolations={ts.get('policyViolations')}  "
            f"toolCallsFile={ts.get('hasToolCallsFile')}"
        )
        if ts.get("shellMarkers"):
            lines.append(f"shellMarkers={ts.get('shellMarkers')}")
        if ts.get("mcpNameMentionsInShell"):
            lines.append(f"mcpNamesInShell={ts.get('mcpNameMentionsInShell')}")
        if ts.get("byKind"):
            lines.append(f"byKind={ts.get('byKind')}")
        if run.mcpToolsAvailable is not None:
            lines.append(f"mcpToolsAvailable={run.mcpToolsAvailable}")
        if run.materialReview:
            lines.append(f"materialReview={run.materialReview}")
        if run.scratchArtifacts:
            lines.append(f"scratch={run.scratchArtifacts}")
        lines.append(f"traceDir={run.traceDir}")
    if not runs:
        lines.append("(no matching ACP runs)")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--generation-id")
    parser.add_argument("--slot")
    parser.add_argument("--run-id")
    parser.add_argument("--storage-root", type=Path)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--list", action="store_true", help="List matching runs (default if no --run-id)")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--with-generation",
        action="store_true",
        default=True,
        help="Attach scratch/material-review context when generation+slot known (default on)",
    )
    parser.add_argument("--no-generation", action="store_true", help="Skip scratch/review attachment")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = (args.repo_root or Path(__file__).resolve().parents[4]).resolve()
    storage_root = resolve_storage_root(args.storage_root, repo_root)
    project_dir = project_root(storage_root, args.project_id)
    if not project_dir.is_dir():
        print(f"project dir not found: {project_dir}", file=sys.stderr)
        print(f"storage_root tried: {storage_root}", file=sys.stderr)
        return 2

    attach = args.with_generation and not args.no_generation
    runs: list[RunSummary] = []

    if args.run_id:
        trace_dir = acp_trace_root(project_dir) / args.run_id
        if not trace_dir.is_dir():
            print(f"trace not found: {trace_dir}", file=sys.stderr)
            return 2
        summary = summarize_run(trace_dir)
        if attach:
            summary = attach_generation_context(project_dir, summary)
        runs = [summary]
    else:
        runs = list_runs(
            project_dir,
            generation_id=args.generation_id,
            slot_id=args.slot,
            limit=args.limit,
        )
        if attach:
            runs = [attach_generation_context(project_dir, r) for r in runs]

    if args.json:
        print(json.dumps([asdict(r) for r in runs], ensure_ascii=False, indent=2))
    else:
        header = (
            f"storageRoot={storage_root}\n"
            f"project={args.project_id}\n"
            f"matches={len(runs)}\n"
        )
        print(header + format_text(runs), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
