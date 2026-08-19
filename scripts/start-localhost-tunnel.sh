#!/bin/bash
# ============================================================
#  JENNY Localhost Tunnel Watcher
#  Usage: bash scripts/start-localhost-tunnel.sh
# ============================================================

set -e

# Clean up old status
rm -f /tmp/jenny-remote-url.txt

echo "[*] Launching localhost.run tunnel for port 3005..."
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:3005 nokey@localhost.run 2>&1 | while read -r line; do
  echo "$line"
  # Match the tunneled URL from output line
  if echo "$line" | grep -q "tunneled with tls termination"; then
    URL=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9.-]+\.lhr\.life')
    if [ -n "$URL" ]; then
      echo "$URL" > /tmp/jenny-remote-url.txt
      echo "[*] Tunneled successfully: $URL"
    fi
  fi
done
