#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Ambiente virtuale .venv non trovato."
    echo "Esegui:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

source .venv/bin/activate
export QT_QPA_PLATFORM_PLUGIN_PATH="$(python -c 'import PySide6; print(PySide6.__path__[0])')/Qt/plugins"
python -m app.main
