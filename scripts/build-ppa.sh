#!/usr/bin/env bash
# Build the PPA source package for MintCam (Launchpad).
#
# IMPORTANT: Launchpad verifies the .dsc *inline* (clearsigned). A detached
# .dsc.asc is not accepted -> rejection "GPG verification ... (7, 58, 'No data')".
# dpkg-buildpackage -S produces a CLEAR-SIGNED .dsc automatically. Never sign
# the .dsc with `gpg --detach-sign`.
#
# The source tree is copied from the repo with explicit excludes (NOT git
# archive) so binary artefacts (apt/pool/*.deb, dist/, flatpak wheels) never
# end up inside the Debian source package.
#
# Usage: ./scripts/build-ppa.sh [upload]
#   without arguments: build only
#   with "upload": also upload with dput to ppa:jeaders/ppa
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(dpkg-parsechangelog -S Version -l "$REPO_DIR/debian/changelog" 2>/dev/null || echo 0.2.0)"
GPG_KEY="419E898D54713D236E923E5CD3A8A804EB07BFF9"
BUILD_ROOT="${BUILD_ROOT:-/tmp/mintcam-ppa-build}"
SRC_DIR="$BUILD_ROOT/mintcam-$VERSION"

echo "==> Building source package mintcam $VERSION"
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

rsync -a \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.kilo/' \
  --exclude='apt/' \
  --exclude='dist/' \
  --exclude='build-deb/' \
  --exclude='build-dir-clean/' \
  --exclude='flatpak-wheels/' \
  --exclude='flatpak-wheels.tar.gz' \
  --exclude='PUBLISHING_STATUS.md' \
  --exclude='index.html' \
  --exclude='logs/' \
  --exclude='photos/' \
  --exclude='recordings/' \
  --exclude='*.mp4' \
  --exclude='*.deb' \
  --exclude='*.log' \
  "$REPO_DIR/" "$SRC_DIR/"

cd "$SRC_DIR"

# -nc skips `debian/rules clean` (debhelper is a build-dependency, not needed
# to produce the source package); -k signs with the registered Launchpad key.
dpkg-buildpackage -S -nc --no-check-builddeps -k"$GPG_KEY"

echo "==> Verifying signatures"
gpg --verify "$BUILD_ROOT/mintcam_${VERSION}.dsc"
gpg --verify "$BUILD_ROOT/mintcam_${VERSION}_source.changes"

# Sanity checks a wrong .dsc would silently survive:
head -1 "$BUILD_ROOT/mintcam_${VERSION}.dsc" | grep -q "BEGIN PGP SIGNED MESSAGE" \
    || { echo "ERROR: .dsc is not clearsigned -- Launchpad will reject it"; exit 1; }
tar -tJf "$BUILD_ROOT/mintcam_${VERSION}.tar.xz" | grep -qE '\.deb$' \
    && { echo "ERROR: .deb artefact inside the source tarball"; exit 1; }

echo "==> Source package ready in $BUILD_ROOT"

if [ "${1:-}" = "upload" ]; then
    command -v dput >/dev/null 2>&1 || {
        echo "dput is not installed: sudo apt install dput"; exit 1; }
    echo "==> Uploading to ppa:jeaders/ppa with dput"
    dput ppa:jeaders/ppa "$BUILD_ROOT/mintcam_${VERSION}_source.changes"
else
    echo "To upload: dput ppa:jeaders/ppa $BUILD_ROOT/mintcam_${VERSION}_source.changes"
    echo "Monitor:   https://launchpad.net/~jeaders/+archive/ubuntu/ppa/+builds"
fi
