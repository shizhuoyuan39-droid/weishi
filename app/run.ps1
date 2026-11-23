param(
  [int]$Port = 8788,
  [string]$HostAddr = "127.0.0.1"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:HF_HOME = Join-Path $root "data\hf"
$env:TRANSFORMERS_CACHE = Join-Path $root "data\hf"
$env:PYTHONUTF8 = "1"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Creating venv..."
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\pip.exe install -r requirements.txt
}
Write-Host "Starting 한끼AI on http://$HostAddr`:$Port"
.\.venv\Scripts\python.exe -m uvicorn main:app --host $HostAddr --port $Port
