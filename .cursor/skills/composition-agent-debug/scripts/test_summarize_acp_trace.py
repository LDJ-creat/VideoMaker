"""Unit tests for summarize_acp_trace (synthetic fixtures + optional live skip)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from summarize_acp_trace import (
    analyze_tool_calls,
    attach_generation_context,
    list_runs,
    parse_generation_id,
    parse_slot_id,
    summarize_run,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_parse_ids_from_windows_paths() -> None:
    scratch = (
        r"D:\VideoMaker\services\api\storage\projects\7bed327a-f272-4887-a294-938d30b98723"
        r"\generations\edcae35e-1184-47d4-8b4e-735c79851580\acp-author\slot-5"
    )
    assert parse_generation_id(scratch) == "edcae35e-1184-47d4-8b4e-735c79851580"
    assert parse_slot_id(scratch) == "slot-5"


def test_analyze_tool_calls_classifies_mcp_shell_read(tmp_path: Path) -> None:
    path = tmp_path / "tool_calls.jsonl"
    lines = [
        {
            "kind": "session_update",
            "update": {
                "sessionUpdate": "tool_call",
                "kind": "other",
                "title": "MCP: tool",
                "toolCallId": "1",
            },
        },
        {
            "kind": "session_update",
            "update": {
                "sessionUpdate": "tool_call",
                "kind": "read",
                "title": "Read File",
                "toolCallId": "2",
            },
        },
        {
            "kind": "session_update",
            "update": {
                "sessionUpdate": "tool_call",
                "kind": "execute",
                "title": '`python -c "from composition.mcp.handlers import handle_write_material_spec"`',
                "toolCallId": "3",
                "rawInput": {"command": "python -c from composition.mcp"},
            },
        },
        {"kind": "policy_violation", "path": "services/composition/foo.py"},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    stats = analyze_tool_calls(path)
    assert stats.nativeMcpToolCalls == 1
    assert stats.readCount == 1
    assert stats.shellBypassCount == 1
    assert stats.policyViolations == 1
    assert stats.behaviorClass == "mcp_mixed_shell"


def test_list_and_summarize_runs(tmp_path: Path) -> None:
    project = "proj-1"
    gen = "edcae35e-1184-47d4-8b4e-735c79851580"
    slot = "slot-5"
    project_dir = tmp_path / "projects" / project
    scratch = project_dir / "generations" / gen / "acp-author" / slot
    scratch.mkdir(parents=True)
    (scratch / "material-spec.json").write_text('{"template":"composition"}', encoding="utf-8")
    _write_json(
        scratch / "task.json",
        {"materialGateRevise": {"affectedSlotIds": [slot]}, "authorContract": {"mustChangeSpec": True}},
    )
    _write_json(
        project_dir / "generations" / gen / "material-reviews" / slot / "report.json",
        {
            "approved": False,
            "reviewPhase": "gate_finalize",
            "reviewBypass": None,
            "reviewInputs": {"mode": "video"},
            "issues": ["beat"],
            "trace": {"reviewRoute": "gate_finalize"},
        },
    )
    run_id = "abcd1234ef56"
    trace = project_dir / "logs" / "composition-author" / "acp" / run_id
    _write_json(
        trace / "session.json",
        {
            "scratchDir": str(scratch),
            "inSessionReviewEnabled": False,
            "reviewMaxRounds": 1,
            "compositionTemplate": True,
        },
    )
    _write_json(
        trace / "outcome.json",
        {
            "valid": True,
            "validationErrors": [],
            "totalLatencyMs": 1234.5,
            "specPath": str(scratch / "material-spec.json"),
            "repairAttempt": 0,
            "turnCount": 1,
            "hintCodes": [],
            "recordedAt": "2026-07-06T09:24:24Z",
            "backend": "acp",
            "acpAgent": "cursor",
        },
    )
    (trace / "tool_calls.jsonl").write_text(
        json.dumps(
            {
                "kind": "session_update",
                "update": {
                    "sessionUpdate": "tool_call",
                    "kind": "execute",
                    "title": "`python -c composition.mcp`",
                    "rawInput": {"command": "python -c from composition.mcp"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    runs = list_runs(project_dir, generation_id=gen, slot_id=slot, limit=10)
    assert len(runs) == 1
    summary = attach_generation_context(project_dir, runs[0])
    assert summary.runId == run_id
    assert summary.generationId == gen
    assert summary.slotId == slot
    assert summary.behaviorClass == "shell_bypass"
    assert summary.scratchArtifacts and summary.scratchArtifacts["hasMaterialSpec"] is True
    assert summary.scratchArtifacts["hasMaterialGateRevise"] is True
    assert summary.materialReview and summary.materialReview["mode"] == "video"


def test_summarize_missing_tool_calls(tmp_path: Path) -> None:
    trace = tmp_path / "run1"
    _write_json(trace / "outcome.json", {"valid": False, "validationErrors": ["Internal error"], "totalLatencyMs": 1})
    _write_json(trace / "session.json", {"inSessionReviewEnabled": True})
    summary = summarize_run(trace)
    assert summary.valid is False
    assert summary.behaviorClass == "no_tool_calls"


@pytest.mark.skipif(
    not Path(
        r"D:\VideoMaker\services\api\storage\projects"
        r"\7bed327a-f272-4887-a294-938d30b98723\logs\composition-author\acp\4ba6260fb75e"
    ).is_dir(),
    reason="live storage fixture not present",
)
def test_live_storage_run_4ba6260fb75e() -> None:
    trace = Path(
        r"D:\VideoMaker\services\api\storage\projects"
        r"\7bed327a-f272-4887-a294-938d30b98723\logs\composition-author\acp\4ba6260fb75e"
    )
    project_dir = Path(
        r"D:\VideoMaker\services\api\storage\projects\7bed327a-f272-4887-a294-938d30b98723"
    )
    summary = attach_generation_context(project_dir, summarize_run(trace))
    assert summary.valid is True
    assert summary.generationId == "edcae35e-1184-47d4-8b4e-735c79851580"
    assert summary.slotId == "slot-5"
    assert summary.inSessionReviewEnabled is False
    assert summary.behaviorClass == "shell_bypass"
    assert summary.toolStats["shellBypassCount"] >= 1
    assert summary.toolStats["nativeMcpToolCalls"] == 0
    assert summary.scratchArtifacts and summary.scratchArtifacts["hasMaterialSpec"] is True
