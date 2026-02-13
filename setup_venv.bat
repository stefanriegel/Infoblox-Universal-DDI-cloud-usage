@echo off
REM Setup Python virtual environment and install dependencies for AWS, Azure, and GCP discovery
REM Batch file fallback for Windows when PowerShell execution is restricted

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
echo  Provider Dependency Selection
echo ================================
echo.

REM Provider selection (simplified - installs all by default)
echo Which provider dependencies do you want to install?
echo   1) AWS
echo   2) Azure
echo   3) GCP
echo   4) All (default)
echo ---------------------------------
echo.

set /p choice="Enter choice [1-4] or press Enter for All: "
if "%choice%"=="" set choice=4

echo.
echo ================================
echo  Installing Dependencies
echo ================================
echo.

REM Install common dependencies
echo   - Installing common dependencies...
python -m pip install tqdm pandas

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
    echo.
    echo [ERROR] Invalid choice: %choice%. Exiting.
    echo.
    exit /b 1
)

echo.
echo ================================
echo  Setup complete!
echo  To activate: venv\Scripts\activate.bat
echo ================================
echo.
pause