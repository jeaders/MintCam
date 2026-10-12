#!/usr/bin/env bash
# Build the Debian (mentors.debian.net) source package for MintCam.
#
# Debian reviews expect a non-native package: an upstream tarball plus a
# separate Debian tarball, and a version with a Debian revision. So this
# produces mintcam_0.2.1-1.{dsc,changes} with 3.0 (quilt) format and
# distribution "unstable", ready for:
#   dput mentors mintcam_0.2.1-1_source.changes
#
# Usage: ./scripts/build-debian.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The version is pinned while the RFS (bug 1150664) is under review:
# the sponsor reviews exactly this version, so it must not drift.
VERSION="0.2.7"
REVISION="1"
DEB_VERSION="${VERSION}-${REVISION}"
GPG_KEY="419E898D54713D236E923E5CD3A8A804EB07BFF9"
BUILD_ROOT="${BUILD_ROOT:-/tmp/mintcam-debian}"
SRC_DIR="$BUILD_ROOT/mintcam-${VERSION}"

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
  --exclude='SPONSORSHIP_REQUEST.md' \
  --exclude='Docs/' \
  --exclude='index.html' \
  --exclude='logs/' \
  --exclude='*.mp4' \
  --exclude='*.deb' \
  --exclude='*.log' \
  "$REPO_DIR/" "$SRC_DIR/"

cd "$SRC_DIR"

# Debian style: quilt format, one tarball for upstream, one for Debian.
echo "3.0 (quilt)" > debian/source/format

# Debian changelog: a single entry with the Debian revision. Fill in the ITP
# bug number after filing the Intent To Package on bugs.debian.org.
cat > debian/changelog <<EOF
mintcam (${DEB_VERSION}) UNRELEASED; urgency=medium

  * Initial Debian packaging (Closes: #1150659): webcam application, MIT,
    built from the 0.2.3 upstream release.
  * Use the Python modules from the archive: python3-pyqt6, python3-opencv,
    python3-numpy, python3-pil, python3-pyzbar. The previous revision shipped
    requirements.txt and pip-installed it into a per-user virtualenv on first
    start, which cannot be accepted in Debian. The app was ported from PySide6
    to PyQt6 for this reason; PySide6 is not packaged in Ubuntu.

 -- Alex Mirici <hilliedmikerano@gmail.com>  Sun, 11 Oct 2026 20:00:00 +0200
EOF

# Non-native build: Debian wants an upstream tarball plus a Debian tarball,
# so the orig tarball has to exist before dpkg-source runs.
tar -cJf "../mintcam_${VERSION}.orig.tar.xz" \
    --exclude='debian' --exclude-vcs \
    -C "$BUILD_ROOT" "mintcam-${VERSION}"

dpkg-source -b .

# Sign the .dsc inline (clearsigned): dput and the Debian importer both verify
# it, and a detached signature is not accepted. This must happen before the
# .changes is generated, because the .changes records the checksums of the
# signed .dsc.
gpg --batch --yes --local-user "$GPG_KEY" --clearsign \
    --output "../mintcam_${DEB_VERSION}.dsc.signed" \
    "../mintcam_${DEB_VERSION}.dsc"
mv "../mintcam_${DEB_VERSION}.dsc.signed" "../mintcam_${DEB_VERSION}.dsc"

dpkg-genchanges -S > "../mintcam_${DEB_VERSION}_source.changes"

gpg --batch --yes --local-user "$GPG_KEY" --clearsign \
    --output "../mintcam_${DEB_VERSION}_source.changes.new" \
    "../mintcam_${DEB_VERSION}_source.changes"
mv "../mintcam_${DEB_VERSION}_source.changes.new" \
   "../mintcam_${DEB_VERSION}_source.changes"

# The .dsc itself is not signed for Debian uploads; mentors checks the
# .changes signature and the .buildinfo if present.
echo "==> Verifying signature"
gpg --verify "../mintcam_${DEB_VERSION}_source.changes"

echo "==> Source package ready in $BUILD_ROOT"
ls -la "$BUILD_ROOT"
echo "Upload with:  dput mentors $BUILD_ROOT/mintcam_${DEB_VERSION}_source.changes"
