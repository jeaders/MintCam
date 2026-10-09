# MintCam Publishing Status

## PPA (Launchpad) — https://launchpad.net/~jeaders/+archive/ubuntu/ppa

### Upload Status
- **Source package**: Uploaded ✓
- **GPG key**: Registered and confirmed ✓ (fingerprint: `2E7B91458E94B7406900E3312D4D6DCD55745DDF`)
- **Distribution**: `noble` (Ubuntu 24.04 LTS) ✓
- **Build**: Completed after fixing `dh_auto_configure` override
- **Publishing**: In progress — signing key auto-generation pending

### PPA Signing Key
- **Status**: `None` (auto-generation in progress — up to 24h after first successful build)
- **Checked**: 2026-10-09 13:05 — still null
- **Monitor**: https://launchpad.net/~jeaders/+archive/ubuntu/ppa
  ```bash
  sudo add-apt-repository ppa:jeaders/ppa
  sudo apt update
  sudo apt install mintcam
  ```

## GitHub — https://github.com/jeaders/MintCam

### Status
- **Commits**: Pushed ✓
- **Tags**: `v0.1.0` and `v0.2.0` pushed ✓
- **Release**: v0.2.0 created with demo video asset ✓
- **Google site verification**: Meta tag committed ✓

---

## Flathub — PR #10572 (https://github.com/flathub/flathub/pull/10572)

### Status: ⛔ Closed (auto-closed by submission-checker bot — awaiting re-evaluation)

### Workflow
1. Forked `flathub/flathub` → `jeaders/flathub` ✓
2. Created branch `flathub-submit` from `new-pr` ✓
3. Copied manifest + flathub.json + screenshots ✓
4. Pushed to fork ✓
5. Opened PR against `flathub:new-pr` ✓
6. **Bot closed**: "Checklist(s) not completed or missing"
7. **Fixed**: Updated PR description with full checklist (all `[X]` checked) ✓
8. Posted comment to trigger re-evaluation ✓
9. Bot re-runs hourly — waiting for next cycle

### Files in PR
| File | Purpose |
|------|---------|
| `io.github.jeaders.MintCam.json` | Manifest with 9 PyPI wheel URL sources (SHA256 verified) |
| `flathub.json` | `{"only-arches": ["x86_64"]}` |
| `screenshots/screenshot.png` | App screenshot (95KB) |
| `screenshots/mintcam-app-1600x900.png` | Desktop screenshot (240KB) |
| `screenshots/mintcam-banner-1600x900.png` | Banner screenshot (360KB) |
- **Release**: Created on GitHub ✓
- **Google site verification**: Added to `index.html` ✓

---

## Flathub — https://flathub.org/apps/io.github.jeaders.MintCam

### Status
- **Local build**: Built and tested ✓
  - App launches: `Avvio MintCam` ✓
  - OpenCV webcam access ✓
  - Audio recording module ✓
  - Python 3.13 wheels installed ✓
- **App ID**: `io.github.jeaders.MintCam` (GitHub-hosted, auto-verified)
- **Runtime**: `org.freedesktop.Platform` 25.08

### Submission Files (ready in `packaging/flathub/io.github.jeaders.MintCam/`)
| File | Purpose |
|------|---------|
| `io.github.jeaders.MintCam.json` | Flatpak manifest with PyPI URL sources |
| `flathub.json` | Build config (x86_64 only) |
| `README.md` | Submission notes |
| `screenshots/` | App screenshots for Flathub website |

### Linter Results
- AppStream validation: ✓ (only warnings about screenshot URL accessibility and developer-info)
- Flatpak builder lint: 4 errors (require reviewer exceptions or fixes):
  1. `--socket=session-bus` (arbitrary dbus access) — needed for Qt/desktop integration
  2. `--filesystem=home` (home filesystem access) — needed for saving recordings
  3. `--device=all` (broad device access) — needed for webcam + ALSA audio
  4. `--socket=x11` + `--socket=wayland` (both) — standard for Qt apps

### Pending PPA items (separate from Flathub)
- PPA signing key auto-generation (up to 24h after build)
- apt repository becomes available after signing key

## Website
- **URL**: `https://mintcam.netlify.app`
- **Status**: `index.html` in repo, deployed to Netlify
- **Google verification**: Meta tag committed ✓

## Files Summary
| Item | Location |
|------|----------|
| PPA source (.tar.gz on desktop) | Debian packages — NOT for Flathub |
| Flatpak local manifest | `flatpak-manifest.json` |
| Flathub submission manifest | `packaging/flathub/io.github.jeaders.MintCam/io.github.jeaders.MintCam.json` |
| PyPI wheel URLs + SHA256 | In submission manifest |
| App source (git) | GitHub `v0.2.0` tag |
| Website | Netlify deployment |
