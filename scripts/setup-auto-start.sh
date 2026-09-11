#!/bin/bash
# macOS Auto-Start Setup for Jenny AI on Boot/Login

PLIST_PATH="$HOME/Library/LaunchAgents/com.jenny.assistant.plist"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

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
