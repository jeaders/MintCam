#!/usr/bin/env bash
#
# MintCam Publishing Automation Script
# 
# This script prepares everything needed for publishing to both Flathub and PPA.
# It handles: deb build, source package creation, and file preparation.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "=== MintCam Publishing Helper ==="
echo ""
echo "Step 1: Building .deb package"
bash build-deb.sh

echo ""
echo "Step 2: Preparing source package for PPA"
mkdir -p debian/source
echo "3.0 (native)" > debian/source/format

# Clean any previous artifacts
rm -f ../mintcam_*.dsc ../mintcam_*.debian.tar.* ../mintcam_*.orig.tar.* ../mintcam_*.changes

# Build source package
if command -v dpkg-buildpackage &>/dev/null; then
    dpkg-buildpackage -S -us -uc -d
    echo "Source package built in parent directory"
else
    echo "WARNING: dpkg-buildpackage not available"
    echo "Create source archive manually:"
    tar --exclude='.git' --exclude='.venv' --exclude='build-deb' \
        --exclude='dist' --exclude='logs' --exclude='recordings' \
        --exclude='photos' --exclude='*.mp4' --exclude='*.log' \
        --exclude='__pycache__' --exclude='.pytest_cache' \
        -czf "../mintcam_0.1.0.orig.tar.gz" .
    echo "Created: ../mintcam_0.1.0.orig.tar.gz"
fi

echo ""
echo "=== Files ready for upload ==="
echo ".deb package: dist/mintcam_0.1.0_all.deb"
ls -la ../mintcam_* 2>/dev/null || true

echo ""
echo "=== Next steps for PPA (Launchpad) ==="
echo "1. Create account at https://launchpad.net"
echo "2. Create PPA: https://launchpad.net/~USERNAME/+addppa"
echo "3. Import Git repo: https://launchpad.net/~USERNAME/+git/mintcam"
echo "4. Link PPA to Git repo for auto-builds"
echo "5. Users install with: sudo add-apt-repository ppa:USERNAME/mintcam"

echo ""
echo "=== Next steps for Flathub ==="
echo "1. Fork https://github.com/flathub/flathub"
echo "2. Copy packaging/flathub/org.mintcam.MintCam/ to your fork"
echo "3. Rename manifest.json -> org.mintcam.MintCam.json"
echo "4. Open Pull Request"
echo "5. Flathub CI builds automatically with network access"
