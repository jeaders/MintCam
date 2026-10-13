#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="0.7.0"
PKG_NAME="mintcam_${VERSION}_all.deb"
BUILD_DIR="${SCRIPT_DIR}/build-deb"
DIST_DIR="${SCRIPT_DIR}/dist"

rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR"/{DEBIAN,usr/bin,usr/share/applications,usr/share/metainfo,usr/share/pixmaps,usr/share/doc/mintcam,usr/share/man/man1,usr/share/mintcam,usr/share/mintcam/assets}
for size in 16 32 48 64 128 256 512; do
  mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/${size}x${size}/apps"
done
mkdir -p "$DIST_DIR"

# Control (single leading space on the extended description lines: Debian Policy)
cat > "$BUILD_DIR/DEBIAN/control" <<EOF
Package: mintcam
Version: $VERSION
Section: video
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pyqt6, python3-opencv, python3-numpy, python3-pil, python3-pyzbar, v4l-utils, ffmpeg, libxcb-cursor0, libzbar0, opencv-data
Maintainer: Alex Mirici <hilliedmikerano@gmail.com>
Homepage: https://github.com/jeaders/MintCam
Description: Webcam application for photo capture and video recording
 Live preview, photo capture and video recording with audio, plus QR
 scanning, focus assist, face auto framing, time-lapse, motion detection,
 background blur and RTMP streaming.
 .
 On first start the Python dependencies are installed into a per-user
 virtualenv.
EOF

# Launcher
install -m 0755 "${SCRIPT_DIR}/packaging/mintcam-launcher" "$BUILD_DIR/usr/bin/mintcam"

# Manual page
install -m 0644 "${SCRIPT_DIR}/packaging/mintcam.1" "$BUILD_DIR/usr/share/man/man1/mintcam.1"

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
rsync -a \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='build-deb' \
  --exclude='dist' \
  --exclude='*.mp4' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.log' \
  "${SCRIPT_DIR}/app" "${SCRIPT_DIR}/README.md" \
  "$BUILD_DIR/usr/share/mintcam/"

# Traduzioni dell'interfaccia (file .qm compilati)
install -d "$BUILD_DIR/usr/share/mintcam/i18n"
install -m 0644 "${SCRIPT_DIR}"/i18n/*.qm "$BUILD_DIR/usr/share/mintcam/i18n/"

# /usr/share/doc: copyright must be plain text (Policy 12.5), changelog compressed
install -m 0644 "${SCRIPT_DIR}/debian/copyright" "$BUILD_DIR/usr/share/doc/mintcam/copyright"
gzip -9 -n -c "${SCRIPT_DIR}/debian/changelog" > "$BUILD_DIR/usr/share/doc/mintcam/changelog.gz"

# Normalise permissions and ownership: Debian packages are root:root,
# directories 0755, regular files 0644, executables 0755.
find "$BUILD_DIR" -type d -exec chmod 0755 {} +
find "$BUILD_DIR" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD_DIR/usr/bin/mintcam"
chmod 0644 "$BUILD_DIR/DEBIAN/control"

# Compress the manual page
gzip -9 -n "$BUILD_DIR/usr/share/man/man1/mintcam.1"

# Build under fakeroot so the archive entries are owned by root:root
fakeroot dpkg-deb --build "$BUILD_DIR" "${DIST_DIR}/${PKG_NAME}"

echo "Pacchetto creato: ${DIST_DIR}/${PKG_NAME}"
