#!/bin/bash
# Launch Jenny AI HUD in Google Chrome frameless App mode for maximum immersion

PORT=3005
URL="http://localhost:${PORT}/app"

echo "=========================================================="
echo "  JENNY AI - Launching HUD in Standalone App Mode"
echo "=========================================================="

if [ "$(uname)" == "Darwin" ]; then
  # macOS
  echo "Opening Chrome in --app mode..."
  open -n -a "Google Chrome" --args --app="${URL}"
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
  # Linux
  echo "Opening Chrome in --app mode..."
  google-chrome --app="${URL}" &
else
  # Windows (via git bash or similar)
  echo "Opening Chrome in --app mode..."
  start chrome --app="${URL}"
fi

echo "HUD launched successfully!"
echo "=========================================================="
