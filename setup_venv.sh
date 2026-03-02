#!/bin/bash
# Setup Python virtual environment and install all dependencies
# Supports AWS, Azure, and GCP discovery
set -e

# Parameter: if set to "4" or "all", skip interactive CLI prompts (CI mode)
PROVIDER_CHOICE="${1:-}"

# Helper function for centered echo
center_echo() {
  local text="$1"
  local width=40
  local pad=$(( (width - ${#text}) / 2 ))
  printf '#%*s%s%*s#\n' "$pad" '' "$text" "$((width - pad - ${#text}))" ''
}

# --- Section: Banner ---
echo "########################################"
center_echo "Infoblox Universal DDI Setup Routine"
echo "########################################"
echo

# --- Section: Clean up old environment ---
if [ -d "venv" ]; then
  echo "[INFO] Removing existing virtual environment..."
  rm -rf venv
  echo
fi

# --- Section: Create new environment ---
echo "[INFO] Creating new Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo

# --- Section: Upgrade pip ---
echo "[INFO] Upgrading pip..."
pip install --upgrade pip

echo
echo "########################################"
center_echo "Installing Dependencies"
echo "########################################"
echo

echo "  - Installing all dependencies..."
pip install -r requirements.txt
echo "  - Installing package entry point..."
pip install -e .

echo
echo "########################################"
center_echo "Cloud CLI Detection"
echo "########################################"
echo

check_cli() {
  local name=$1 cmd=$2 install_url=$3
  if command -v "$cmd" &>/dev/null; then
    echo "[OK]   $name CLI found: $(command -v "$cmd")"
  else
    echo "[WARN] $name CLI not found on PATH."
    echo "       Install: $install_url"
  fi
}

check_cli "AWS"   "aws"    "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
check_cli "Azure" "az"     "https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
check_cli "GCP"   "gcloud" "https://cloud.google.com/sdk/docs/install"

echo

# --- Section: Port check ---
if command -v lsof &>/dev/null; then
  if lsof -i :8080 &>/dev/null; then
    echo "[WARN] Port 8080 is already in use. Dashboard may need --port flag."
  else
    echo "[OK]   Port 8080 is available for web dashboard."
  fi
fi

echo
echo "########################################"
center_echo "Setup complete!"
center_echo "To activate: source venv/bin/activate"
echo "########################################"
echo
