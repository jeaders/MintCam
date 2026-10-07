# MintCam on Flathub

**App ID:** `org.mintcam.MintCam`

## Publishing Steps

1. Fork https://github.com/flathub/flathub
2. Copy this directory into your fork:
   ```
   cp -r org.mintcam.MintCam/ /path/to/flathub-fork/
   ```
3. Rename `manifest.json` to `org.mintcam.MintCam.json`
4. Ensure screenshots are 1600x900 (resize if needed)
5. Commit and push
6. Open a PR to https://github.com/flathub/flathub

## Prerequisites
- Screenshots must be at least 1280x720, preferably 1600x900
- AppData must reference HTTPS screenshot URLs (done)
- Icons must be 256x256 PNG in hicolor theme (done)

## Testing Locally
```bash
flatpak-builder --user --install --force-clean build-dir manifest.json
flatpak run org.mintcam.MintCam
```
