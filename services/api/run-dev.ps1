$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "未找到 .venv，请先执行：cd services/api; uv venv .venv; uv pip install --python .venv\Scripts\python.exe -r pyproject.toml"
}

# Shared Python modules (model_gateway store, etc.)
$sharedRoot = Join-Path $PSScriptRoot "..\shared"
$env:PYTHONPATH = if ($env:PYTHONPATH) {
  "$sharedRoot$([IO.Path]::PathSeparator)$env:PYTHONPATH"
} else {
  $sharedRoot
}

function Import-DotEnvFile {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [string]$Label = ""
  )
  if (-not (Test-Path $Path)) {
    return $false
  }
  Get-Content $Path | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
      $name = $matches[1].Trim()
      $value = $matches[2].Trim().Trim('"')
      Set-Item -Path "env:$name" -Value $value
    }
  }
  $display = if ($Label) { $Label } else { (Split-Path $Path -Leaf) }
  Write-Host "Loaded env from $display"
  return $true
}

# Optional: Hugging Face mirror for faster-whisper first-time model download (China network).
# $env:HF_ENDPOINT = "https://hf-mirror.com"
# $env:HF_TOKEN = "hf_..."  # optional, improves rate limits

# Worker / composition dev config (ACP, render, review gates, …)
Import-DotEnvFile -Path (Join-Path $PSScriptRoot ".env") -Label ".env" | Out-Null

# Optional: Langfuse Cloud observability (see docs/demos/langfuse-cloud-setup-guide.md)
Import-DotEnvFile -Path (Join-Path $PSScriptRoot "langfuse.env") -Label "langfuse.env" | Out-Null

function Ensure-LangfuseWorkerSdk {
    param([string]$PythonExe)
    if ($env:LANGFUSE_ENABLED -notmatch '^(?i:true|1|yes|on)$') {
        return
    }
    & $PythonExe -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('langfuse') else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "LANGFUSE_ENABLED=true but langfuse SDK missing in API worker Python; installing..."
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        if ($uv) {
            & uv pip install --python $PythonExe "langfuse>=4.0,<5"
        } else {
            & $PythonExe -m pip install "langfuse>=4.0,<5"
        }
    }
}

Ensure-LangfuseWorkerSdk -PythonExe $python

& $python -m app.dev_server
