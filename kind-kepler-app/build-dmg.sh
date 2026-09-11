#!/bin/bash

# Exit on error
set -e

echo "================ BUNDLING BINARIES ================"
# Clean old dist folder if exists
rm -rf dist
mkdir -p dist

# Compile server defined in server.js
echo "Compiling Web Assistant Server..."
./node_modules/.bin/pkg server.js --targets node18-macos-x64,node18-win-x64 --out-path dist

# Compile CLI defined in friday-cli.js
echo "Compiling Terminal CLI Assistant..."
./node_modules/.bin/pkg friday-cli.js --targets node18-macos-x64,node18-win-x64 --out-path dist

# Rename compiled outputs to friendly names
echo "Renaming compiled outputs..."
mv dist/server-macos dist/friday-server
mv dist/server-win.exe dist/friday-server.exe
mv dist/friday-cli-macos dist/friday-cli-macos
mv dist/friday-cli-win.exe dist/friday-cli-win.exe

echo "================ CREATING MACOS APP BUNDLE ================"
# Set up macOS App bundle directories
APP_DIR="dist/FRIDAY.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Run python image masking script first to ensure squircle transparency
if [ -f "mask_icon.py" ]; then
    echo "Applying Python Pillow macOS squircle masking to logo.png..."
    python3 mask_icon.py
fi

# Copy the server executable into the bundle as the backend binary
cp dist/friday-server "$MACOS_DIR/friday-server-bin"

# Create a bash wrapper executable for the app launcher to prevent window manager lockups
cat <<'EOF' > "$MACOS_DIR/friday-server"
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
# Clear Gatekeeper quarantine attributes
xattr -cr "$DIR/../.." 2>/dev/null || true
# Launch backend node server in background
"$DIR/friday-server-bin" > /tmp/friday_server.log 2>&1 &
EOF
chmod +x "$MACOS_DIR/friday-server"

# Create Custom App Icon from logo.png using sips and iconutil
if [ -f "logo.png" ]; then
    echo "Creating macOS AppIcon set..."
    mkdir -p logo.iconset
    
    sips -z 16 16     logo.png --out logo.iconset/icon_16x16.png
    sips -z 32 32     logo.png --out logo.iconset/icon_16x16@2x.png
    sips -z 32 32     logo.png --out logo.iconset/icon_32x32.png
    sips -z 64 64     logo.png --out logo.iconset/icon_32x32@2x.png
    sips -z 128 128   logo.png --out logo.iconset/icon_128x128.png
    sips -z 256 256   logo.png --out logo.iconset/icon_128x128@2x.png
    sips -z 256 256   logo.png --out logo.iconset/icon_256x256.png
    sips -z 512 512   logo.png --out logo.iconset/icon_256x256@2x.png
    sips -z 512 512   logo.png --out logo.iconset/icon_512x512.png
    sips -z 1024 1024 logo.png --out logo.iconset/icon_512x512@2x.png
    
    iconutil -c icns logo.iconset -o "$RESOURCES_DIR/AppIcon.icns"
    rm -rf logo.iconset
    echo "AppIcon.icns successfully compiled and bundled."
else
    echo "Warning: logo.png not found. App bundle will have default system icon."
fi

# Create Info.plist for macOS bundle metadata
cat <<EOF > "$CONTENTS_DIR/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>friday-server</string>
    <key>CFBundleIdentifier</key>
    <string>com.boss.friday</string>
    <key>CFBundleName</key>
    <string>FRIDAY</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon.icns</string>
</dict>
</plist>
EOF

echo "================ PACKAGING DMG DISK IMAGE ================"
# Create a staging folder for the DMG contents (so we include /Applications link)
echo "Preparing DMG Staging Area..."
rm -rf dist/dmg_stage
mkdir -p dist/dmg_stage

# Copy the app bundle into staging
cp -R dist/FRIDAY.app dist/dmg_stage/

# Clear Gatekeeper quarantine flags from files inside the app bundle
xattr -cr dist/dmg_stage/FRIDAY.app 2>/dev/null || true

# Create symlink to /Applications inside the staging folder
ln -s /Applications dist/dmg_stage/Applications

# Package into standard DMG using hdiutil pointing to staging folder
echo "Compiling DMG installer..."
hdiutil create -volname "FRIDAY Assistant" -srcfolder dist/dmg_stage -ov -format UDZO dist/FRIDAY_Assistant.dmg

echo "================ CLEANING UP ================"
# Clean up raw app bundle and staging directory
rm -rf dist/FRIDAY.app
rm -rf dist/dmg_stage

echo "================ BUILD SUCCESSFUL ================"
echo "Build outputs created in the dist/ folder:"
echo "1. dist/FRIDAY_Assistant.dmg (macOS standalone App installer with custom icon)"
echo "2. dist/friday-server.exe (Windows standalone web app runner)"
echo "3. dist/friday-cli-macos (macOS terminal assistant)"
echo "4. dist/friday-cli-win.exe (Windows terminal assistant)"
