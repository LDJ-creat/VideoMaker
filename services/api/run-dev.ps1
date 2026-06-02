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

# Optional: Hugging Face mirror for faster-whisper first-time model download (China network).
# $env:HF_ENDPOINT = "https://hf-mirror.com"
# $env:HF_TOKEN = "hf_..."  # optional, improves rate limits

& $python -m app.dev_server
