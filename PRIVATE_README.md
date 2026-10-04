# MintCam – Internal development notes

This is the internal development document. Do not ship this publicly.

## Current state

- Working: live preview, photos, video recording/playback, filters, formats, timer, burst, recent media strip, folder opening, dark theme, desktop entry, .deb packaging.
- Verified on Linux Mint with user venv at `~/.local/share/mintcam/.venv`.
- System venv OpenCV must be 4.14.0; 5.0.0 breaks `CascadeClassifier` and related paths.

## Recent fixes

- Recording playback broken due to OpenCV FFmpeg writer path issues.
- Crash on stop due to UI-thread ffmpeg assembly and video thumbnail loading.
- Desktop launcher reliability improved with absolute `/usr/bin/mintcam` path.
- Timelapse writer guard added; frame buffer cleared after assembly.
- Face framing relies on `cv2.CascadeClassifier` with fallback logging.

## Packaging notes

- `.deb` built with `./build-deb.sh`
- Output: `dist/mintcam_0.1.0_all.deb`
- Launcher: `/usr/bin/mintcam`
- App data: `/usr/share/mintcam`
- User venv: `~/.local/share/mintcam/.venv`

## Internal TODOs

- Audio recording
- Real FPS counter
- Date/time overlay
- Digital zoom slider
- Configurable hotkeys
- Gallery thumbnails
- Advanced codec settings
- Multi-camera support
