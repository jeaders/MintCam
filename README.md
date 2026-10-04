# MintCam

Lightweight desktop webcam app for Linux Mint.
Live preview, photo capture, video recording, filters, QR/Barcode scanning, focus assist, face auto-framing, time-lapse, and MintCast virtual webcam.

## Screenshots

<img src="https://raw.githubusercontent.com/jeaders/MintCam/main/assets/screenshot.png" alt="MintCam screenshot" width="720">

## Features

- Live webcam preview with OpenCV
- Photo capture with auto-save in `~/MintCam/photos`
- Video recording in `~/MintCam/recordings`
- Device selection with webcam name
- Resolutions: 640x480, 1280x720, 1920x1080 (if supported)
- FPS: 1-120
- Filters: Normal, Grayscale, Sepia, Negative, High contrast
- Live mirror
- Composition grid
- Formats: 16:9, 4:3, 9:16
- Photo timer: 3, 5, 10 seconds
- Photo burst: 3, 5, 10 shots
- Adjustments: brightness, contrast, saturation
- Focus assist with visual indicator
- Live QR/Barcode scanner
- Face auto-framing
- Time-lapse with automatic MP4 assembly
- MintCast virtual webcam
- Preview pause
- Recording duration limit
- Adjustable photo quality
- Open photo/video folder
- Autostart with system
- Modern dark theme
- Custom icon

## Requirements

- Linux Mint 21+ (or compatible)
- Python 3.10 or newer
- `python3-venv`, `python3-pip`
- `v4l-utils`
- `ffmpeg`
- `libxcb-cursor0`
- `pyzbar`, `Pillow`

## Installation

### From .deb

```bash
sudo dpkg -i dist/mintcam_0.1.0_all.deb
```

### From source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x run.sh
./run.sh
```

### Local install script

```bash
chmod +x install-local.sh
./install-local.sh
```

Then search for **MintCam** in the Linux Mint menu, or run:

```bash
mintcam
```

### Uninstall

```bash
sudo dpkg --purge mintcam || true
rm -f ~/.local/share/applications/mintcam.desktop
rm -rf ~/.local/share/mintcam
rm -f ~/.local/bin/mintcam
```

## Verify webcam

```bash
v4l2-ctl --list-devices
v4l2-ctl --list-formats-ext -d /dev/video0
```

## Autostart

1. Open Menu → Preferences → Startup Applications
2. Add
3. Name: `MintCam`
4. Command: `mintcam`
5. Save

## MintCast virtual webcam (optional)

```bash
sudo apt install v4l2loopback-dkms
sudo modprobe v4l2loopback
```

Then enable "MintCast virtual cam" in the app.

## Known issues

- Video recording is silent in this release.
- Some preview/recording behavior depends on webcam driver capabilities.
- If the app does not start from the menu, run `/usr/bin/mintcam` from a terminal once so the user venv is created.

## Changelog

### 0.1.0
- Initial public release
- Live preview, photo, video recording
- Filters, adjustments, formats, timer, burst
- QR/Barcode, focus assist, face framing, time-lapse
- MintCast virtual webcam
- Dark theme and custom icon
- .deb package for Linux Mint

## License

Prototype without a defined license.
