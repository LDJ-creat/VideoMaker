$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv-dev\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "未找到 .venv-dev，请先执行：uv venv .venv-dev"
}

# Optional: Hugging Face mirror for faster-whisper first-time model download (China network).
# $env:HF_ENDPOINT = "https://hf-mirror.com"
# $env:HF_TOKEN = "hf_..."  # optional, improves rate limits

& $python -m app.dev_server
