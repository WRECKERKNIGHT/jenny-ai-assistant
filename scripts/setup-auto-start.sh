#!/bin/bash
# macOS Auto-Start Setup for Jenny AI on Boot/Login
# Usage: setup-auto-start.sh [install|uninstall|status]

PLIST_PATH="$HOME/Library/LaunchAgents/com.jenny.assistant.plist"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

MODE="${1:-install}"

case "$MODE" in
  uninstall|remove)
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "✅ Jenny AI Auto-Start disabled. LaunchAgent removed."
    exit 0
    ;;
  status|check)
    if [ -f "$PLIST_PATH" ] && launchctl list 2>/dev/null | grep -q "com.jenny.assistant"; then
      echo "✅ Jenny AI Auto-Start is ENABLED and loaded."
    elif [ -f "$PLIST_PATH" ]; then
      echo "ℹ️  LaunchAgent file exists but is not loaded."
    else
      echo "ℹ️  Jenny AI Auto-Start is DISABLED (no LaunchAgent found)."
    fi
    exit 0
    ;;
  install)
    ;;
  *)
    echo "Usage: $0 [install|uninstall|status]"
    exit 1
    ;;
esac

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jenny.assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$APP_DIR/scripts/start-mac-menubar-tray.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "✅ Jenny AI Auto-Start enabled! Will automatically launch on Mac startup/restart."
echo "   To disable later: $0 uninstall"
