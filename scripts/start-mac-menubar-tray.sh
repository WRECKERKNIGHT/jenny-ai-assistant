#!/bin/bash
# NATIVE macOS STANDALONE DESKTOP APP & MENU BAR POPOVER LAUNCHER FOR JENNY AI

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================================="
echo "  🌌 JENNY AI - REFRESHING NATIVE MENU BAR & DESKTOP APP  "
echo "=========================================================="

# Kill any existing background instances of old menu bar apps
killall JennyAI JennyMenuBarApp JennyToggleMic JennyAIAppExecutable JennyMenuBarExecutable 2>/dev/null
sleep 1

# Ensure server is running
if ! lsof -i :3000 > /dev/null; then
  echo "🚀 Starting Jenny Server on http://localhost:3000..."
  cd "$APP_DIR" && node server.js &
  sleep 2
fi

# Launch Native macOS Menu Bar Popover App
if [ -d "$APP_DIR/bin/JennyAI.app" ]; then
  open "$APP_DIR/bin/JennyAI.app"
  echo "✅ macOS Menu Bar Mini Jenny Popover active in status bar!"
fi

# Launch Native Standalone Desktop Window App
if [ -d "$APP_DIR/bin/JennyDesktop.app" ]; then
  open "$APP_DIR/bin/JennyDesktop.app"
  echo "✅ Jenny Standalone Desktop App Window launched!"
fi
