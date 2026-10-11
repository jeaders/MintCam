# Sponsorship request for MintCam (universe)

Send this to **ubuntu-motu@lists.ubuntu.com** (subscribe first, the list only
accepts members) after the PPA build succeeds, and only after you ran `lintian`
on the package and fixed or understood everything it reports.

Subject: `[Sponsorship request] mintcam 0.2.0 (universe)`

---

Hello,

I would like to get MintCam into universe and I am looking for a sponsor.

MintCam is a small PySide6 webcam app I originally wrote for myself: live
preview, photo capture, video recording with audio through ffmpeg, QR scanning,
focus assist, face auto framing, time lapse, motion detection and RTMP
streaming. It is MIT licensed and developed on GitHub:

    https://github.com/jeaders/MintCam

This is my first Debian package, so I fully expect some back and forth. The
package builds and is signed here (source and built debs):

    https://launchpad.net/~jeaders/+archive/ubuntu/ppa/+packages

Packaging is native, arch: all, debhelper-compat (= 13), and the appdata
component id is "mintcam" to match mintcam.desktop as the Debian AppStream
policy asks.

The one decision I want to flag before you read the diff: the app needs
PySide6, opencv, numpy, pyzbar and Pillow. PySide6 on its own is already split
into many small packages in Ubuntu, and I did not want to vendor a few hundred
megabytes of wheels into the source. So the package ships requirements.txt and
/usr/bin/mintcam builds a per user virtualenv under
~/.local/share/mintcam/.venv on first start and pip installs into it. Anything
that has to come from the archive does: v4l-utils, ffmpeg, libxcb-cursor0,
python3-venv and python3-pip are all in Depends. I wrote the reasoning down in
debian/README.source. If you would rather see the Ubuntu python modules used
directly, tell me and I will do it.

Known rough edges, so you do not have to hunt for them:

- first start needs the network and takes a minute or two while pip runs
- the icon ships only as PNG in the hicolor theme, no SVG yet
- recordings are written under XDG_VIDEOS_DIR, which I only tested on Mint

The changelog and copyright file are in the source package, contact details in
debian/control.

Thanks for having a look,
Alex Mirici

---

## Before sending, checklist

1. `sudo apt install dput lintian` (dput uploads, lintian is what reviewers run)
2. Upload the package so the build link above is valid:
   `dput ppa:jeaders/ppa /tmp/mintcam-ppa-build/mintcam_0.2.0_source.changes`
3. Wait for the PPA build to reach "Successfully built" and the .deb to be
   published, otherwise a reviewer cannot install what you are asking about
4. `lintian -i /tmp/mintcam-ppa-build/mintcam_0.2.0_source.changes` and fix what
   you can. The tags a reviewer will definitely look at are the ones about
   debian/copyright, the appdata file and missing debian/watch
5. Subscribe to ubuntu-motu and send the mail (keep the same tone: short,
   concrete, no marketing language)
