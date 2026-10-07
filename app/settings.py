import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("mintcam.settings")

DEFAULTS: dict[str, Any] = {
    "camera_index": 0,
    "resolution": "640x480",
    "fps": 30,
    "filter": "Normale",
    "format": "16:9",
    "timer_seconds": 0,
    "brightness": 0,
    "contrast": 0,
    "saturation": 0,
    "last_photo_dir": "",
    "last_recording_dir": "",
    "autostart": False,
    "mirror": False,
    "zoom": 100,
    "grid": False,
    "burst_count": 1,
    "pause_preview": False,
    "clip_seconds": 0,
    "photo_quality": 95,
    "qr_enabled": False,
    "focus_assist": False,
    "face_framing": False,
    "audio_enabled": False,
    "background_blur": False,
    "blur_strength": 15,
    "motion_detection": False,
    "motion_sensitivity": 20,
    "timelapse": False,
    "timelapse_interval": 1,
    "presets": {},
}


class Settings:
    FILE = Path.home() / "MintCam" / "settings.json"

    def __init__(self) -> None:
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            if self.FILE.exists():
                with open(self.FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._data.update({k: data.get(k, v) for k, v in DEFAULTS.items()})
        except Exception as exc:
            logger.warning("Impossibile caricare le impostazioni: %s", exc)

    def save(self) -> None:
        try:
            self.FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("Impossibile salvare le impostazioni: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def get_presets(self) -> dict:
        return dict(self._data.get("presets", {}))

    def save_preset(self, name: str, values: dict) -> None:
        presets = self._data.get("presets", {})
        presets[name] = values
        self._data["presets"] = presets
        self.save()

    def delete_preset(self, name: str) -> None:
        presets = self._data.get("presets", {})
        presets.pop(name, None)
        self._data["presets"] = presets
        self.save()
