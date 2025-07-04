@echo off
REM Setup script for virtual environment (Windows 11)

echo Setting up virtual environment for Infoblox Universal DDI Management Token Calculator
echo ================================================================================

REM Check if Python 3 is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
echo Python version: %python_version%

REM Ask user which modules they want to install
echo.
echo Which modules would you like to install?
echo 1) AWS only
echo 2) Azure only
echo 3) GCP only
echo 4) All three (AWS, Azure, GCP)
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo Installing AWS module only...
    set modules=aws
) else if "%choice%"=="2" (
    echo Installing Azure module only...
    set modules=azure
) else if "%choice%"=="3" (
    echo Installing GCP module only...
    set modules=gcp
) else if "%choice%"=="4" (
    echo Installing all three modules (AWS, Azure, GCP)...
    set modules=aws azure gcp
) else (
    echo Invalid choice. Please run the script again and select 1-4.
    pause
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Check AWS CLI version (only if AWS module is selected)
if "%modules%"=="aws" (
    where aws >nul 2>nul
    if errorlevel 1 (
        echo ERROR: AWS CLI is not installed. Please install AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
        exit /b 1
    )
    for /f "tokens=2 delims=/" %%A in ('aws --version 2^>^&1 ^| findstr "aws-cli"') do set AWS_CLI_VERSION=%%A
    for /f "tokens=1 delims=." %%B in ("%AWS_CLI_VERSION%") do set AWS_CLI_MAJOR=%%B
    if "%AWS_CLI_MAJOR%" LSS "2" (
        echo ERROR: AWS CLI v2.0.0 or higher is required. Please install it from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
        exit /b 1
    )
)

REM Check Google Cloud SDK (only if GCP module is selected)
if "%modules%"=="gcp" (
    where gcloud >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Google Cloud SDK is not installed. Please install it from https://cloud.google.com/sdk/docs/install
        exit /b 1
    )
    echo Google Cloud SDK found
)

REM Install module-specific dependencies
for %%m in (%modules%) do (
    if "%%m"=="aws" (
        echo Installing AWS module dependencies...
        pip install -r aws_discovery\requirements.txt
    ) else if "%%m"=="azure" (
        echo Installing Azure module dependencies...
        pip install -r azure_discovery\requirements.txt
    ) else if "%%m"=="gcp" (
        echo Installing GCP module dependencies...
        pip install -r gcp_discovery\requirements.txt
    )
)

echo.
echo Virtual environment setup complete!
echo.
echo Installed modules: %modules%
echo.
echo IMPORTANT: You must activate the virtual environment before running the tool!
echo.
echo To activate the virtual environment:
echo   venv\Scripts\activate.bat
echo.
echo To deactivate:
echo   deactivate
echo.
echo To run discovery (after activating the virtual environment):
echo   # Main entry point (recommended):
if "%modules%"=="aws" (
    echo   python main.py aws --format json
) else if "%modules%"=="azure" (
    echo   python main.py azure --format json
) else if "%modules%"=="gcp" (
    echo   python main.py gcp --format json
) else (
    echo   python main.py aws --format json
    echo   python main.py azure --format json
    echo   python main.py gcp --format json
)
echo.
echo   # Module-specific commands:
if "%modules%"=="aws" (
    echo   python aws_discovery\discover.py --format json
) else if "%modules%"=="azure" (
    echo   python azure_discovery\discover.py --format json
) else if "%modules%"=="gcp" (
    echo   python gcp_discovery\discover.py --format json
) else (
    echo   python aws_discovery\discover.py --format json
    echo   python azure_discovery\discover.py --format json
    echo   python gcp_discovery\discover.py --format json
)
echo.
echo Note: The virtual environment must be activated in each new terminal session.
echo.
pause 