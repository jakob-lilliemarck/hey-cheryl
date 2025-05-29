#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting simplified ROOT installation for Hey Cheryl..."
echo "------------------------------------------------------------------"
echo " IMPORTANT: Prerequisites"
echo " 1. Installed 'git' on the system."
echo " 2. Installed 'uv' for the 'root' user or globally."
echo "    Example: curl -LsSf https://astral.sh/uv/install.sh | sh (as root)"
echo " 3. Your domain 'hey-cheryl.se' DNS records point to this server's IP."
echo "------------------------------------------------------------------"

# --- Configuration ---
INSTALL_DIR="/opt/hey-cheryl"
REPO_URL="https://github.com/your-username/hey-cheryl.git" # <-- **UPDATE WITH YOUR REPO URL**
# Domain is now hardcoded in deploy/nginx.conf

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

# --- Clone or Update Repository ---
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory ${INSTALL_DIR} already exists. Pulling latest changes..."
    cd "$INSTALL_DIR" || { echo "Failed to cd into ${INSTALL_DIR}"; exit 1; }
    if ! git pull origin main; then # Assuming 'main' is your default branch
        echo "Error: Failed to pull latest changes from repository."
        exit 1
    fi
else
    echo "Cloning repository into ${INSTALL_DIR}..."
    if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
        echo "Error: Failed to clone repository from ${REPO_URL}"
        exit 1
    fi
fi

# --- Set up Virtual Environment and Install Dependencies (as root) ---
echo "Setting up venv and installing dependencies in ${INSTALL_DIR}..."
cd "$INSTALL_DIR" || { echo "Failed to cd into ${INSTALL_DIR} after clone/pull"; exit 1; }

echo "Creating/updating virtual environment..."
uv venv .venv # uv venv is idempotent

echo "Installing dependencies into .venv..."
(
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv sync --locked
)
echo "Venv setup and dependency installation complete."

# --- Install and Configure Gunicorn Systemd Service ---
echo "Updating and configuring Gunicorn systemd service..."
GUNICORN_SERVICE_NAME="hey-cheryl.service"
GUNICORN_SERVICE_SRC="${INSTALL_DIR}/deploy/${GUNICORN_SERVICE_NAME}"
GUNICORN_SERVICE_DEST="/etc/systemd/system/${GUNICORN_SERVICE_NAME}"

echo "Attempting to stop and disable ${GUNICORN_SERVICE_NAME}..."
systemctl stop "${GUNICORN_SERVICE_NAME}" >/dev/null 2>&1 || true
systemctl disable "${GUNICORN_SERVICE_NAME}" >/dev/null 2>&1 || true

if [ ! -f "$GUNICORN_SERVICE_SRC" ]; then
    echo "Error: Gunicorn service source file not found at ${GUNICORN_SERVICE_SRC}"
    exit 1
fi
echo "Copying Gunicorn service file to ${GUNICORN_SERVICE_DEST}..."
if ! cp "$GUNICORN_SERVICE_SRC" "$GUNICORN_SERVICE_DEST"; then
    echo "Error: Failed to copy Gunicorn service file."
    exit 1
fi
echo "Configuring Gunicorn service file placeholders..."
if ! sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$GUNICORN_SERVICE_DEST"; then
    echo "Error substituting __APP_DIR__ in Gunicorn service file."
    exit 1
fi
echo "Reloading systemd daemon for Gunicorn service..."
if ! systemctl daemon-reload; then # daemon-reload applies to all changed units
    echo "Error: Failed to reload systemd daemon."
    exit 1
fi
echo "Enabling ${GUNICORN_SERVICE_NAME}..."
if ! systemctl enable "${GUNICORN_SERVICE_NAME}"; then
    echo "Error: Failed to enable ${GUNICORN_SERVICE_NAME}."
    exit 1
fi
echo "Starting ${GUNICORN_SERVICE_NAME}..."
if ! systemctl start "${GUNICORN_SERVICE_NAME}"; then
    echo "Error: Failed to start ${GUNICORN_SERVICE_NAME}."
fi
echo "Gunicorn systemd service setup complete."

# --- Install and Configure Cheryl Worker Systemd Service ---
echo "Updating and configuring Cheryl worker systemd service..."
CHERYL_SERVICE_NAME="cheryl.service"
CHERYL_SERVICE_SRC="${INSTALL_DIR}/deploy/${CHERYL_SERVICE_NAME}"
CHERYL_SERVICE_DEST="/etc/systemd/system/${CHERYL_SERVICE_NAME}"

echo "Attempting to stop and disable ${CHERYL_SERVICE_NAME}..."
systemctl stop "${CHERYL_SERVICE_NAME}" >/dev/null 2>&1 || true
systemctl disable "${CHERYL_SERVICE_NAME}" >/dev/null 2>&1 || true

