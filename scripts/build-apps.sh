#!/bin/bash
# Build macOS native apps from Swift source files
# Requires: macOS with Xcode Command Line Tools (swiftc)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BIN_DIR="$PROJECT_DIR/bin"
SRC_MENU="$SCRIPT_DIR/JennyMenuBarApp.swift"
SRC_DESKTOP="$SCRIPT_DIR/JennyDesktopApp.swift"

echo "=========================================================="
echo "  JENNY AI - Building Native macOS Apps"
echo "=========================================================="

# Create bin directory
mkdir -p "$BIN_DIR"

# Build Menu Bar App
echo ""
echo "Building Menu Bar App..."
swiftc "$SRC_MENU" \
  -o "$BIN_DIR/JennyMenuBarApp" \
  -framework Cocoa \
  -framework WebKit \
  -target "$(uname -m)-apple-macosx12.0"

# Create JennyAI.app bundle
mkdir -p "$BIN_DIR/JennyAI.app/Contents/MacOS"
mkdir -p "$BIN_DIR/JennyAI.app/Contents/Resources"
cp "$BIN_DIR/JennyMenuBarApp" "$BIN_DIR/JennyAI.app/Contents/MacOS/JennyMenuBarApp"
cp "$BIN_DIR/JennyAI.app/Contents/Resources/AppIcon.icns" "$BIN_DIR/JennyAI.app/Contents/Resources/AppIcon.icns" 2>/dev/null || true

cat > "$BIN_DIR/JennyAI.app/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>JennyMenuBarApp</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.jenny.menubar</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>JENNY</string>
    <key>CFBundleDisplayName</key>
    <string>JENNY</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleVersion</key>
    <string>2.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST
echo "  JennyAI.app bundle created"

# Build Desktop App
echo ""
echo "Building Desktop App..."
swiftc "$SRC_DESKTOP" \
  -o "$BIN_DIR/JennyDesktop" \
  -framework Cocoa \
  -framework WebKit \
  -target "$(uname -m)-apple-macosx12.0"

# Create JennyDesktop.app bundle
mkdir -p "$BIN_DIR/JennyDesktop.app/Contents/MacOS"
mkdir -p "$BIN_DIR/JennyDesktop.app/Contents/Resources"
cp "$BIN_DIR/JennyDesktop" "$BIN_DIR/JennyDesktop.app/Contents/MacOS/JennyDesktop"
cp "$BIN_DIR/JennyDesktop.app/Contents/Resources/AppIcon.icns" "$BIN_DIR/JennyDesktop.app/Contents/Resources/AppIcon.icns" 2>/dev/null || true

cat > "$BIN_DIR/JennyDesktop.app/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>JennyDesktop</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.jenny.desktop</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>JENNY Desktop</string>
    <key>CFBundleDisplayName</key>
    <string>JENNY Desktop</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleVersion</key>
    <string>2.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST
echo "  JennyDesktop.app bundle created"

echo ""
echo "=========================================================="
echo "  Build complete!"
echo "  Menu Bar App: $BIN_DIR/JennyAI.app"
echo "  Desktop App:  $BIN_DIR/JennyDesktop.app"
echo "=========================================================="
