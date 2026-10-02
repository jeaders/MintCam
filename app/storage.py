import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("mintcam.storage")


class Storage:
    BASE_DIR = Path.home() / "MintCam"

    @classmethod
    def _ensure_dir(cls, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error("Impossibile creare la cartella %s: %s", path, exc)
            raise

    @classmethod
    def photos_dir(cls) -> Path:
        d = cls.BASE_DIR / "photos"
        cls._ensure_dir(d)
        return d

    @classmethod
    def recordings_dir(cls) -> Path:
        d = cls.BASE_DIR / "recordings"
        cls._ensure_dir(d)
        return d

    @classmethod
    def logs_dir(cls) -> Path:
        d = cls.BASE_DIR / "logs"
        cls._ensure_dir(d)
        return d

    @staticmethod
    def photo_filename() -> str:
        return f"foto_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"

    @staticmethod
    def video_filename() -> str:
        return f"video_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"

    @classmethod
    def save_photo(cls, frame, path: Path | None = None, quality: int = 95) -> Path | None:
        if path is None:
            path = cls.photos_dir() / cls.photo_filename()
        try:
            import cv2
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
            logger.info("Foto salvata in %s", path)
            return path
        except Exception as exc:
            logger.error("Errore salvataggio foto %s: %s", path, exc)
            return None

    @classmethod
    def open_folder(cls, folder: Path) -> None:
        import subprocess
        try:
            subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as exc:
            logger.error("Impossibile aprire la cartella %s: %s", folder, exc)
