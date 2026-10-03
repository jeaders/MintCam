#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="0.1.0"
PKG_NAME="mintcam_${VERSION}_all.deb"
BUILD_DIR="${SCRIPT_DIR}/build-deb"
DIST_DIR="${SCRIPT_DIR}/dist"

rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR"/{DEBIAN,usr/bin,usr/share/applications,usr/share/metainfo,usr/share/pixmaps,usr/share/mintcam}
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
 Features live preview, photo capture with timer, video recording,
 basic filters and adjustments, multiple camera support and dark theme UI.
EOF

# Launcher
install -m 0755 "${SCRIPT_DIR}/packaging/mintcam-launcher" "$BUILD_DIR/usr/bin/mintcam"

# Desktop file
install -m 0644 "${SCRIPT_DIR}/packaging/mintcam.desktop" "$BUILD_DIR/usr/share/applications/mintcam.desktop"

# AppStream metadata
install -m 0644 "${SCRIPT_DIR}/mintcam.appdata.xml" "$BUILD_DIR/usr/share/metainfo/mintcam.appdata.xml"

# Icon
install -m 0644 "${SCRIPT_DIR}/assets/mintcam-logo.jpg" "$BUILD_DIR/usr/share/pixmaps/mintcam-logo.jpg"

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
chmod 0644 "$BUILD_DIR/usr/share/pixmaps/mintcam-logo.jpg"

# Build
dpkg-deb --build "$BUILD_DIR" "${DIST_DIR}/${PKG_NAME}"

echo "Pacchetto creato: ${DIST_DIR}/${PKG_NAME}"
