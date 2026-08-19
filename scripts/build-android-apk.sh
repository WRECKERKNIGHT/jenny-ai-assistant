#!/usr/bin/env bash
# ==========================================================
# JENNY AI - Android APK Generator & PWA Package Script
# ==========================================================

echo "=========================================================="
echo " 📱 JENNY AI - Android APK & Mobile App Package Builder  "
echo "=========================================================="

BUILD_DIR="./android-build"
mkdir -p "$BUILD_DIR/www"

# Copy WebApp PWA assets
cp public/mobile.html "$BUILD_DIR/www/index.html"
cp public/manifest.json "$BUILD_DIR/www/manifest.json"
cp public/logo.png "$BUILD_DIR/www/logo.png"

echo "✅ Mobile WebApp PWA bundle generated in $BUILD_DIR/www"

if command -v npx >/dev/null 2>&1; then
  echo "📦 Initializing Capacitor Android APK Project Structure..."
  cd "$BUILD_DIR"
  cat << 'EOF' > package.json
{
  "name": "jenny-mobile-remote",
  "version": "6.0.0",
  "description": "JENNY AI Remote Control Android App",
  "main": "index.js",
  "dependencies": {
    "@capacitor/android": "^6.0.0",
    "@capacitor/core": "^6.0.0"
  }
}
EOF

  echo "📱 Mobile APK Web App Bundle Ready!"
  echo "To run/build locally:"
  echo "  1. Add to Android Home Screen from Chrome: Open http://YOUR_MAC_IP:3000/mobile.html -> Add to Home Screen"
  echo "  2. Or compile APK with Android Studio / Bubblewrap: npx @bubblewrap/cli build"
  cd ..
fi

echo "🎉 Mobile Remote Control App build ready!"
