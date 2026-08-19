#!/bin/bash
# ============================================================
#  JENNY Remote Access — Expose JENNY to the internet
#  Usage: bash scripts/start-remote.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
PORT=$(grep '^PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "3000")
PORT=${PORT:-3000}

echo "=========================================================="
echo "  JENNY REMOTE ACCESS"
echo "=========================================================="
echo ""

# Check if server is running
if ! curl -s "http://localhost:$PORT/api/system-status" > /dev/null 2>&1; then
  echo "[!] Server not running on port $PORT"
  echo "    Starting server first..."
  cd "$PROJECT_DIR"
  launchctl start com.jenny.server 2>/dev/null || node server.js &
  sleep 3
fi

echo "[*] Server confirmed on port $PORT"
echo ""

# Try ngrok first
if command -v ngrok &>/dev/null; then
  echo "[*] Using ngrok for tunnel..."
  echo "[*] Starting tunnel to localhost:$PORT..."
  echo ""
  ngrok http "$PORT" --log=stdout 2>&1 | while IFS= read -r line; do
    if echo "$line" | grep -q "https://.*ngrok-free"; then
      URL=$(echo "$line" | grep -oP 'https://[a-zA-Z0-9\-]+\.ngrok-free\.app')
      if [ -n "$URL" ]; then
        echo ""
        echo "=========================================================="
        echo "  REMOTE ACCESS URL:"
        echo "  $URL"
        echo ""
        echo "  Open this URL on your phone to access JENNY."
        echo "  Login token: (check your .env REMOTE_ACCESS_TOKEN)"
        echo "=========================================================="
        echo ""
        # Save URL for reference
        echo "$URL" > /tmp/jenny-remote-url.txt
      fi
    fi
  done
else
  echo "[*] ngrok not found. Trying localtunnel (npm)..."
  echo ""

  # Check if localtunnel is available
  if ! command -v lt &>/dev/null; then
    echo "[*] Installing localtunnel via npm..."
    npm install -g localtunnel 2>/dev/null || {
      echo "[!] Failed to install localtunnel."
      echo ""
      echo "  Install ngrok manually:"
      echo "    1. Visit https://ngrok.com/download"
      echo "    2. Download for macOS"
      echo "    3. Move to /usr/local/bin/ngrok"
      echo "    4. Run: ngrok config add-authtoken YOUR_TOKEN"
      echo ""
      echo "  Or install localtunnel:"
      echo "    npm install -g localtunnel"
      echo ""
      echo "  Then re-run this script."
      exit 1
    }
  fi

  echo "[*] Starting localtunnel on port $PORT..."
  echo "[*] Your URL will appear below:"
  echo ""
  lt --port "$PORT" 2>&1 | while IFS= read -r line; do
    echo "  $line"
    if echo "$line" | grep -q "your url is"; then
      URL=$(echo "$line" | grep -oP 'https://[a-zA-Z0-9\-]+\.loca\.lt')
      if [ -n "$URL" ]; then
        echo "$URL" > /tmp/jenny-remote-url.txt
        echo ""
        echo "=========================================================="
        echo "  REMOTE ACCESS URL:"
        echo "  $URL"
        echo ""
        echo "  Open this URL on your phone to access JENNY."
        echo "  You may need to enter the password shown on the page."
        echo "=========================================================="
      fi
    fi
  done
fi
