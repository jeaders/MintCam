#!/usr/bin/env bash
set -euo pipefail

# PPA Build & Upload Script for MintCam
# Requires: devscripts, debhelper, dput, lintian
# Usage: ./scripts/ppa-upload.sh

PKG_VERSION="0.1.0"
PPA_NAME="ppa:jeaders/mintcam"
DIST="focal"  # Ubuntu 20.04 LTS (base for Linux Mint 20.x)

echo "Building source package for PPA..."
dpkg-buildpackage -S -us -uc -d

echo "Uploading to $PPA_NAME for $DIST..."
dput "$PPA_NAME" "../mintcam_${PKG_VERSION}-1_source.changes"

echo "Upload complete. Check https://launchpad.net/~jeaders/+archive/ubuntu/mintcam"
echo "Users can install with:"
echo "  sudo add-apt-repository $PPA_NAME"
echo "  sudo apt update && sudo apt install mintcam"
