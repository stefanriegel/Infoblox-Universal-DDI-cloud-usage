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
# AgEAAgEAAgEAAgEAAgEAMCEwCQYFKw4DAhoFAAQUk0sxD8oy1Ax7Myn0dKPKcFdu
# eF2gggMiMIIDHjCCAgagAwIBAgIQHM6pXGLCRaVCRRwoec87YDANBgkqhkiG9w0B
# AQsFADAnMSUwIwYDVQQDDBxJbmZvYmxveCBVbml2ZXJzYWwgRERJIFNldHVwMB4X
# DTI2MDIxOTE5NTg1NloXDTI3MDIxOTIwMDg1NlowJzElMCMGA1UEAwwcSW5mb2Js
# b3ggVW5pdmVyc2FsIERESSBTZXR1cDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCC
# AQoCggEBAJlc4GfpNX2jdQI3fZoH+RWvPvzOS7thXslqpzTafda7gC+kUKoKLYH4
# bvL0M1rzlzPnKz2Txczj6zeVz7x/1/NO/cbWzeohyBoXbweD8mQUQlGXUsaGGg9f
# Ri6ujlOq3BugqdxEduKkxYSBrEfENzAPcZkjq2DYN8AAA/twIIkMUZ0Ct1ljsD36
# fjiTgeFXwZ71LD4TyDb275MAVTkgmKBDLMg4/jZ2ppXDlvbjAI2OBM3Xh1C93Qru
# a+o0nZpotGXXp1dwKXoQfAZWu5gHwuS1ArRKMnGSsoE6vVIGHKNVCnoHGxW9X1y3
# m3F4ADZLPd9/Tv7ydH80rybPn5NMSlECAwEAAaNGMEQwDgYDVR0PAQH/BAQDAgeA
# MBMGA1UdJQQMMAoGCCsGAQUFBwMDMB0GA1UdDgQWBBRnjjxy6I1yZiQ1ldB6Hg/x
# xtWOrjANBgkqhkiG9w0BAQsFAAOCAQEATqKJZe5VO651t01t+BJt91lxQTc8Pqhu
# DIv0ldUHi4pQ2xnD+a+3ZN1BIO7L49tyLsalaoaUga2yb+hMAJVKG1jxZwEFkHnG
# qrbivuV8iRlbFky5TcCPWQ1znX4KYlUnTXdAb2dQk81FTkmVWjzDQt84i33tdXqw
# URTrJzIUqXnHjr5VOprMjibZaoTZstPcU1LApkWrPIk2VRucXXNP1wc4cjyRDvwS
# cSVemShQb73rCPZjej7XDg+dNNKiegKck3StIReuMxsQYou0SrCq6C3Ic/tXrWc5
# DzikT0Zs2fjcp4burWgNCDgp9s6frgI5U4s6nltcJDZnQGqEAyG5PzGCAdwwggHY
# AgEBMDswJzElMCMGA1UEAwwcSW5mb2Jsb3ggVW5pdmVyc2FsIERESSBTZXR1cAIQ
# HM6pXGLCRaVCRRwoec87YDAJBgUrDgMCGgUAoHgwGAYKKwYBBAGCNwIBDDEKMAig
# AoAAoQKAADAZBgkqhkiG9w0BCQMxDAYKKwYBBAGCNwIBBDAcBgorBgEEAYI3AgEL
# MQ4wDAYKKwYBBAGCNwIBFTAjBgkqhkiG9w0BCQQxFgQUPOdHoEOAn7/vcVW+ud4T
# WXAe2hMwDQYJKoZIhvcNAQEBBQAEggEAQPPHaF3yxbHFvbreO3sXVwe5VCKK4dz+
# VkTY+KBdwhUrqR9o9UJ380RkQ6+A/RmwcGSYEbh84CfE+JxfDpy+KY8Ikz/9FMSP
# fdpr0ebHrtbCewHVoiuO28j91+x+yYG7L30x0ahaZSEF8euxLBkGCOLfKEkiR4Ez
# LcRQf9W8nilkA5YZ48lX2WlXRYxmR6WKdEnpoknfy2mMSY3r43tAKam68WiQPMcr
# WQJbj0g2ysbPfX/uEG/5qDOvx7xdGMamXjhtoXE19nn28BnVIPS9RKDSuHvXiuHL
# 8hPc3K2FIuHPt3od+m0rrT4fbsoO91xj5rfkbqi4XHdDA6enDcDMQg==
# SIG # End signature block
