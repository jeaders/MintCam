import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("mintcam.recorder")


class Recorder:
    def __init__(self) -> None:
        self._writer: Optional[cv2.VideoWriter] = None
        self._started: Optional[float] = None
        self._path: Optional[Path] = None

    def start(self, frame: np.ndarray, path: Path, fps: int = 30) -> bool:
        if self._writer is not None:
            return False
        fourccs = [cv2.VideoWriter_fourcc(*"mp4v"), cv2.VideoWriter_fourcc(*"XVID"), cv2.VideoWriter_fourcc(*"MJPG")]
        height, width = frame.shape[:2]
        for fourcc in fourccs:
            try:
                writer = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height))
                if writer.isOpened():
                    self._writer = writer
                    self._started = time.time()
                    self._path = path
                    logger.info("Registrazione avviata: %s", path)
                    return True
            except Exception as exc:
                logger.debug("Fourcc %s non supportato: %s", fourcc, exc)
        logger.error("Nessun codec disponibile per la registrazione video")
        return False

    def write(self, frame: np.ndarray) -> None:
        if self._writer is not None:
            try:
                self._writer.write(frame)
            except Exception as exc:
                logger.error("Errore scrittura frame registrazione: %s", exc)

    def stop(self) -> Optional[Path]:
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception as exc:
                logger.error("Errore chiusura registrazione: %s", exc)
            finally:
                self._writer = None
        path = self._path
        self._path = None
        self._started = None
        if path:
            logger.info("Registrazione salvata: %s", path)
        return path

    def elapsed(self) -> float:
        if self._started is None:
            return 0.0
        return time.time() - self._started

    def is_recording(self) -> bool:
        return self._writer is not None
