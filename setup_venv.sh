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
echo "3) Both AWS and Azure"
echo ""
read -p "Enter your choice (1-3): " choice

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
        echo "Installing both AWS and Azure modules..."
        modules="aws azure"
        ;;
    *)
        echo "Invalid choice. Please run the script again and select 1, 2, or 3."
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

# Install common dependencies
echo "Installing common dependencies..."
pip install tqdm>=4.64.0 pandas>=1.5.0 scikit-learn>=1.3.0 matplotlib>=3.6.0 seaborn>=0.12.0

# Install module-specific dependencies
for module in $modules; do
    echo "Installing $module module dependencies..."
    if [ "$module" = "aws" ]; then
        pip install boto3>=1.26.0
    elif [ "$module" = "azure" ]; then
        pip install azure-mgmt-compute>=30.0.0 azure-mgmt-network==29.0.0 azure-mgmt-resource>=23.0.0 azure-mgmt-monitor>=5.0.0 azure-identity>=1.12.0
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
echo "  python main.py aws --format json"
echo "  python main.py azure --format json"
echo ""
echo "  # Module-specific commands:"
if [[ $modules == *"aws"* ]]; then
    echo "  python aws_discovery/discover.py --format json"
fi
if [[ $modules == *"azure"* ]]; then
    echo "  python azure_discovery/discover.py --format json"
fi
echo ""
echo "Note: The virtual environment must be activated in each new terminal session."
echo "" 