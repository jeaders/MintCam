#!/usr/bin/env bash
# One-command installer for the MintCam APT repository.
# Usage: curl -fsSL https://mintcam.netlify.app/apt/install.sh | sudo bash
set -euo pipefail

REPO_URL="https://mintcam.netlify.app/apt"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo:  curl -fsSL $REPO_URL/install.sh | sudo bash" >&2
    exit 1
fi

need() { command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required tool: $1" >&2; exit 1; }; }
need curl
need gpg
need apt-get

echo "==> Importing MintCam repository signing key"
install -d -m 0755 /etc/apt/keyrings
curl -fsSL "$REPO_URL/mintcam-archive-key.asc" -o /tmp/mintcam-archive-key.asc
gpg --dearmor --yes -o /etc/apt/keyrings/mintcam.gpg /tmp/mintcam-archive-key.asc
chmod 0644 /etc/apt/keyrings/mintcam.gpg
rm -f /tmp/mintcam-archive-key.asc

echo "==> Adding MintCam repository"
echo "deb [signed-by=/etc/apt/keyrings/mintcam.gpg] $REPO_URL stable main" \
    > /etc/apt/sources.list.d/mintcam.list

echo "==> Installing MintCam"
apt-get update
apt-get install -y mintcam

echo
echo "MintCam installed. Launch it from the application menu or run 'mintcam'."
