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
# eF2gggMiMIIDHjCCAgagAwIBAgIQMSfkT6/IhJtPqQN9FVtq1jANBgkqhkiG9w0B
# AQsFADAnMSUwIwYDVQQDDBxJbmZvYmxveCBVbml2ZXJzYWwgRERJIFNldHVwMB4X
# DTI2MDMwODE5NTIwOFoXDTI3MDMwODIwMDIwOFowJzElMCMGA1UEAwwcSW5mb2Js
# b3ggVW5pdmVyc2FsIERESSBTZXR1cDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCC
# AQoCggEBALln+Ak8C3ggPh6vthTxwc4b0c9nI0ooof3g7pBIs7uPGV4XZXido+F4
# qridE1NC7ppNYjhqaNskP/uR5ohsWzGZK0CI49F4RqjMpRwXxRwglEx7Rdq9BkBF
# c0zWipIrwI57XHTQeXlQrUpghPpqbYtGIzsnVoP4t4LnP3vK3lr5IyZoPRSs7Q5I
# onWH6R1nIlcUin9BpB9NbqK7yLvhNuXnNZDwxxJotFSli7MXgZHHERfncXPhzh+p
# MfV9AZcP+HKWVJHr7feZ37YiP5g2z5k94wv1nVButXDg3gCTwpf6zNZkgnl/d2vY
# 3LUIyeNzJx3ggh310SPQVd2nPz5SWEUCAwEAAaNGMEQwDgYDVR0PAQH/BAQDAgeA
# MBMGA1UdJQQMMAoGCCsGAQUFBwMDMB0GA1UdDgQWBBSV8N5wyr+gaMJDTwJrz0EW
# mvahAjANBgkqhkiG9w0BAQsFAAOCAQEAmnmnQEnz5JZ8Zp46TcWpIdmIiZklGxSl
# kDLIfIAHhDF7/b+v2UA/IK9vfxfgogL98Zm/SNDgit+wlilvqsTmxMliD2whFult
# U8JrGpEj0Z2wUM3vwBHO9CPZA7sC8Q/n2EROEKpLvC29NM9TuGytAERFgU5TZSdW
# CVkh0OGrFi3W+vGeOrwHnEOud2moEpwzt7xo6Vr2QALj7xh6B6N8AJrYZ6g7SfTD
# udqnOvIFT1Aq820n8Fi/sdc9DrEp81rqdbntJkSMThdcPAicEPDHALmNX7BHSKlI
# wL2IlkrXiATBsdy3CdOgU74ygsLESkLdUZ5oqm/fi+F/Ci/r6ZKYojGCAdwwggHY
# AgEBMDswJzElMCMGA1UEAwwcSW5mb2Jsb3ggVW5pdmVyc2FsIERESSBTZXR1cAIQ
# MSfkT6/IhJtPqQN9FVtq1jAJBgUrDgMCGgUAoHgwGAYKKwYBBAGCNwIBDDEKMAig
# AoAAoQKAADAZBgkqhkiG9w0BCQMxDAYKKwYBBAGCNwIBBDAcBgorBgEEAYI3AgEL
# MQ4wDAYKKwYBBAGCNwIBFTAjBgkqhkiG9w0BCQQxFgQUPOdHoEOAn7/vcVW+ud4T
# WXAe2hMwDQYJKoZIhvcNAQEBBQAEggEAOAL+uTRpQhyKbJKItk8LRBUFOpouZ+49
# X6mu38jDjqgUQmwBxJhN/s2L1bY/8cwqfcDIZdLKxcVnFy8KKOOYkxOvkQCJgF6s
# pdSiRYh7EuLVmt4JQDDy5ZgGj10wQhUdMf2R4MtujI561PlgsE8N45O/nMzIghKi
# pzIpg4Sy2I2xQF+5tcZvGPMPJ9JKU9I5JgywhuYCWx/9E676NskoauhV8WK2Aw29
# Qxkz1PBhA1s0VBvAKeUCHvKOmwkY2AbV3AIV8o/rCCvuEMpb3StTQrCsMrVVfSqx
# iqADHMsL5DpubbU8AY0ZN39d+0NOA32a/B3Mi8FTPsd39F5t0IkRPQ==
# SIG # End signature block
