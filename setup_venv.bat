@echo off
REM Setup Python virtual environment and install all dependencies
REM Batch file fallback for Windows when PowerShell execution is restricted
REM For full features (CLI detection with prompts, long-path check), use setup_venv.ps1

echo ================================
echo  Infoblox Universal DDI Setup Routine
echo ================================
echo.

REM --- Section: Clean up old environment ---
if exist "venv" (
    echo [INFO] Removing existing virtual environment...
    rmdir /s /q venv
    echo.
)

REM --- Section: Create new environment ---
echo [INFO] Creating new Python virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

REM --- Section: Upgrade pip ---
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo ================================
echo  Installing Dependencies
echo ================================
echo.

echo   - Installing all dependencies...
python -m pip install -r requirements.txt
echo   - Installing package entry point...
python -m pip install -e .

echo.
echo ================================
echo  Cloud CLI Detection
echo ================================
echo.

where aws >nul 2>&1 && (echo [OK]   AWS CLI found.) || (echo [WARN] AWS CLI not found.)
where az >nul 2>&1 && (echo [OK]   Azure CLI found.) || (echo [WARN] Azure CLI not found.)
where gcloud >nul 2>&1 && (echo [OK]   GCP CLI found.) || (echo [WARN] GCP CLI not found.)

echo.
echo ================================
echo  Setup complete!
echo  To activate: venv\Scripts\activate.bat
echo  For full features, use setup_venv.ps1
echo ================================
echo.
pause
