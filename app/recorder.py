import logging
import os
import shutil
import subprocess
import tempfile
import threading
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
        self._release_thread: Optional[threading.Thread] = None
        self._width: int = 640
        self._height: int = 480
        self._fps: int = 30

    def start(self, frame: np.ndarray, path: Path, fps: int = 30) -> bool:
        if self._writer is not None:
            return False
        height, width = frame.shape[:2]
        self._height = height
        self._width = width
        self._fps = int(fps)
        used_path = path.with_suffix(".mp4")
        for fourcc_code in ("mp4v", "XVID", "MJPG"):
            try:
                writer = cv2.VideoWriter(
                    str(used_path),
                    cv2.VideoWriter_fourcc(*fourcc_code),
                    float(fps),
                    (width, height),
                )
                if writer.isOpened():
                    self._writer = writer
                    self._started = time.time()
                    self._path = used_path
                    logger.info("Registrazione avviata: %s (codec=%s)", used_path, fourcc_code)
                    return True
            except Exception as exc:
                logger.debug("Fourcc %s non supportato: %s", fourcc_code, exc)
        logger.error("Nessun codec disponibile per la registrazione video")
        return False

    def write(self, frame: np.ndarray) -> None:
        if self._writer is None:
            return
        try:
            frame = np.ascontiguousarray(frame)
            if frame.ndim != 3 or frame.shape[2] != 3:
                if frame.ndim == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            h, w = frame.shape[:2]
            if (w, h) != (self._width, self._height):
                frame = cv2.resize(frame, (self._width, self._height))
            frame = np.clip(frame, 0, 255).astype(np.uint8, copy=False)
            frame = np.ascontiguousarray(frame)
            self._writer.write(frame)
        except Exception as exc:
            logger.error("Errore scrittura frame registrazione: %s", exc)

    def stop(self) -> Optional[Path]:
        writer = self._writer
        path = self._path
        self._writer = None
        self._path = None
        self._started = None
        if path:
            logger.info("Registrazione salvata: %s", path)
        if writer is not None:
            self._release_writer_async(writer, path)
        return path

    def elapsed(self) -> float:
        if self._started is None:
            return 0.0
        return time.time() - self._started

    def is_recording(self) -> bool:
        return self._writer is not None

    def _release_writer_async(self, writer: cv2.VideoWriter, path: Optional[Path]) -> None:
        def _release() -> None:
            try:
                writer.release()
            except Exception as exc:
                logger.error("Errore chiusura registrazione: %s", exc)
            finally:
                if path:
                    try:
                        size = path.stat().st_size
                    except Exception:
                        size = -1
                    logger.debug("File registrazione: %s (%s bytes)", path, size)

        self._release_thread = threading.Thread(target=_release, daemon=True)
        self._release_thread.start()
