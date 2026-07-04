from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

COMPOSITION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = COMPOSITION_ROOT.parents[1]


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged["PYTHONPATH"] = os.pathsep.join(
        [str(COMPOSITION_ROOT), str(REPO_ROOT / "services" / "shared"), merged.get("PYTHONPATH", "")]
    )
    merged["VM_ACP_FIXTURE_LINT"] = "1"
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "composition.cli", "lint-spec", *args],
        cwd=str(REPO_ROOT),
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    path = tmp_path / "scratch"
    path.mkdir()
    payload = path / "task.json"
    payload.write_text(
        json.dumps({"slot": {"role": "benefit_card"}, "renderPolicy": {"forbidVoiceoverText": True}}),
        encoding="utf-8",
    )
    return path


def test_cli_schema_only_success(scratch: Path) -> None:
    spec_path = scratch / "material-spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "template": "benefit-card",
                "durationSec": 3,
                "params": {
                    "title": "Ok",
                    "bullets": ["A"],
                    "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
                },
            }
        ),
        encoding="utf-8",
    )
    proc = _run_cli(
        "--scratch",
        str(scratch),
        "--repo-root",
        str(REPO_ROOT),
        "--schema-only",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True


def test_cli_full_lint_writes_passed_marker(scratch: Path) -> None:
    spec_path = scratch / "material-spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "template": "benefit-card",
                "durationSec": 3,
                "params": {
                    "title": "Ok",
                    "bullets": ["A"],
                    "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
                },
            }
        ),
        encoding="utf-8",
    )
    proc = _run_cli(
        "--scratch",
        str(scratch),
        "--repo-root",
        str(REPO_ROOT),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert (scratch / "lint-draft" / ".lint-passed.json").is_file()


def test_cli_invalid_spec_exit_one(scratch: Path) -> None:
    (scratch / "material-spec.json").write_text(json.dumps({"durationSec": 1}), encoding="utf-8")
    proc = _run_cli("--scratch", str(scratch), "--repo-root", str(REPO_ROOT), "--schema-only")
    assert proc.returncode == 1
