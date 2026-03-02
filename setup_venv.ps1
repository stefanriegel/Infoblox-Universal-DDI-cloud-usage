# Setup Python virtual environment and install all dependencies
# Supports AWS, Azure, and GCP discovery
# This script is automatically signed by GitHub Actions for Windows compatibility

# CI compatibility: $ProviderChoice controls whether to skip interactive CLI prompts
param(
    [string]$ProviderChoice = ""
)

# --- Section: ExecutionPolicy Detection ---
# Check if execution is allowed before doing anything else
$machinePolicy = $null
$userPolicy = $null
try {
    $machinePolicy = (Get-ExecutionPolicy -Scope MachinePolicy -ErrorAction SilentlyContinue).ToString()
} catch { $machinePolicy = $null }
try {
    $userPolicy = (Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue).ToString()
} catch { $userPolicy = $null }

if ($machinePolicy -eq "Restricted") {
    Write-Host "[WARN] ExecutionPolicy is controlled by Group Policy." -ForegroundColor Yellow
    Write-Host "       Contact IT administrator." -ForegroundColor Yellow
    Write-Host "       See docs/enterprise-resign.md for enterprise signing guidance." -ForegroundColor Cyan
    # Script is already running if we get here, so just warn
}
elseif ($userPolicy -in @("Restricted", "Undefined", $null)) {
    Write-Host "[WARN] PowerShell ExecutionPolicy is '$userPolicy'." -ForegroundColor Yellow
    Write-Host "       Run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Cyan
}

Write-Host "================================" -ForegroundColor Cyan
Write-Host " Infoblox Universal DDI Setup Routine" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

# --- Section: Clean up old environment ---
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
Write-Host " Installing Dependencies" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

Write-Host "  - Installing all dependencies..." -ForegroundColor Green
python -m pip install -r requirements.txt
Write-Host "  - Installing package entry point..." -ForegroundColor Green
python -m pip install -e .

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Cloud CLI Detection" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

function Test-CLI($Name, $Command, $InstallUrl) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        Write-Host "[WARN] $Name CLI not found on PATH." -ForegroundColor Yellow
        if (-not $ProviderChoice) {
            $yn = Read-Host "  Open $Name CLI install page? (y/N)"
            if ($yn -match "^[Yy]$") {
                Start-Process $InstallUrl
            }
        } else {
            Write-Host "       Install: $InstallUrl" -ForegroundColor Cyan
        }
    } else {
        Write-Host "[OK]   $Name CLI found." -ForegroundColor Green
    }
}

Test-CLI "AWS"   "aws"    "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
Test-CLI "Azure" "az"     "https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows"
Test-CLI "GCP"   "gcloud" "https://cloud.google.com/sdk/docs/install"

Write-Host

# --- Section: Windows Long-Path Check ---
try {
    $longPath = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -ErrorAction Stop).LongPathsEnabled
    if ($longPath -ne 1) {
        Write-Host "[WARN] Windows long path support is disabled." -ForegroundColor Yellow
        Write-Host "       Run as Admin: New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1 -PropertyType DWORD -Force" -ForegroundColor Cyan
    } else {
        Write-Host "[OK]   Windows long path support is enabled." -ForegroundColor Green
    }
} catch {
    Write-Host "[WARN] Could not check long path support." -ForegroundColor Yellow
}

# --- Section: Port Check ---
$portCheck = Test-NetConnection -ComputerName localhost -Port 8080 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
if ($portCheck.TcpTestSucceeded) {
    Write-Host "[WARN] Port 8080 is already in use. Dashboard may need --port flag." -ForegroundColor Yellow
} else {
    Write-Host "[OK]   Port 8080 is available for web dashboard." -ForegroundColor Green
}

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Setup complete!" -ForegroundColor Green
Write-Host " To activate: & venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host
