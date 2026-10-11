#!/usr/bin/env bash
# Regenerate the APT repository served at https://jeaders.github.io/MintCam/apt
# Usage: ./scripts/update-apt-repo.sh [path-to-deb]
# Run ./build-deb.sh first, or pass a .deb explicitly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APT_DIR="$REPO_DIR/apt"
SUITE="stable"
GPG_KEY="419E898D54713D236E923E5CD3A8A804EB07BFF9"
KEY_FINGERPRINT="2E7B91458E94B7406900E3312D4D6DCD55745DDF"

DEB="${1:-$REPO_DIR/dist/mintcam_0.2.0_all.deb}"

# Reset only the generated parts, keep install.sh and the exported key.
rm -rf "$APT_DIR/dists" "$APT_DIR/pool"
mkdir -p "$APT_DIR/pool/main/m/mintcam" "$APT_DIR/dists/$SUITE/main/binary-all"

cp "$DEB" "$APT_DIR/pool/main/m/mintcam/"

# Public key users import with `signed-by`
gpg --export --armor "$KEY_FINGERPRINT" > "$APT_DIR/mintcam-archive-key.asc"

cd "$APT_DIR"
dpkg-scanpackages --arch all pool /dev/null > "dists/$SUITE/main/binary-all/Packages"
gzip -9 -c "dists/$SUITE/main/binary-all/Packages" > "dists/$SUITE/main/binary-all/Packages.gz"

apt-ftparchive \
  -o APT::FTPArchive::Release::Origin="MintCam" \
  -o APT::FTPArchive::Release::Suite="$SUITE" \
  -o APT::FTPArchive::Release::Codename="$SUITE" \
  -o APT::FTPArchive::Release::Architectures="all" \
  -o APT::FTPArchive::Release::Components="main" \
  -o APT::FTPArchive::Release::Description="MintCam package repository" \
  release "dists/$SUITE" > "dists/$SUITE/Release"

gpg --batch --yes --local-user "$GPG_KEY" --detach-sign --armor \
    -o "dists/$SUITE/Release.gpg" "dists/$SUITE/Release"
gpg --batch --yes --local-user "$GPG_KEY" --clearsign \
    -o "dists/$SUITE/InRelease" "dists/$SUITE/Release"

echo "APT repository rebuilt in $APT_DIR"
echo "Commit and push 'apt/' so Netlify publishes it, then run:"
echo "  sudo apt update && sudo apt install mintcam"
