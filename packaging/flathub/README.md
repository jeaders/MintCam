# MintCam on Flathub

**App ID:** `org.mintcam.MintCam`
**Runtime:** `org.freedesktop.Platform` 25.08
**License:** GPL-3.0-or-later

## Publishing Steps

1. **Fork** https://github.com/flathub/flathub
2. **Copy** this directory into your fork as `python3/mintcam.json`:
   ```bash
   cp -r packaging/flathub/org.mintcam.MintCam/ /path/to/flathub-fork/python3/
   cp /path/to/flathub-fork/python3/mintcam.json
   ```
3. **Add** `mintcam.png` to `icons/256x256/apps/` in the Flathub repo
4. **Upload** screenshots to a public HTTPS URL (update AppData references)
5. **Commit** and **push** to your fork
6. **Open a PR** to https://github.com/flathub/flathub

## Prerequisites
- Screenshots must be at least 1280x720, preferably 1600x900
- AppData must reference HTTPS screenshot URLs
- Icons must be 256x256 PNG in hicolor theme
- Flatpak manifest uses offline pip wheels (no network during build required)

## Testing Locally

### Build (requires flatpak + flatpak-builder)
```bash
flatpak-builder --user --install --force-clean build-dir manifest.json
flatpak run org.mintcam.MintCam
```

### Local installation (via Flathub after approval)
```bash
flatpak install flathub org.mintcam.MintCam
```

## Offline Build Dependencies

All Python wheels are bundled in `../../../flatpak-wheels.tar.gz` (338MB).
To regenerate:
```bash
pip download -r requirements.txt --dest flatpak-wheels/
tar czf flatpak-wheels.tar.gz -C flatpak-wheels/ *.whl
```
