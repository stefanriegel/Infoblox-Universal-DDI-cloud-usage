# Setup Python virtual environment and install dependencies for AWS, Azure, and GCP discovery
# This script is automatically signed by GitHub Actions for Windows compatibility

# Check for non-interactive mode (CI) - accept parameter
param(
    [string]$ProviderChoice = ""
)

# --- Section: Find Python 3.11+ ---
$script:PythonCmd = $null
$script:PythonVersion = $null

# Try candidates: py launcher (Windows standard), then python3, then python
$candidates = @("py", "python3", "python")
foreach ($cmd in $candidates) {
    try {
        if ($cmd -eq "py") {
            # Windows py launcher: try highest 3.x version
            $ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver) {
                $parts = $ver.Split('.')
                if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
                    $script:PythonCmd = "py -3"
                    $script:PythonVersion = $ver
                    break
                }
            }
        } else {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver) {
                $parts = $ver.Split('.')
                if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
                    $script:PythonCmd = $cmd
                    $script:PythonVersion = $ver
                    break
                }
            }
        }
    } catch {}
}

if (-not $script:PythonCmd) {
    Write-Host "[ERROR] No Python 3.11+ found. Searched: py launcher, python3, python" -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Using $($script:PythonCmd) (Python $($script:PythonVersion))" -ForegroundColor Green
Write-Host

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
Write-Host "[INFO] Creating new Python virtual environment using $($script:PythonCmd)..." -ForegroundColor Green
if ($script:PythonCmd -eq "py -3") {
    & py -3 -m venv venv
} else {
    & $script:PythonCmd -m venv venv
}
& venv\Scripts\Activate.ps1

# --- Section: Upgrade pip ---
Write-Host "[INFO] Upgrading pip..." -ForegroundColor Green
python -m pip install --upgrade pip

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Provider Dependency Selection" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

# Use parameter if provided (non-interactive mode)
if ($ProviderChoice) {
    $choice = $ProviderChoice
    Write-Host "Using provider choice from parameter: $choice" -ForegroundColor Yellow
} else {
    Write-Host "Which provider dependencies do you want to install?"
    Write-Host "  1) AWS"
    Write-Host "  2) Azure"
    Write-Host "  3) GCP"
    Write-Host "  4) All"
    Write-Host "---------------------------------"
    Write-Host

    $choice = Read-Host "Enter choice [1-4]"
}

Write-Host
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Installing Dependencies" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host

# Install common dependencies
Write-Host "  - Installing common dependencies..."
python -m pip install tqdm pandas

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
        Write-Host "[ERROR] Invalid choice: $choice. Exiting." -ForegroundColor Red
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
# SIG # Begin signature block
# MIIFlAYJKoZIhvcNAQcCoIIFhTCCBYECAQExCzAJBgUrDgMCGgUAMGkGCisGAQQB
# gjcCAQSgWzBZMDQGCisGAQQBgjcCAR4wJgIDAQAABBAfzDtgWUsITrck0sYpfvNR
# AgEAAgEAAgEAAgEAAgEAMCEwCQYFKw4DAhoFAAQUPXw5oEAB2j/V3bFPVOa/cmXj
# iyKgggMiMIIDHjCCAgagAwIBAgIQaIeb1n1GY7lCgwHrU45WAzANBgkqhkiG9w0B
# AQsFADAnMSUwIwYDVQQDDBxJbmZvYmxveCBVbml2ZXJzYWwgRERJIFNldHVwMB4X
# DTI1MTIxMjE0MzQwNFoXDTI2MTIxMjE0NDQwNFowJzElMCMGA1UEAwwcSW5mb2Js
# b3ggVW5pdmVyc2FsIERESSBTZXR1cDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCC
# AQoCggEBANWQUeoa8jhos3BmkssRryZA36iGme+1U4gM9v65TJfflp+OXiC5IzvL
# /81G1Vawd/s8mIXKr/MELY0aSVSXhlgz3vl3Brz0JYhtVW5TDxG6dTdVwLMcPdr8
# bL3HYsSPYyT8boR4MmVTo83t9OzIiIC7lyhr7CXpCtAcgtLok2DpHQBHg0xPCs+O
# YM7unK+EtuzP7HIr2DuDj9WJBGsx/rQJA/W/qH9PPjeSlN+TrKzjV3hiLRTMLn/D
# ZSm2xdhb73r94AOLT5IOi2Fh5TZGL8IkgSCxHdNlECcTrZt2CiZJP3ifr7ZfzlGD
# LdGueBbIIi1rafh6FQEajO8ZpyPBIHkCAwEAAaNGMEQwDgYDVR0PAQH/BAQDAgeA
# MBMGA1UdJQQMMAoGCCsGAQUFBwMDMB0GA1UdDgQWBBToPoyj6c7P/uztUJN4d68q
# CP3KEjANBgkqhkiG9w0BAQsFAAOCAQEAMPVRwRNR/TtTQLjPgA3HpWrPhBPg5agY
# 8VkG5lM9UfOpV9b7lPTLZf0lwZw8epiQKLeKpGqVTEGabkT1IWMUXebBSWUlluq3
# waC617Lh6T9g6HipgZI6kkI9Erp5YHKv6uPBsXrLNiMo4tSnuvZYlO99QWGlDLGU
# v/gdo7jXDzMctEpfg/FyV/oCVu0NImEMPAkqIC2rkNvfMAvopmZLowNIyZNAV2Is
# PcUoc7d4ZNax6vUXLAVfAJaM78//F5fp8g8RykI5lEw38XTLzzCF9snIDpAuOm5Z
# fCzH1GK03It8BIujHOqCkrOOqngO7YFfk13eOBEdnlh8bBIfRfgrpjGCAdwwggHY
# AgEBMDswJzElMCMGA1UEAwwcSW5mb2Jsb3ggVW5pdmVyc2FsIERESSBTZXR1cAIQ
# aIeb1n1GY7lCgwHrU45WAzAJBgUrDgMCGgUAoHgwGAYKKwYBBAGCNwIBDDEKMAig
# AoAAoQKAADAZBgkqhkiG9w0BCQMxDAYKKwYBBAGCNwIBBDAcBgorBgEEAYI3AgEL
# MQ4wDAYKKwYBBAGCNwIBFTAjBgkqhkiG9w0BCQQxFgQUsrJViNt5X8mJCJ7CiTDP
# divzs7cwDQYJKoZIhvcNAQEBBQAEggEAEllkqGiwcqD2E+1hd/JMd76zRzDP0zUR
# bZuKC4t0VAD8sGNNvPinzYJFmR4sGyJAv8QgbCvgNf4pkLVVEKHiH9NMS/KFhhnZ
# KqeEPtubPL2tO6FZQi1UDPmDj1TaUwMtjC+DQomOOp8xu9maQyT9BXFQt/qymk0D
# rQrDlyztZZ6CXlxle0KYEqH+rihpJRtJYNXlNcvwYHFMnxqWr+mygXNFNy2PnSmP
# E/i1lnTnS1B8bw5+/DuVL4z5t3y3nhzLQw6dSBvyWSesbHkvCuiw7Ky702g8BK6v
# 2mzoWa8XmXiFUlCZSEg3VkC24Xiw3K9Yzfh0lcMIzkOrFAO399I7Ig==
# SIG # End signature block
