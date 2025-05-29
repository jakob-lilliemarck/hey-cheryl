INSTALL_DIR="/home/jakob/Projects/hey-cheryl"
SOURCE_SERVICE_FILE="./deploy/cheryl.service"
DEST_SERVICE_FILE="/etc/systemd/system/cheryl.service"

sudo cp "$SOURCE_SERVICE_FILE" "$DEST_SERVICE_FILE" || {
    echo "Error copying service file."
    exit 1
}

sudo sed -i "s|__APP_DIR__|$INSTALL_DIR|g" "$DEST_SERVICE_FILE" || {
    echo "Error substituting __APP_DIR__ in Cheryl worker service file."
    # Consider removing the partially modified file if sed fails catastrophically
    exit 1
}

# Reload the systemd daemon to recognize the new service file
sudo systemctl daemon-reload || {
    echo "Error reloading systemd daemon."
    exit 1
}

# Enable the service to start on boot
sudo systemctl enable cheryl.service || {
    echo "Error enabling Cheryl worker service."
    exit 1
}

# Start the service
sudo systemctl start cheryl.service || {
    echo "Error starting Cheryl worker service."
    exit 1
}

echo "Cheryl worker service installed and started successfully."
