# Run ONNX service natively on Windows with DirectML support.
# This gives actual NPU/GPU acceleration via DirectML — not available in Linux containers.
#
# Prerequisites: Python 3.11+ on PATH
#
# Usage:
#   .\run_native.ps1
#   .\run_native.ps1 -ModelName phi3-mini-onnx
#   .\run_native.ps1 -Device cpu   (for testing without DirectML)
#
# After starting, the service is accessible at http://localhost:5006
# In docker-compose.dev.yml, change ollama_wrapper's ONNX_SERVICE_URL to:
#   http://host.docker.internal:5006

param(
    [string]$ModelName = "",
    [string]$Device = "dml",
    [int]$Port = 5006
)

$VenvPath = "$PSScriptRoot\.venv"
$PipExe = "$VenvPath\Scripts\pip.exe"
$UvicornExe = "$VenvPath\Scripts\uvicorn.exe"

# Create venv if it doesn't exist
if (-not (Test-Path $UvicornExe)) {
    Write-Host "Creating virtual environment at $VenvPath ..."
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create venv"; exit 1 }

    Write-Host "Installing base dependencies ..."
    & $PipExe install --no-cache-dir `
        fastapi "uvicorn[standard]" requests pydantic `
        "optimum>=1.19.0" `
        transformers>=4.40.0 `
        huggingface-hub>=0.22.0 `
        numpy>=1.26
    if ($LASTEXITCODE -ne 0) { Write-Error "Base install failed"; exit 1 }
}

# Install or upgrade onnxruntime-directml (mutually exclusive with onnxruntime)
Write-Host "Installing onnxruntime-directml ..."
& $PipExe install --no-cache-dir onnxruntime-directml --force-reinstall --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warning "onnxruntime-directml install failed. Falling back to onnxruntime (CPU)."
    & $PipExe install --no-cache-dir onnxruntime --force-reinstall --quiet
    $Device = "cpu"
}

# Create model storage dir
$ModelDir = "$PSScriptRoot\models"
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

$env:ONNX_MODEL_DIR = $ModelDir
$env:ONNX_DEVICE = $Device
$env:ONNX_MODEL_NAME = $ModelName
$env:PORT = "$Port"

Write-Host ""
Write-Host "Starting ONNX service on port $Port (device=$Device)"
if ($ModelName) { Write-Host "  Auto-loading model: $ModelName" }
Write-Host "  Model dir: $ModelDir"
Write-Host ""

Set-Location $PSScriptRoot
& $UvicornExe onnx_app:app --host 0.0.0.0 --port $Port
