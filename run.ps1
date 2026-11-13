# One-click setup and run for Windows PowerShell.
# Usage:  powershell -ExecutionPolicy Bypass -File run.ps1
#         powershell -ExecutionPolicy Bypass -File run.ps1 -Port 8001     (if 8000 is busy)
param([int]$Port = 8000)
Set-Location $PSScriptRoot
$py = ".\venv\Scripts\python.exe"

if (-not (Test-Path "venv")) { python -m venv venv }
& $py -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Installing the libraries failed. See the message above." -ForegroundColor Red; exit 1 }

if (-not (Test-Path "data\raw\Steel_industry_data.csv")) {
    Write-Host "Missing data\raw\Steel_industry_data.csv. Copy the CSV there and run this again." -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path "models\energy_model.joblib")) {
    & $py train.py
    if ($LASTEXITCODE -ne 0) { Write-Host "Training failed. See the message above." -ForegroundColor Red; exit 1 }
}
& $py app\kg_build.py

Write-Host "Starting CircuLoop at http://127.0.0.1:$Port  (Ctrl+C to stop)" -ForegroundColor Green
& $py -m uvicorn main:app --app-dir app --port $Port
