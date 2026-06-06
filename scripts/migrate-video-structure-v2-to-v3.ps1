# Dry-run migration: coerce existing video-structure.json artifacts from p1-v2 to p1-v3.
# Does NOT re-run sample analysis or LLM agents — only applies structure_coercer locally.
param(
    [string]$StorageRoot = (Join-Path $PSScriptRoot ".." "storage"),
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkerRoot = Join-Path $RepoRoot "services" "worker"
$env:PYTHONPATH = $WorkerRoot

$structureFiles = @(
    Get-ChildItem -Path (Join-Path $StorageRoot "projects") -Recurse -Filter "video-structure.json" -ErrorAction SilentlyContinue
)
if ($structureFiles.Count -eq 0) {
    Write-Host "No video-structure.json files found under $StorageRoot/projects"
    exit 0
}

$coercePy = @'
import json
import sys
from pathlib import Path

worker_root = Path(sys.argv[1])
structure_path = Path(sys.argv[2])
analysis_path = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
mode = sys.argv[4] if len(sys.argv) > 4 else "dry-run"

sys.path.insert(0, str(worker_root))
from app.validation.structure_coercer import coerce_video_structure

raw = json.loads(structure_path.read_text(encoding="utf-8"))
if str(raw.get("version") or "") == "p1-v3":
    print(json.dumps({"status": "skip", "path": str(structure_path)}, ensure_ascii=False))
    raise SystemExit(0)

analysis: dict = {}
if analysis_path and analysis_path.is_file():
    loaded = json.loads(analysis_path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        analysis = loaded

coerced = coerce_video_structure(
    raw,
    project_id=str(raw.get("projectId") or ""),
    source_video_id=str(raw.get("sourceVideoId") or ""),
    analysis=analysis,
)
if str(coerced.get("version") or "") != "p1-v3":
    print(json.dumps({"status": "failed", "path": str(structure_path)}, ensure_ascii=False))
    raise SystemExit(2)

if mode == "apply":
    structure_path.write_text(
        json.dumps(coerced, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "applied", "path": str(structure_path)}, ensure_ascii=False))
else:
    print(json.dumps({"status": "would_migrate", "path": str(structure_path)}, ensure_ascii=False))
'@

$changed = 0
foreach ($file in $structureFiles) {
    $analysisPath = Join-Path $file.Directory.Parent.FullName "analysis" "sample-analysis.json"
    if (-not (Test-Path $analysisPath)) {
        $analysisPath = ""
    }
    $mode = if ($Apply) { "apply" } else { "dry-run" }
    $resultJson = python -c $coercePy $WorkerRoot $file.FullName $analysisPath $mode
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Coerce failed: $($file.FullName)"
        continue
    }
    $result = $resultJson | ConvertFrom-Json
    switch ($result.status) {
        "skip" { Write-Host "OK (already v3): $($file.FullName)" }
        "would_migrate" {
            $changed++
            Write-Host "Would migrate: $($file.FullName)"
        }
        "applied" {
            $changed++
            Write-Host "Migrated: $($file.FullName)"
        }
        default { Write-Warning "Unexpected status for $($file.FullName): $($result.status)" }
    }
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry-run complete. $changed file(s) would be updated. Re-run with -Apply to write changes."
}
else {
    Write-Host ""
    Write-Host "Applied migration to $changed file(s)."
}