if [ ! -f "$CHERYL_SERVICE_SRC" ]; then
    echo "Error: Cheryl worker service source file not found at ${CHERYL_SERVICE_SRC}"
    exit 1
fi
echo "Copying Cheryl worker service file to ${CHERYL_SERVICE_DEST}..."
if ! cp "$CHERYL_SERVICE_SRC" "$CHERYL_SERVICE_DEST"; then
    echo "Error: Failed to copy Cheryl worker service file."
    exit 1
fi
echo "Configuring Cheryl worker service file placeholders..."
if ! sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$CHERYL_SERVICE_DEST"; then
    echo "Error substituting __APP_DIR__ in Cheryl worker service file."
    exit 1
fi
echo "Reloading systemd daemon for Cheryl service..."
if ! systemctl daemon-reload; then
    echo "Error: Failed to reload systemd daemon."
    exit 1
fi
echo "Enabling ${CHERYL_SERVICE_NAME}..."
if ! systemctl enable "${CHERYL_SERVICE_NAME}"; then
    echo "Error: Failed to enable ${CHERYL_SERVICE_NAME}."
    exit 1
fi
echo "Starting ${CHERYL_SERVICE_NAME}..."
if ! systemctl start "${CHERYL_SERVICE_NAME}"; then
    echo "Error: Failed to start ${CHERYL_SERVICE_NAME}."
fi
echo "Cheryl worker systemd service setup complete."


# --- Install and Configure Nginx ---
echo "Installing and configuring Nginx..."

if ! command -v nginx &> /dev/null; then
    echo "Nginx not found, installing..."
    if ! dnf install -y nginx; then
        echo "Error: Failed to install Nginx. Please install it manually."
        exit 1
    fi
else
    echo "Nginx is already installed."
fi

# Use a fixed Nginx conf name, or derive from domain if preferred
NGINX_CONF_FILENAME="hey-cheryl.se.conf"
NGINX_CONF_SRC="${INSTALL_DIR}/deploy/nginx.conf" # This is the template from the repo
NGINX_CONF_DEST="/etc/nginx/conf.d/${NGINX_CONF_FILENAME}"

if [ ! -f "$NGINX_CONF_SRC" ]; then
    echo "Error: Nginx config source file not found at ${NGINX_CONF_SRC}"
    exit 1
fi

echo "Copying Nginx configuration to ${NGINX_CONF_DEST}..."
# This will overwrite the existing Nginx config for hey-cheryl.se if it exists
if ! cp "$NGINX_CONF_SRC" "$NGINX_CONF_DEST"; then
    echo "Error: Failed to copy Nginx configuration."
    exit 1
fi

echo "Testing Nginx configuration..."
if ! nginx -t; then
    echo "Error: Nginx configuration test failed. Please check ${NGINX_CONF_DEST}"
    exit 1
fi

echo "Reloading Nginx to apply changes..."
if ! systemctl reload nginx; then
    echo "Nginx reload failed, attempting restart..."
    if ! systemctl restart nginx; then
        echo "Error: Failed to reload or restart Nginx."
        exit 1
    fi
fi

if ! systemctl is-enabled --quiet nginx; then
    echo "Enabling Nginx to start on boot..."
    if ! systemctl enable nginx; then
        echo "Warning: Failed to enable Nginx."
    fi
fi
echo "Nginx setup complete."

echo "------------------------------------------------------------------"
echo "Installation complete."
echo "Gunicorn service: sudo systemctl status ${GUNICORN_SERVICE_NAME}"
echo "Cheryl worker service: sudo systemctl status ${CHERYL_SERVICE_NAME}"
echo "Nginx service: sudo systemctl status nginx"
echo "Application should be accessible via HTTP at http://hey-cheryl.se"
echo ""
echo "--- Viewing Logs ---"
echo "To view Gunicorn (application) logs:  sudo journalctl -u ${GUNICORN_SERVICE_NAME} -f"
echo "To view Cheryl worker logs:           sudo journalctl -u ${CHERYL_SERVICE_NAME} -f"
echo "To view Nginx access logs:            sudo journalctl -u nginx -f"
echo "To view PostgreSQL logs:              sudo journalctl -u postgresql -f"
echo ""
echo "Next steps for HTTPS:"
echo "1. Ensure your domain 'hey-cheryl.se' DNS records point to this server's IP."
echo "2. Install Certbot: sudo dnf install certbot python3-certbot-nginx"
echo "3. Run Certbot: sudo certbot --nginx -d hey-cheryl.se -d www.hey-cheryl.se"
echo "   Certbot will obtain SSL certificates and update Nginx configuration for HTTPS."
echo "------------------------------------------------------------------"
