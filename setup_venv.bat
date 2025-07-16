@echo off
REM Setup Python virtual environment and install dependencies for AWS, Azure, and GCP discovery

REM --- Section: Clean up old environment ---
echo ===============================
echo  Infoblox Universal DDI Setup Routine
echo ===============================

IF EXIST venv (
    echo [INFO] Removing existing virtual environment...
    rmdir /s /q venv
)

REM --- Section: Create new environment ---
echo [INFO] Creating new Python virtual environment...
python -m venv venv
call venv\Scripts\activate

REM --- Section: Upgrade pip ---
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Which provider dependencies do you want to install?
echo   1^) AWS
echo   2^) Azure
echo   3^) GCP
echo   4^) All
echo ---------------------------------
set /p choice="Enter choice [1-4]: "

echo.
echo [INFO] Installing dependencies...
if "%choice%"=="1" (
    echo   - Installing AWS dependencies...
    python -m pip install -r aws_discovery/requirements.txt
) else if "%choice%"=="2" (
    echo   - Installing Azure dependencies...
    python -m pip install -r azure_discovery/requirements.txt
) else if "%choice%"=="3" (
    echo   - Installing GCP dependencies...
    python -m pip install -r gcp_discovery/requirements.txt
) else if "%choice%"=="4" (
    echo   - Installing AWS dependencies...
    python -m pip install -r aws_discovery/requirements.txt
    echo   - Installing Azure dependencies...
    python -m pip install -r azure_discovery/requirements.txt
    echo   - Installing GCP dependencies...
    python -m pip install -r gcp_discovery/requirements.txt
) else (
    echo [ERROR] Invalid choice. Exiting.
    exit /b 1
)

echo.
echo ===============================
echo  Setup complete!
echo  To activate: call venv\Scripts\activate
echo =============================== 