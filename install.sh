!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting simplified ROOT installation for Hey Cheryl..."
echo ""
echo "------------------------------------------------------------------"
echo " IMPORTANT: Prerequisites"
echo " Before running this script, ensure you have:"
echo " 1. Installed 'git' on the system."
echo " 2. Installed 'uv' for the 'root' user or globally."
echo "    Example: curl -LsSf https://astral.sh/uv/install.sh | sh (as root)"
echo "------------------------------------------------------------------"
echo ""

# --- Configuration ---

# Fixed installation directory
INSTALL_DIR="/opt/hey-cheryl"

# Git repository URL
REPO_URL="https://github.com/your-username/hey-cheryl.git" # <-- **UPDATE WITH YOUR REPO URL**

# --- Check for Root Privileges ---

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run this script with sudo or as the root user."
    exit 1
fi

# --- Check Prerequisites ---

if ! command -v git &> /dev/null; then
    echo "Error: git command not found. Please install git."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "Error: uv command not found. Please install uv (e.g., run 'curl -LsSf https://astral.sh/uv/install.sh | sh' as root)."
    exit 1
fi

# --- Clone Repository ---

echo "Cloning repository into ${INSTALL_DIR}..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory ${INSTALL_DIR} already exists. Skipping git clone. Ensure it contains the correct repo."
else
    if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
        echo "Error: Failed to clone repository from ${REPO_URL}"
        exit 1
    fi
fi

# --- Set up Virtual Environment and Install Dependencies (as root) ---

echo "Setting up venv and installing dependencies in ${INSTALL_DIR}..."
cd "$INSTALL_DIR" || exit 1 # Ensure we are in the app directory

echo "Creating virtual environment..."
uv venv .venv

echo "Activating virtual environment (for this script block)..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
uv sync --locked

echo "Deactivating virtual environment..."
deactivate

echo "Venv setup and dependency installation complete."


# --- Install and Configure Systemd Service ---

echo "Installing and configuring systemd service..."

# The service file is expected to be in deploy/hey-cheryl.service within the cloned repo
SERVICE_SRC="${INSTALL_DIR}/deploy/hey-cheryl.service"
SERVICE_DEST="/etc/systemd/system/hey-cheryl.service"

if [ ! -f "$SERVICE_SRC" ]; then
    echo "Error: Systemd service source file not found at ${SERVICE_SRC}"
    echo "Please ensure 'deploy/hey-cheryl.service' exists in the cloned repository."
    exit 1
fi

echo "Copying service file to ${SERVICE_DEST}..."
if ! cp "$SERVICE_SRC" "$SERVICE_DEST"; then
    echo "Error: Failed to copy service file to ${SERVICE_DEST}"
    exit 1
fi

echo "Configuring service file placeholders..."
# Only __APP_DIR__ needs to be substituted.
# User=root and Group=root are hardcoded in hey-cheryl.service
if ! sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$SERVICE_DEST"; then echo "Error substituting __APP_DIR__" && exit 1; fi


echo "Reloading systemd daemon..."
if ! systemctl daemon-reload; then
    echo "Error: Failed to reload systemd daemon."
    exit 1
fi

echo "Enabling hey-cheryl.service..."
if ! systemctl enable hey-cheryl.service; then
    echo "Error: Failed to enable hey-cheryl.service."
    exit 1
fi

echo "Starting hey-cheryl.service..."
if ! systemctl start hey-cheryl.service; then
    echo "Error: Failed to start hey-cheryl.service."
    echo "Please check service status and logs manually:"
    echo "  sudo systemctl status hey-cheryl.service"
    echo "  sudo journalctl -u hey-cheryl.service -f"
    exit 1
fi

echo ""
echo "------------------------------------------------------------------"
echo "Installation complete. Systemd service hey-cheryl.service should now be running as root."
echo "Check service status with: sudo systemctl status hey-cheryl.service"
echo "View logs with: sudo journalctl -u hey-cheryl.service -f"
echo "------------------------------------------------------------------"
echo ""