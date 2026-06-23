$ErrorActionPreference = "Stop"

$apiRoot = Join-Path $PSScriptRoot "..\..\api" | Resolve-Path
$langfuseEnv = Join-Path $apiRoot "langfuse.env"

if (-not (Test-Path $langfuseEnv)) {
    Write-Host "Missing $langfuseEnv"
    Write-Host "Copy langfuse.env.example to langfuse.env and set your keys."
    exit 1
}

Get-Content $langfuseEnv | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"')
        Set-Item -Path "env:$name" -Value $value
    }
}

$workerRoot = Join-Path $PSScriptRoot ".." | Resolve-Path
$python = Join-Path $apiRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $workerRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = "python"
}

$enabled = $env:LANGFUSE_ENABLED -match '^(?i:true|1|yes|on)$'
if ($enabled) {
    & $python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('langfuse') else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing langfuse into worker Python: $python"
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        if ($uv) {
            & uv pip install --python $python "langfuse>=4.0,<5"
        } else {
            & $python -m pip install "langfuse>=4.0,<5"
        }
    }
}

Write-Host "Using worker Python: $python"
& $python (Join-Path $workerRoot "scripts\verify_langfuse.py")
exit $LASTEXITCODE
