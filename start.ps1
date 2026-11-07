<#
  Grupo 1 Attendance - start everything with one command.

    .\start.bat                (double-click also works)
    .\start.bat -Port 8502     (use another port)

  Same as `streamlit run App.py`, plus a few checks first. The app itself starts
  Docker Desktop, Kafka and Spark in the background (see src/streaming/infrastructure.py);
  progress is shown on the admin Dashboard.
#>
param([int]$Port = 8501)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

function Fail($text) { Write-Host ""; Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Fail "Python is not installed or not on PATH." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: Docker is not installed - the app runs, but Kafka/Spark analytics will be offline." -ForegroundColor Yellow
}

python -c "import streamlit, kafka, plotly, qrcode" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Python packages (requirements.txt)..."
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }
}

$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $proc = Get-Process -Id ($busy | Select-Object -First 1).OwningProcess -ErrorAction SilentlyContinue
    Fail "Port $Port is already used by '$($proc.ProcessName)' (PID $($proc.Id)). Close the other app or run: .\start.bat -Port 8502"
}

$lan = (python -c "from src.core.config import lan_ip; print(lan_ip())" 2>$null)
if (-not $lan) { $lan = "localhost" }
Write-Host ""
Write-Host "  Admin (this laptop)   : http://localhost:$Port/admin"
Write-Host "  Students (same Wi-Fi) : http://${lan}:$Port   (use the QR codes on Classes & Links)"
Write-Host "  Kafka UI / Spark UI   : http://localhost:8085  /  http://localhost:4040"
Write-Host "  Docker, Kafka and Spark start automatically in the background."
Write-Host ""

python -m streamlit run App.py --server.port $Port
