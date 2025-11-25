#!/bin/bash

# Move to the directory where the script is located
cd "$(dirname "$0")"

# Create and activate the virtual environment if it does not exist
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Start "npm run dev" in a new terminal
# Choose the line that fits your environment:

# For GNOME Terminal (Ubuntu / Debian / PopOS)
# gnome-terminal -- bash -c "npm run dev; exec bash"

# For KDE Konsole
# konsole -e bash -c "npm run dev; exec bash"

# For macOS Terminal
# osascript -e 'tell app "Terminal" to do script "cd \"$(pwd)\" && npm run dev"'

# For xterm (fallback, works everywhere)
xterm -hold -e "npm run dev"
