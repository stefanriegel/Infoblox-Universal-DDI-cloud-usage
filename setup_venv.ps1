# Setup Python virtual environment and install dependencies for AWS, Azure, and GCP discovery

# --- Section: Clean up old environment ---
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Infoblox Universal DDI Setup Routine" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

if (Test-Path "venv") {
    Write-Host "[INFO] Removing existing virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force venv
    Write-Host
}

# --- Section: Create new environment ---
Write-Host "[INFO] Creating new Python virtual environment..." -ForegroundColor Green
python -m venv venv
& venv\Scripts\Activate.ps1

# --- Section: Upgrade pip ---
Write-Host "[INFO] Upgrading pip..." -ForegroundColor Green
python -m pip install --upgrade pip

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Provider Dependency Selection" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

Write-Host "Which provider dependencies do you want to install?"
Write-Host "  1) AWS"
Write-Host "  2) Azure"
Write-Host "  3) GCP"
Write-Host "  4) All"
Write-Host "---------------------------------"
Write-Host

$choice = Read-Host "Enter choice [1-4]"

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Installing Dependencies" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

switch ($choice) {
    "1" {
        Write-Host "  - Installing AWS dependencies..."
        python -m pip install -r aws_discovery/requirements.txt
    }
    "2" {
        Write-Host "  - Installing Azure dependencies..."
        python -m pip install -r azure_discovery/requirements.txt
    }
    "3" {
        Write-Host "  - Installing GCP dependencies..."
        python -m pip install -r gcp_discovery/requirements.txt
    }
    "4" {
        Write-Host "  - Installing AWS dependencies..."
        python -m pip install -r aws_discovery/requirements.txt
        Write-Host "  - Installing Azure dependencies..."
        python -m pip install -r azure_discovery/requirements.txt
        Write-Host "  - Installing GCP dependencies..."
        python -m pip install -r gcp_discovery/requirements.txt
    }
    default {
        Write-Host
        Write-Host "[ERROR] Invalid choice. Exiting." -ForegroundColor Red
        Write-Host
        exit 1
    }
}

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Setup complete!" -ForegroundColor Green
Write-Host " To activate: & venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host