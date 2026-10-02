#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/mintcam"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# Copia progetto escludendo file non necessari
rsync -av \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='*.mp4' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.log' \
  "$PROJECT_DIR/" "$INSTALL_DIR/"

cd "$INSTALL_DIR"

# Crea/aggiorna il virtualenv
if [ ! -d ".venv" ]; then
    echo "Creazione virtualenv in $INSTALL_DIR ..."
    python3 -m venv .venv
else
    echo "Virtualenv esistente in $INSTALL_DIR"
fi

echo "Installazione dipendenze Python ..."
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Crea il launcher
cat > "$BIN_DIR/mintcam" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
source .venv/bin/activate
export QT_QPA_PLATFORM_PLUGIN_PATH="\$(python -c 'import PySide6; print(PySide6.__path__[0])')/Qt/plugins"
python -m app.main
EOF
chmod +x "$BIN_DIR/mintcam"

# Crea il .desktop
cat > "$DESKTOP_DIR/mintcam.desktop" <<EOF
[Desktop Entry]
Name=MintCam
Comment=Webcam app for Linux Mint
Exec=$BIN_DIR/mintcam
Icon=camera-photo
Terminal=false
Type=Application
Categories=AudioVideo;Video;Recorder;
Keywords=webcam;camera;video;recorder;
EOF
chmod +x "$DESKTOP_DIR/mintcam.desktop"

echo "MintCam installato per l'utente $USER."
echo "Avvia dal menu applicazioni o con: mintcam"
