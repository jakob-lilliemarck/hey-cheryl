#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Installing uv..."
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ensure the uv executable is in the PATH for the current script
# uv is often installed via cargo, so add the default cargo bin directory to PATH
export PATH="$HOME/.cargo/bin:$PATH"

echo "Creating virtual environment..."
# Create a virtual environment named .venv in the current directory
uv venv .venv

echo "Activating virtual environment..."
# Activate the virtual environment
source .venv/bin/activate

echo "Installing dependencies with uv sync..."
# Install dependencies from pyproject.toml and uv.lock into the active environment
uv sync

source .venv/bin/deactivate
