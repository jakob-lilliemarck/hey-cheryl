```sh
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
echo "------------------------------------------------------------------"
echo ""

# --- Configuration ---

# Default installation directory
DEFAULT_INSTALL_DIR="/opt/hey-cheryl"

# The dedicated unprivileged user the service will run as
# This user MUST exist on the system before running the script
RUN_USER="hey-cheryl" # <-- **UPDATE THIS IF YOUR USERNAME IS DIFFERENT**

# Git repository URL
REPO_URL="https://github.com/jakob-lilliemarck/hey-cheryl.git" # <-- **UPDATE WITH YOUR REPO URL**

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
    echo "Warning: Installation directory ${INSTALL_DIR} already exists. Cloning into it."
    # Optional: add logic here to handle existing directory, e.g., git pull or error
    # For initial install, we expect it not to exist, so let's just clone
    # If directory exists, assume it's a re-run or manual intervention and skip clone
    echo "Skipping git clone as directory already exists. Ensure it contains the correct repo."
else
    # Use git clone to get the project
    echo "Cloning from ${REPO_URL}..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# --- Set Permissions ---

echo "Setting ownership of ${INSTALL_DIR} to user ${RUN_USER}..."
# Change ownership of the application directory to the dedicated user
chown -R "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"

# --- Install uv and Dependencies ---

echo "Installing uv..."
# Install uv globally (or for root/sudo user running script)
# Check if uv is already installed globally first
if ! command -v uv &> /dev/null || [ "$(command -V uv)" != "$(which uv)" ]; then
    echo "uv not found or not in standard path for root, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Ensure uv is in the PATH for the current script execution
    # uv is often installed via cargo, so add the default cargo bin directory for root/sudo user
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Check if the uv executable is available AFTER potential installation
if ! command -v uv &> /dev/null; then
    echo "Error: uv command not found after installation attempt. Please check the installation path or install manually."
    exit 1
fi

# --- Set up Virtual Environment and Install Dependencies as the dedicated user ---

echo "Setting up virtual environment and installing dependencies as user ${RUN_USER}..."
# Execute commands as the dedicated user using sudo -u
sudo -u "$RUN_USER" bash -c "
  set -e # Exit immediately if a command fails within this bash shell
  cd \"$INSTALL_DIR\" # Navigate to the app directory

  # Determine the uv executable path for the target user
  UV_EXEC=\"\$(sudo -u ${RUN_USER} command -v uv)\"
  if [ -z \"\$UV_EXEC\" ]; then
      echo \"Error: uv command not found for user '$RUN_USER'. Please install uv for this user or ensure it's in their PATH.\"
      exit 1
  fi

  echo \"Creating virtual environment in ${INSTALL_DIR}/.venv...\"
  \$UV_EXEC venv \"${INSTALL_DIR}/.venv\"

  echo \"Activating virtual environment...\"
  source \"${INSTALL_DIR}/.venv/bin/activate\"

  echo \"Installing dependencies with uv sync...\"
  \$UV_EXEC sync --locked

  # Deactivate is not strictly needed at the end of this non-interactive script
  # deactivate
" # End of sudo -u bash -c block


# --- Install and Configure Systemd Service ---

echo "Installing and configuring systemd service..."

# Determine the path to the virtual environment bin directory (for the service file placeholder)
VENV_BIN_DIR="${INSTALL_DIR}/.venv/bin"

# Define source and destination paths for the systemd service file
SERVICE_SRC="${INSTALL_DIR}/deploy/hey-cheryl.service"
SERVICE_DEST="/etc/systemd/system/hey-cheryl.service"


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
# Use | as delimiter for sed to avoid issues with slashes in paths
sed -i "s|__RUN_USER__|$RUN_USER|g" "$SERVICE_DEST"
sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$SERVICE_DEST"
# VENV_BIN_DIR in the service file points to the bin directory for sourcing activate
sed -i "s|__VENV_DIR__|$VENV_BIN_DIR|g" "$SERVICE_DEST"


# Reload systemd daemon to recognize the new service file
echo "Reloading systemd daemon... Paxton: Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service to start on boot
echo "Enabling hey-cheryl.service..."
systemctl enable hey-cheryl.service

# Start the service
echo "Starting hey-cheryl.service..."
systemctl start hey-cheryl.service

echo ""
echo "------------------------------------------------------------------"
echo "Installation complete. Systemd service hey-cheryl.service should now be running."
echo "Check service status with: sudo systemctl status hey-cheryl.service"
echo "View logs with: sudo journalctl -u hey-cheryl.service -f"
echo "------------------------------------------------------------------"
echo ""
```
