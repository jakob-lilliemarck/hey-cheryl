#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting production installation for Hey Cheryl..."
echo ""
echo "------------------------------------------------------------------"
echo " IMPORTANT:"
echo " Before running this script, ensure you have:"
echo " 1. Created a dedicated unprivileged user for this application (e.g., 'hey-cheryl')."
echo "    Example: sudo useradd --system --no-create-home --shell /bin/false hey-cheryl"
echo " 2. Installed git on the system."
echo " 3. Installed uv for the user that will run the application ('hey-cheryl')."
echo "    Log in as that user and run: curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "------------------------------------------------------------------"
echo ""

# --- Configuration ---

# Default installation directory
DEFAULT_INSTALL_DIR="/opt/hey-cheryl"

# The dedicated unprivileged user the service will run as
# This user MUST exist on the system and have uv installed before running the script
RUN_USER="hey-cheryl" # <-- **UPDATE THIS IF YOUR USERNAME IS DIFFERENT**

# Git repository URL
REPO_URL="https://github.com/your-username/hey-cheryl.git" # <-- **UPDATE WITH YOUR REPO URL**

# --- Check for Root Privileges ---

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run this script with sudo or as the root user."
    exit 1
fi

# --- Check if the dedicated user exists ---
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    echo "Error: Dedicated user '$RUN_USER' does not exist."
    echo "Please create the user first (see instructions above)."
    exit 1
fi


# --- Determine Installation Directory ---

# If an argument is provided, use it; otherwise, use the default
if [ -n "$1" ]; then
  # Use realpath to handle relative paths and get the absolute path
  INSTALL_DIR="$(realpath "$1")"
  echo "Using provided installation directory: ${INSTALL_DIR}"
else
  INSTALL_DIR="${DEFAULT_INSTALL_DIR}"
  echo "Using default installation directory: ${INSTALL_DIR}"
fi

# --- Clone Repository ---

echo "Cloning repository into ${INSTALL_DIR}..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Warning: Installation directory ${INSTALL_DIR} already exists."
    # For initial install, we expect it not to exist, so let's just clone
    # If directory exists, assume it's a re-run or manual intervention and skip clone
    echo "Skipping git clone as directory already exists. Ensure it contains the correct repo."
else
    # Use git clone to get the project
    echo "Cloning from ${REPO_URL}... Paxton: Cloning from ${REPO_URL}..."
    if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
        echo "Error: Failed to clone repository from ${REPO_URL}"
        exit 1
    fi
fi

# --- Set Permissions ---

echo "Setting ownership of ${INSTALL_DIR} to user ${RUN_USER}..."
# Change ownership of the application directory to the dedicated user
if ! chown -R "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"; then
    echo "Error: Failed to set ownership of ${INSTALL_DIR} to ${RUN_USER}"
    exit 1
fi


# --- Set up Virtual Environment and Install Dependencies as the dedicated user ---

echo "Setting up virtual environment and installing dependencies as user ${RUN_USER}... Paxton: Running venv setup as ${RUN_USER}..."

# Determine the full path to the activate script for the target user
ACTIVATE_SCRIPT="${INSTALL_DIR}/.venv/bin/activate"

# Determine the uv executable path for the target user's environment
# We need to run 'command -v uv' *as the target user* to find it in their PATH
echo "Checking if uv is in the PATH for user '$RUN_USER'..."
UV_EXEC_FOR_USER=$(sudo -u "$RUN_USER" bash -c "command -v uv")

if [ -z "$UV_EXEC_FOR_USER" ]; then
    echo "Error: uv command not found for user '$RUN_USER'. Please install uv for this user (see instructions above)."
    exit 1
fi
echo "uv executable found for user '$RUN_USER' at: $UV_EXEC_FOR_USER"


