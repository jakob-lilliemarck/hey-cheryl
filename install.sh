#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting simplified ROOT installation for Hey Cheryl..."
echo "------------------------------------------------------------------"
echo " IMPORTANT: Prerequisites"
echo " 1. Installed 'git' on the system."
echo " 2. Installed 'uv' for the 'root' user or globally."
echo "    Example: curl -LsSf https://astral.sh/uv/install.sh | sh (as root)"
echo "------------------------------------------------------------------"

# --- Configuration ---
INSTALL_DIR="/opt/hey-cheryl"
REPO_URL="https://github.com/your-username/hey-cheryl.git" # <-- **UPDATE WITH YOUR REPO URL**

# --- Check for Root Privileges & Prerequisites ---
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run this script with sudo or as the root user."
    exit 1
fi
if ! command -v git &> /dev/null; then
    echo "Error: git command not found. Please install git."
    exit 1
fi
if ! command -v uv &> /dev/null; then
    echo "Error: uv command not found. Please install uv for root."
    exit 1
fi

# --- Clone Repository ---
echo "Cloning repository into ${INSTALL_DIR}..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory ${INSTALL_DIR} already exists. Assuming it's the correct repo."
else
    if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
        echo "Error: Failed to clone repository from ${REPO_URL}"
        exit 1
    fi
fi

# --- Set up Virtual Environment and Install Dependencies (as root) ---
echo "Setting up venv and installing dependencies in ${INSTALL_DIR}..."
cd "$INSTALL_DIR" || exit 1

echo "Creating/updating virtual environment..."
uv venv .venv # uv venv is idempotent

echo "Installing dependencies into .venv..."
(
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv sync --locked
)

echo "Venv setup and dependency installation complete."

# --- Install and Configure Systemd Service ---
echo "Updating and configuring systemd service..."

SERVICE_NAME="hey-cheryl.service"
SERVICE_SRC="${INSTALL_DIR}/deploy/${SERVICE_NAME}"
SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}"

echo "Attempting to stop and disable ${SERVICE_NAME}..."
systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
systemctl disable "${SERVICE_NAME}" >/dev/null 2>&1 || true

if [ ! -f "$SERVICE_SRC" ]; then
    echo "Error: Systemd service source file not found at ${SERVICE_SRC}"
    exit 1
fi

echo "Copying updated service file to ${SERVICE_DEST}..."
if ! cp "$SERVICE_SRC" "$SERVICE_DEST"; then
    echo "Error: Failed to copy service file to ${SERVICE_DEST}"
    exit 1
fi

echo "Configuring service file placeholders in ${SERVICE_DEST}..."
if ! sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$SERVICE_DEST"; then
    echo "Error substituting __APP_DIR__ in ${SERVICE_DEST}"
    exit 1
fi

echo "Reloading systemd daemon..."
if ! systemctl daemon-reload; then
    echo "Error: Failed to reload systemd daemon."
    exit 1
fi

echo "Enabling ${SERVICE_NAME}..."
if ! systemctl enable "${SERVICE_NAME}"; then
    echo "Error: Failed to enable ${SERVICE_NAME}."
    exit 1
fi

echo "Starting ${SERVICE_NAME}..."
if ! systemctl start "${SERVICE_NAME}"; then
    echo "Error: Failed to start ${SERVICE_NAME}."
    echo "Please check service status and logs manually:"
    echo "  sudo systemctl status ${SERVICE_NAME}"
    echo "  sudo journalctl -u ${SERVICE_NAME} -f"
    exit 1
fi

echo "------------------------------------------------------------------"
echo "Installation complete. Systemd service ${SERVICE_NAME} should now be running as root."
echo "Check status: sudo systemctl status ${SERVICE_NAME}"
echo "View logs: sudo journalctl -u ${SERVICE_NAME} -f"
echo "------------------------------------------------------------------"