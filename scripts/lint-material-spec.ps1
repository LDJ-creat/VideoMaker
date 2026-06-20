param(
    [Parameter(Mandatory = $true)]
    [string]$Scratch
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$CompositionRoot = Join-Path $RepoRoot "services\composition"
$SharedRoot = Join-Path $RepoRoot "services\shared"

$env:PYTHONPATH = "$CompositionRoot;$SharedRoot"
if ($env:PYTHONPATH -and $env:PYTHONPATH -notmatch [regex]::Escape($SharedRoot)) {
    $env:PYTHONPATH = "$CompositionRoot;$SharedRoot;$($env:PYTHONPATH)"
}

Push-Location $RepoRoot
try {
    python -m composition.cli lint-spec --scratch $Scratch --repo-root $RepoRoot @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
