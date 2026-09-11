#!/bin/bash
# JENNY AI - macOS Menu Bar & Desktop App Launcher

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="$APP_DIR/bin"
SERVER_PORT=3005

echo "=========================================================="
echo "  JENNY AI - Starting Native macOS Apps"
echo "=========================================================="

# Kill any existing instances
killall JennyMenuBarApp JennyDesktop 2>/dev/null || true
sleep 0.5

# Auto-build if binaries are missing or outdated
if [ ! -f "$BIN_DIR/JennyAI.app/Contents/MacOS/JennyMenuBarApp" ] || \
   [ "$APP_DIR/scripts/JennyMenuBarApp.swift" -nt "$BIN_DIR/JennyAI.app/Contents/MacOS/JennyMenuBarApp" ]; then
  echo "Building native apps (first run or source changed)..."
  bash "$APP_DIR/scripts/build-apps.sh"
fi

# Check if server is already running
if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
  echo "Server already running on port $SERVER_PORT"
else
  echo "Starting JENNY server on http://localhost:$SERVER_PORT..."
  cd "$APP_DIR" && nohup node server.js > /tmp/jenny-server.log 2>&1 &
  
  # Wait for server to be ready
  echo -n "Waiting for server"
  for i in $(seq 1 15); do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$SERVER_PORT" | grep -q "200"; then
      echo " ready!"
      break
    fi
    echo -n "."
    sleep 1
  done
  echo ""
fi

# Launch Menu Bar App
if [ -f "$BIN_DIR/JennyAI.app/Contents/MacOS/JennyMenuBarApp" ]; then
  open "$BIN_DIR/JennyAI.app"
  echo "Menu Bar App active in status bar"
else
  echo "WARNING: JennyAI.app not found. Run: bash scripts/build-apps.sh"
fi

# Launch Desktop App (optional - uncomment to auto-start)
# if [ -f "$BIN_DIR/JennyDesktop.app/Contents/MacOS/JennyDesktop" ]; then
#   open "$BIN_DIR/JennyDesktop.app"
#   echo "Desktop App launched"
# fi

echo ""
echo "Done! JENNY is running."
