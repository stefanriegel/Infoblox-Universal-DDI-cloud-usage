#!/bin/bash
# Setup Python virtual environment and install dependencies for AWS, Azure, and GCP discovery
set -e

# Check for non-interactive mode (CI)
PROVIDER_CHOICE="${1:-}"

# Helper function for centered echo
center_echo() {
  local text="$1"
  local width=40
  local pad=$(( (width - ${#text}) / 2 ))
  printf '#%*s%s%*s#\n' "$pad" '' "$text" "$((width - pad - ${#text}))" ''
}

# --- Section: Clean up old environment ---
echo "########################################"
center_echo "Infoblox Universal DDI Setup Routine"
echo "########################################"
echo

if [ -d "venv" ]; then
  echo "[INFO] Removing existing virtual environment..."
  rm -rf venv
  echo
fi

# --- Section: Create new environment ---
echo "[INFO] Creating new Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
echo

# --- Section: Upgrade pip ---
echo "[INFO] Upgrading pip..."
pip install --upgrade pip

echo
echo "########################################"
center_echo "Provider Dependency Selection"
echo "########################################"
echo

# Use parameter if provided (non-interactive mode)
if [ -n "$PROVIDER_CHOICE" ]; then
  choice="$PROVIDER_CHOICE"
  echo "Using provider choice from parameter: $choice"
else
  echo "Which provider dependencies do you want to install?"
  echo "  1) AWS"
  echo "  2) Azure"
  echo "  3) GCP"
  echo "  4) All"
  echo "----------------------------------------"
  echo
  read -p "Enter choice [1-4]: " choice
fi

echo

echo "########################################"
center_echo "Installing Dependencies"
echo "########################################"
echo

case $choice in
  1)
    echo "  - Installing AWS dependencies..."
    pip install -r aws_discovery/requirements.txt
    ;;
  2)
    echo "  - Installing Azure dependencies..."
    pip install -r azure_discovery/requirements.txt
    ;;
  3)
    echo "  - Installing GCP dependencies..."
    pip install -r gcp_discovery/requirements.txt
    ;;
  4)
    echo "  - Installing AWS dependencies..."
    pip install -r aws_discovery/requirements.txt
    echo "  - Installing Azure dependencies..."
    pip install -r azure_discovery/requirements.txt
    echo "  - Installing GCP dependencies..."
    pip install -r gcp_discovery/requirements.txt
    ;;
  *)
    echo
    echo "[ERROR] Invalid choice: $choice. Exiting."
    echo
    exit 1
    ;;
esac

echo

echo "########################################"
center_echo "Setup complete!"
center_echo "To activate: source venv/bin/activate"
echo "########################################"
echo 