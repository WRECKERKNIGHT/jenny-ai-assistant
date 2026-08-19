#!/bin/bash
# JENNY AI ASSISTANT - macOS Menu Bar Shortcut Trigger Script
# Runs via macOS Shortcuts app, Automator, or Menu Bar item

curl -s -X GET "http://localhost:3000/api/toggle-mic" > /dev/null
echo "[JENNY AI] Mic toggle triggered from macOS Menu Bar."
