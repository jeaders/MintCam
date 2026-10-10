# MintCam on Flathub

**App ID:** `io.github.jeaders.MintCam`
**Runtime:** `org.freedesktop.Platform` 25.08
**License:** MIT

## What this directory contains

- `io.github.jeaders.MintCam.json` — the Flatpak manifest
- `flathub.json` — restricts builds to x86_64 (aarch64 not yet tested)
- `screenshots/` — images for the submission PR

## Build locally

```bash
flatpak-builder --user --install --force-clean ../build-dir io.github.jeaders.MintCam.json
flatpak run io.github.jeaders.MintCam
```

## Submission notes

The manifest pulls source from the `v0.2.0` tag on GitHub. All PyPI
dependencies are bundled as pre-built wheels with SHA256 checksums
(verified via the PyPI JSON API). No network access is needed at build time.

### Permissions explained

- `--device=all` — webcam + USB audio capture (needed for OpenCV + ALSA)
- `--filesystem=home` — save photos, videos, logs to the user's home directory
- `--socket=x11` + `--socket=wayland` — display server access (Qt needs both)
- `--socket=session-bus` — Qt desktop integration
- `--share=network` — RTMP streaming (optional feature, can be removed if not needed)
