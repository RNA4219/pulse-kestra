#!/bin/bash
# Start pulse-bridge server

set -e

# Load environment variables from .env if present
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default port
PORT=${PORT:-8000}

echo "Starting pulse-bridge on port $PORT..."
python -m uvicorn bridge.main:app --host 0.0.0.0 --port $PORT