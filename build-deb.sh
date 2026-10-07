#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="0.1.0"
PKG_NAME="mintcam_${VERSION}_all.deb"
BUILD_DIR="${SCRIPT_DIR}/build-deb"
DIST_DIR="${SCRIPT_DIR}/dist"

rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR"/{DEBIAN,usr/bin,usr/share/applications,usr/share/metainfo,usr/share/pixmaps,usr/share/mintcam,usr/share/mintcam/assets,usr/share/icons/hicolor/16x16/apps,usr/share/icons/hicolor/32x32/apps,usr/share/icons/hicolor/48x48/apps,usr/share/icons/hicolor/64x64/apps,usr/share/icons/hicolor/128x128/apps,usr/share/icons/hicolor/256x256/apps,usr/share/icons/hicolor/512x512/apps}
mkdir -p "$DIST_DIR"

# Control
cat > "$BUILD_DIR/DEBIAN/control" <<EOF
Package: mintcam
Version: $VERSION
Section: video
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pip, python3-venv, v4l-utils, ffmpeg, libxcb-cursor0
Maintainer: jead <hilliedmikerano@gmail.com>
Homepage: https://github.com/jeaders/MintCam
Description: MintCam - Webcam app for Linux Mint
  Lightweight desktop webcam application for Linux Mint.
  Features live preview, photo capture with burst mode, video recording
  with audio support, RTMP live streaming, QR scanner, focus assist,
  face auto-framing, time-lapse, motion detection, background blur
  (Bokeh), preset management, digital zoom, social sharing, and dark
  theme UI.
EOF

# Launcher
install -m 0755 "${SCRIPT_DIR}/packaging/mintcam-launcher" "$BUILD_DIR/usr/bin/mintcam"

# Desktop file
install -m 0644 "${SCRIPT_DIR}/packaging/mintcam.desktop" "$BUILD_DIR/usr/share/applications/mintcam.desktop"

# AppStream metadata
install -m 0644 "${SCRIPT_DIR}/mintcam.appdata.xml" "$BUILD_DIR/usr/share/metainfo/mintcam.appdata.xml"

# Icon - install PNG in pixmaps and hicolor theme directories
install -m 0644 "${SCRIPT_DIR}/assets/mintcam.png" "$BUILD_DIR/usr/share/pixmaps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/mintcam-logo.jpg" "$BUILD_DIR/usr/share/mintcam/assets/mintcam-logo.jpg"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-16.png" "$BUILD_DIR/usr/share/icons/hicolor/16x16/apps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-32.png" "$BUILD_DIR/usr/share/icons/hicolor/32x32/apps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-48.png" "$BUILD_DIR/usr/share/icons/hicolor/48x48/apps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-64.png" "$BUILD_DIR/usr/share/icons/hicolor/64x64/apps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-128.png" "$BUILD_DIR/usr/share/icons/hicolor/128x128/apps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-256.png" "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/mintcam.png"
install -m 0644 "${SCRIPT_DIR}/assets/icons/mintcam-512.png" "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps/mintcam.png"

# App files
rsync -av \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='build-deb' \
  --exclude='dist' \
  --exclude='*.mp4' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.log' \
  "${SCRIPT_DIR}/app" "${SCRIPT_DIR}/requirements.txt" "${SCRIPT_DIR}/run.sh" "${SCRIPT_DIR}/README.md" \
  "$BUILD_DIR/usr/share/mintcam/"

# Permissions
chmod 0644 "$BUILD_DIR/usr/share/applications/mintcam.desktop"
chmod 0644 "$BUILD_DIR/usr/share/metainfo/mintcam.appdata.xml"
chmod 0644 "$BUILD_DIR/usr/share/pixmaps/mintcam.png"
chmod 0644 "$BUILD_DIR/usr/share/icons/hicolor/"*/apps/mintcam.png

# Build
dpkg-deb --build "$BUILD_DIR" "${DIST_DIR}/${PKG_NAME}"

echo "Pacchetto creato: ${DIST_DIR}/${PKG_NAME}"
