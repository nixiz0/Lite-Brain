#!/usr/bin/env bash

# ============================
# CPU/GPU script
# ============================

# Stop on error
set -e

# Go to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python binary (python or python3)
if command -v python &>/dev/null; then
    PYTHON_BIN="python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
else
    echo "Error: python or python3 not found in PATH."
    exit 1
fi

# Venv name
VENV_DIR=".venv"

# Paths inside the venv
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_ACTIVATE="$VENV_DIR/bin/activate"

if [ ! -f "$VENV_PYTHON" ]; then
    echo
    echo "============================"
    echo " Launch the API (CPU / GPU) "
    echo "============================"
    echo "[1] CPU"
    echo "[2] GPU"
    echo

    read -rp "Choose the mode (1=CPU, 2=GPU): " choice

    case "$choice" in
        1)
            MODE="CPU"
            ;;
        2)
            MODE="GPU"
            ;;
        *)
            echo "Invalid choice, defaulting to CPU."
            MODE="CPU"
            ;;
    esac

    echo
    echo "Selected mode: $MODE"
    echo

    if [ "$MODE" = "CPU" ]; then
        TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"
    else
        TORCH_INDEX_URL="https://download.pytorch.org/whl/cu118"
    fi

    echo "Creating the virtual environment $VENV_DIR ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"

    # Activate the venv
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"

    echo "Updating pip..."
    python -m pip install --upgrade pip

    echo "Installing torch / torchvision..."
    python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url "$TORCH_INDEX_URL"

    echo "Installing dependencies..."
    python -m pip install -r requirements.txt
else
    echo "Activating the existing virtual environment $VENV_DIR ..."
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
fi

# Launch the API in background (similar to 'start cmd /k' behavior)
uvicorn app.main:app --host 127.0.0.1 --port 9005 --reload &
echo "API started on http://127.0.0.1:9005 (running in background)"
