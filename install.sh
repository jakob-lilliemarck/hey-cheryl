```sh
#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting simplified production installation for Hey Cheryl..."
echo ""
echo "------------------------------------------------------------------"
echo " IMPORTANT: Prerequisites"
echo " Before running this script, ensure you have:"
echo " 1. Created a dedicated system user named 'hey-cheryl'."
echo "    Example: sudo useradd --system --no-create-home --shell /bin/false hey-cheryl"
echo " 2. Installed 'git' on the system."
echo " 3. Installed 'uv' for the 'hey-cheryl' user."
echo "    Log in as 'hey-cheryl' and run: curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "------------------------------------------------------------------"
echo ""

# --- Configuration ---

# Fixed installation directory
INSTALL_DIR="/opt/hey-cheryl"

# Fixed dedicated unprivileged user the service will run as
RUN_USER="hey-cheryl" # <-- **UPDATE THIS IF YOUR USERNAME IS DIFFERENT**

# Git repository URL
REPO_URL="https://github.com/your-username/hey-cheryl.git" # <-- **UPDATE WITH YOUR REPO URL**

# --- Check for Root Privileges ---

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run this script with sudo or as the root user."
    exit 1
fi

# --- Check Prerequisites ---

if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    echo "Error: Dedicated user '$RUN_USER' does not exist. Please create it first."
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "Error: git command not found. Please install git."
    exit 1
fi

# Check if uv is in the PATH for the target user
if ! sudo -u "$RUN_USER" command -v uv &> /dev/null; then
    echo "Error: uv command not found for user '$RUN_USER'. Please install uv for this user."
    exit 1
fi


# --- Clone Repository ---

echo "Cloning repository into ${INSTALL_DIR}..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory ${INSTALL_DIR} already exists. Skipping git clone. Ensure it contains the correct repo."
    # Optional: Add logic here to ensure it's the correct repo, or prompt to remove
else
    if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
        echo "Error: Failed to clone repository from ${REPO_URL}"
        exit 1
    fi
fi

# --- Set Permissions ---

echo "Setting ownership of ${INSTALL_DIR} to user ${RUN_USER}..."
if ! chown -R "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"; then
    echo "Error: Failed to set ownership of ${INSTALL_DIR} to ${RUN_USER}"
    exit 1
fi

# --- Set up Virtual Environment and Install Dependencies as the dedicated user ---

echo "Setting up venv and installing dependencies as user ${RUN_USER}..."
sudo -u "$RUN_USER" bash -c "
  set -e
  trap 'echo \"An error occurred during venv setup or dependency installation.\" >&2' ERR
  cd \"$INSTALL_DIR\" || exit 1

  echo \"Creating virtual environment...\"
  # Use the determined uv executable path (found in parent script) if available for the user
  uv venv .venv

  echo \"Installing dependencies...\"
  uv sync --locked

  echo \"Venv setup and dependency installation complete.\"
"

# --- Install and Configure Systemd Service ---

echo "Installing and configuring systemd service..."

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
# Use | as delimiter for sed to avoid issues with slashes in paths
if ! sed -i "s|__RUN_USER__|$RUN_USER|g" "$SERVICE_DEST"; then echo "Error substituting RUN_USER" && exit 1; fi
if ! sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$SERVICE_DEST"; then echo "Error substituting APP_DIR" && exit 1; fi


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
echo "Installation complete. Systemd service hey-cheryl.service should now be running."
echo "Check service status with: sudo systemctl status hey-cheryl.service"
echo "View logs with: sudo journalctl -u hey-cheryl.service -f"
echo "------------------------------------------------------------------"
echo ""
```