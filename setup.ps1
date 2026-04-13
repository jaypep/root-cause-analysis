# Root Cause Analysis — Windows setup script
# Run from the project root: .\setup.ps1

$ErrorActionPreference = "Stop"

function Prompt-YN ($msg) {
    $r = Read-Host "$msg [y/N]"
    return $r -match '^[Yy]$'
}

Write-Host ""
Write-Host "=== Root Cause Analysis Setup ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Find Python ────────────────────────────────────────────────────────────
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 12)) {
                $python = $cmd
                Write-Host "[OK] Found $ver ($cmd)" -ForegroundColor Green
                break
            } else {
                Write-Host "[WARN] Found $ver but Python 3.12+ is required." -ForegroundColor Yellow
            }
        }
    } catch { }
}

if (-not $python) {
    Write-Host ""
    Write-Host "[ERROR] Python 3.12 or newer not found on PATH." -ForegroundColor Red
    Write-Host "Download it from https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

# ── 2. Virtual environment ────────────────────────────────────────────────────
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "[OK] Virtual environment already exists." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "No virtual environment found."
    if (Prompt-YN "Create one now?") {
        Write-Host "Creating venv..." -ForegroundColor Cyan
        & $python -m venv venv
        Write-Host "[OK] venv created." -ForegroundColor Green
    } else {
        Write-Host "Skipping venv creation. Dependencies will be installed globally." -ForegroundColor Yellow
    }
}

# Activate if venv exists
$pip = "pip"
$uvicorn = "uvicorn"
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
    $pip = "venv\Scripts\pip.exe"
    $uvicorn = "venv\Scripts\uvicorn.exe"
    Write-Host "[OK] Virtual environment activated." -ForegroundColor Green
}

# ── 3. Install dependencies ───────────────────────────────────────────────────
Write-Host ""
$installed = & $pip freeze 2>&1

# Quick check: are all three packages already present?
$needsInstall = -not (
    ($installed -match "fastapi") -and
    ($installed -match "uvicorn") -and
    ($installed -match "pydantic")
)

if (-not $needsInstall) {
    Write-Host "[OK] Dependencies already installed." -ForegroundColor Green
} else {
    Write-Host "Missing one or more dependencies (fastapi, uvicorn, pydantic)."
    if (Prompt-YN "Install from requirements.txt now?") {
        Write-Host "Installing..." -ForegroundColor Cyan
        & $pip install -r requirements.txt
        Write-Host "[OK] Dependencies installed." -ForegroundColor Green
    } else {
        Write-Host "[WARN] Skipping install. The app may not start correctly." -ForegroundColor Yellow
    }
}

# ── 4. Start the app ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""

$hostAll = Prompt-YN "Bind to 0.0.0.0 so other devices on your network can connect?"
$hostFlag = if ($hostAll) { "0.0.0.0" } else { "127.0.0.1" }

if (Prompt-YN "Start the app now?") {
    Write-Host ""
    if ($hostAll) {
        # Show local IP to make it easy to connect from other devices
        $ip = (Get-NetIPAddress -AddressFamily IPv4 |
               Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -notmatch "^169" } |
               Select-Object -First 1).IPAddress
        if ($ip) {
            Write-Host "Other devices on your network can connect at: http://${ip}:8000" -ForegroundColor Cyan
        }
    }
    Write-Host "Starting app at http://${hostFlag}:8000 — press Ctrl+C to stop." -ForegroundColor Cyan
    Write-Host ""
    & $uvicorn main:app --host $hostFlag --port 8000 --reload
}
