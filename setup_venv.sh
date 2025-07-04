#!/bin/bash
# Setup script for virtual environment (macOS/Linux)

echo "Setting up virtual environment for Infoblox Universal DDI Management Token Calculator"
echo "================================================================================"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python version: $python_version"

# Ask user which modules they want to install
echo ""
echo "Which modules would you like to install?"
echo "1) AWS only"
echo "2) Azure only"
echo "3) GCP only"
echo "4) All three (AWS, Azure, GCP)"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo "Installing AWS module only..."
        modules="aws"
        ;;
    2)
        echo "Installing Azure module only..."
        modules="azure"
        ;;
    3)
        echo "Installing GCP module only..."
        modules="gcp"
        ;;
    4)
        echo "Installing all three modules (AWS, Azure, GCP)..."
        modules="aws azure gcp"
        ;;
    *)
        echo "Invalid choice. Please run the script again and select 1-4."
        exit 1
        ;;
esac

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Check AWS CLI version (only if AWS module is selected)
if [[ $modules == *"aws"* ]]; then
    if command -v aws &> /dev/null; then
        AWS_CLI_VERSION=$(aws --version 2>&1 | grep -o 'aws-cli/[0-9.]*' | cut -d/ -f2)
        AWS_CLI_MAJOR=$(echo $AWS_CLI_VERSION | cut -d. -f1)
        if [ -z "$AWS_CLI_VERSION" ] || [ "$AWS_CLI_MAJOR" -lt 2 ]; then
            echo "ERROR: AWS CLI v2.0.0 or higher is required. Please install it from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
            exit 1
        fi
    else
        echo "ERROR: AWS CLI is not installed. Please install AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi
fi

# Check Google Cloud SDK (only if GCP module is selected)
if [[ $modules == *"gcp"* ]]; then
    if ! command -v gcloud &> /dev/null; then
        echo "ERROR: Google Cloud SDK is not installed. Please install it from https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    echo "Google Cloud SDK found: $(gcloud --version | head -1)"
fi

# Install module-specific dependencies
for module in $modules; do
    echo "Installing $module module dependencies..."
    if [ "$module" = "aws" ]; then
        pip install -r aws_discovery/requirements.txt
    elif [ "$module" = "azure" ]; then
        pip install -r azure_discovery/requirements.txt
    elif [ "$module" = "gcp" ]; then
        pip install -r gcp_discovery/requirements.txt
    fi
done

echo ""
echo "Virtual environment setup complete!"
echo ""
echo "Installed modules: $modules"
echo ""
echo "IMPORTANT: You must activate the virtual environment before running the tool!"
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate:"
echo "  deactivate"
echo ""
echo "To run discovery (after activating the virtual environment):"
echo "  # Main entry point (recommended):"
if [[ $modules == *"aws"* ]]; then
    echo "  python main.py aws --format json"
fi
if [[ $modules == *"azure"* ]]; then
    echo "  python main.py azure --format json"
fi
if [[ $modules == *"gcp"* ]]; then
    echo "  python main.py gcp --format json"
fi
echo ""
echo "  # Module-specific commands:"
if [[ $modules == *"aws"* ]]; then
    echo "  python aws_discovery/discover.py --format json"
fi
if [[ $modules == *"azure"* ]]; then
    echo "  python azure_discovery/discover.py --format json"
fi
if [[ $modules == *"gcp"* ]]; then
    echo "  python gcp_discovery/discover.py --format json"
fi
echo ""
echo "Note: The virtual environment must be activated in each new terminal session."
echo "" 