# Execute commands as the dedicated user using sudo -u bash -c
# Use -O to restore shell options from invoking shell (if needed)
# Use -s to read commands from standard input (the string)
sudo -u "$RUN_USER" bash -c "
  # Set up error handling within the subshell
  set -e
  trap 'echo \"An error occurred during venv setup and dependency installation.\" >&2' ERR

  echo \"Navigating to application directory: ${INSTALL_DIR}\"
  cd \"$INSTALL_DIR\" || exit 1 # Navigate to the app directory

  echo \"Creating virtual environment in ${INSTALL_DIR}/.venv...\"
  # Use the determined uv executable path
  \"$UV_EXEC_FOR_USER\" venv \"${INSTALL_DIR}/.venv\"

  echo \"Activating virtual environment...\"
  # Use . instead of source for POSIX compatibility, often preferred in scripts
  . \"$ACTIVATE_SCRIPT\"

  echo \"Installing dependencies with uv sync... Paxton: Running uv sync...\"
  # Use the determined uv executable path
  \"$UV_EXEC_FOR_USER\" sync --locked

  echo \"Venv setup and dependency installation complete.\"

  # Deactivate is not strictly needed at the end of this non-interactive script
  # command -v deactivate &> /dev/null && deactivate # Check if deactivate exists before calling

" # End of sudo -u bash -c block


# --- Install and Configure Systemd Service ---

echo "Installing and configuring systemd service... Paxton: Installing systemd service..."

# Determine the path to the virtual environment bin directory (for the service file placeholder)
VENV_BIN_DIR="${INSTALL_DIR}/.venv/bin"

# Define source and destination paths for the systemd service file
SERVICE_SRC="${INSTALL_DIR}/deploy/hey-cheryl.service"
SERVICE_DEST="/etc/systemd/system/hey-cheryl.service"


# Check if the source service file exists
if [ ! -f "$SERVICE_SRC" ]; then
    echo "Error: Systemd service source file not found at ${SERVICE_SRC}"
    echo "Please ensure 'deploy/hey-cheryl.service' exists in your repository at this path relative to the install directory."
    exit 1
fi

# Copy the service file to the systemd directory
echo "Copying service file to ${SERVICE_DEST}... Paxton: Copying service file..."
if ! cp "$SERVICE_SRC" "$SERVICE_DEST"; then
    echo "Error: Failed to copy service file to ${SERVICE_DEST}"
    exit 1
fi

# Substitute placeholders with actual paths and user
echo "Configuring service file placeholders... Paxton: Configuring service file..."
# Use | as delimiter for sed to avoid issues with slashes in paths
if ! sed -i "s|__RUN_USER__|$RUN_USER|g" "$SERVICE_DEST"; then echo "Error substituting RUN_USER" && exit 1; fi
if ! sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$SERVICE_DEST"; then echo "Error substituting APP_DIR" && exit 1; fi
# VENV_BIN_DIR in the service file points to the bin directory for sourcing activate
if ! sed -i "s|__VENV_DIR__|$VENV_BIN_DIR|g" "$SERVICE_DEST"; then echo "Error substituting VENV_DIR" && exit 1; fi


# Reload systemd daemon to recognize the new service file
echo "Reloading systemd daemon... Paxton: Reloading systemd daemon..."
if ! systemctl daemon-reload; then
    echo "Error: Failed to reload systemd daemon."
    exit 1
fi

# Enable the service to start on boot
echo "Enabling hey-cheryl.service... Paxton: Enabling service..."
if ! systemctl enable hey-cheryl.service; then
    echo "Error: Failed to enable hey-cheryl.service."
    exit 1
fi

# Start the service
echo "Starting hey-cheryl.service... Paxton: Starting service..."
if ! systemctl start hey-cheryl.service; then
    echo "Error: Failed to start hey-cheryl.service."
    # Provide instructions to check status and logs
    echo "Please check service status and logs manually:"
    echo "  sudo systemctl status hey-cheryl.service"
    echo "  sudo journalctl -u hey-cheryl.service -f"
    exit 1
fi

echo ""
echo "------------------------------------------------------------------"
echo "Installation complete. Systemd service hey-cheryl.service should now be running."
echo "Check service status with: sudo systemctl status hey-cheryl.service"
echo "View logs with: sudo journalctl -u hey-cheryl.service -f"
echo "------------------------------------------------------------------"
echo ""
