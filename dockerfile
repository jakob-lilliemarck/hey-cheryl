FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync --locked

# Expose the port your Flask app will listen on (default: 5000)
EXPOSE 5000

# Set environment variables (important!)
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Define the command to run your application
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]
