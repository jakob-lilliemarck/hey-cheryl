#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting installation..."

# --- Determine Installation Paths and User ---

# Determine the absolute path to the application directory
# If an argument is provided, use it; otherwise, use the current directory
if [ -n "$1" ]; then
  # Convert relative path to absolute path if necessary
  INSTALL_DIR="$(realpath "$1")"
else
  INSTALL_DIR="$(pwd)"
fi

# Get the user running the script (will be used for the service User/Group)
# whoami needs to be run by the *target* user if installing as root for another user
# A safer approach might be to take the target user as an argument, but for simplicity,
# we'll assume the user who will run the service is the user who will eventually own
# the application files and have permissions to the venv after git clone/etc.
# When run with sudo, $USER will be the sudo user, whoami will be the target user.
# Let's explicitly use the sudo user if available, otherwise whoami
if [ -n "$SUDO_USER" ]; then
  RUN_USER="$SUDO_USER"
else
  RUN_USER="$(whoami)"
fi


# Determine the path to the virtual environment bin directory
VENV_BIN_DIR="${INSTALL_DIR}/.venv/bin"

# Define source and destination paths for the systemd service file
SERVICE_SRC="${INSTALL_DIR}/deploy/hey-cheryl.service"
SERVICE_DEST="/etc/systemd/system/hey-cheryl.service"

# --- Check for Root Privileges ---

# Ensure the script is run as root for systemctl and file operations in /etc
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script with sudo or as the root user."
    exit 1
fi

# --- Install uv and Dependencies ---

# Install uv
echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ensure the uv executable is in the PATH for the current script
# uv is often installed via cargo, so add the default cargo bin directory to PATH
# Note: This primarily affects the script's execution, service will use VENV_BIN_DIR in PATH
export PATH="$HOME/.cargo/bin:$PATH"

# Check if the uv executable is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv command not found after installation attempt. Please check the installation."
    exit 1
fi


echo "Creating virtual environment in ${INSTALL_DIR}/.venv..."
# Create a virtual environment named .venv in the application directory
# Use the full path to uv to ensure it's found regardless of PATH export timing
uv venv "${INSTALL_DIR}/.venv"

echo "Activating virtual environment..."
# Activate the virtual environment for dependency installation
# Use the full path to the activate script
source "${INSTALL_DIR}/.venv/bin/activate"

echo "Installing dependencies with uv sync..."
# Navigate to the install directory before running uv sync to ensure pyproject.toml is found
pushd "$INSTALL_DIR" > /dev/null
uv sync --locked
popd > /dev/null # Return to the original directory

echo "Deactivating virtual environment..."
# Check if deactivate function exists before calling it
if command -v deactivate &> /dev/null; then
  deactivate # Deactivate the virtual environment
else
  echo "Deactivate command not found, skipping deactivation."
fi


# --- Install and Configure Systemd Service ---

echo "Installing and configuring systemd service..."

# Check if the source service file exists
if [ ! -f "$SERVICE_SRC" ]; then
    echo "Error: Systemd service source file not found at ${SERVICE_SRC}"
    echo "Please ensure 'deploy/hey-cheryl.service' exists in your repository."
    exit 1
fi

# Copy the service file to the systemd directory
echo "Copying service file to ${SERVICE_DEST}..."
cp "$SERVICE_SRC" "$SERVICE_DEST"

# Substitute placeholders with actual paths and user
echo "Configuring service file placeholders..."
sed -i "s|__RUN_USER__|$RUN_USER|g" "$SERVICE_DEST"
sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$SERVICE_DEST"
# In the service file, PATH should point to the bin directory
sed -i "s|__VENV_DIR__|$VENV_BIN_DIR|g" "$SERVICE_DEST"
# Also update the ExecStart command to use the gunicorn executable from the venv bin
sed -i "s|ExecStart=__VENV_DIR__/gunicorn|ExecStart=${VENV_BIN_DIR}/gunicorn|g" "$SERVICE_DEST"


# Reload systemd daemon to recognize the new service file
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service to start on boot
echo "Enabling hey-cheryl.service..."
systemctl enable hey-cheryl.service

# Start the service
echo "Starting hey-cheryl.service..."
systemctl start hey-cheryl.service

echo "Installation complete. Systemd service hey-cheryl.service should now be running."
echo "Check service status with: sudo systemctl status hey-cheryl.service"
echo "View logs with: sudo journalctl -u hey-cheryl.service -f"
