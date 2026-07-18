#!/bin/bash
# NATIVE macOS MENU BAR SHORTCUT & LAUNCHER FOR JENNY AI
# This script runs a background status loop and triggers Mic Toggle on demand.

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN_APP="$APP_DIR/bin/JennyToggleMic.app"

echo "===================================================="
echo "   🎙️ JENNY AI - NATIVE macOS MENU BAR LAUNCHER   "
echo "===================================================="
echo " Native App: $BIN_APP"
echo " Trigger Endpoint: http://localhost:3000/api/toggle-mic"
echo ""

# Launch Jenny Toggle App once to test
open "$BIN_APP"
echo "✅ Native macOS Menu Bar Shortcut triggered!"
