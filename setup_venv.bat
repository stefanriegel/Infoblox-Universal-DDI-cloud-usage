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
echo 3) Both AWS and Azure
echo.
set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" (
    echo Installing AWS module only...
    set modules=aws
) else if "%choice%"=="2" (
    echo Installing Azure module only...
    set modules=azure
) else if "%choice%"=="3" (
    echo Installing both AWS and Azure modules...
    set modules=aws azure
) else (
    echo Invalid choice. Please run the script again and select 1, 2, or 3.
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

REM Check AWS CLI version
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

REM Install common dependencies
echo Installing common dependencies...
pip install tqdm>=4.64.0 pandas>=1.5.0 scikit-learn>=1.3.0 matplotlib>=3.6.0 seaborn>=0.12.0

REM Install module-specific dependencies
for %%m in (%modules%) do (
    if "%%m"=="aws" (
        echo Installing AWS module dependencies...
        pip install boto3>=1.26.0
    ) else if "%%m"=="azure" (
        echo Installing Azure module dependencies...
        pip install azure-mgmt-compute>=30.0.0 azure-mgmt-network==29.0.0 azure-mgmt-resource>=23.0.0 azure-mgmt-monitor>=5.0.0 azure-identity>=1.12.0
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
echo   python main.py aws --format json
echo   python main.py azure --format json
echo.
echo   # Module-specific commands:
if "%modules%"=="aws" (
    echo   python aws_discovery\discover.py --format json
) else if "%modules%"=="azure" (
    echo   python azure_discovery\discover.py --format json
) else (
    echo   python aws_discovery\discover.py --format json
    echo   python azure_discovery\discover.py --format json
)
echo.
echo Note: The virtual environment must be activated in each new terminal session.
echo.
pause 