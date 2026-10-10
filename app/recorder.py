import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("mintcam.recorder")

# TODO: handle case where ffmpeg is missing but audio=True (show error dialog?)


class Recorder:
    def __init__(self) -> None:
        self._writer: Optional[cv2.VideoWriter] = None
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._using_audio: bool = False
        self._started: Optional[float] = None
        self._path: Optional[Path] = None
        self._width: int = 640
        self._height: int = 480
        self._fps: int = 30

    def start(self, frame: np.ndarray, path: Path, fps: int = 30, audio: bool = False) -> bool:
        if self._writer is not None or self._ffmpeg_proc is not None:
            return False
        height, width = frame.shape[:2]
        self._height = height
        self._width = width
        self._fps = int(fps)
        used_path = path.with_suffix(".mp4")
        if audio:
            return self._start_with_audio(used_path, width, height, fps)
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

    def _start_with_audio(self, path: Path, width: int, height: int, fps: int) -> bool:
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-f", "alsa",
            "-i", "default",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-f", "mp4",
            str(path),
        ]
        try:
            self._ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.error("ffmpeg non trovato: impossibile registrare con audio")
            return False
        except Exception as exc:
            logger.error("Errore avvio ffmpeg con audio: %s", exc)
            return False
        self._using_audio = True
        self._started = time.time()
        self._path = path
        logger.info("Registrazione avviata con audio: %s", path)
        return True

    def write(self, frame: np.ndarray) -> None:
        if self._ffmpeg_proc is not None:
            self._write_to_ffmpeg(frame)
            return
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

    def _write_to_ffmpeg(self, frame: np.ndarray) -> None:
        if self._ffmpeg_proc is None or self._ffmpeg_proc.stdin is None:
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
            self._ffmpeg_proc.stdin.write(frame.tobytes())
            self._ffmpeg_proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            logger.error("Pipe ffmpeg chiusa inaspettatamente: %s", exc)
            self._ffmpeg_proc = None

    def stop(self) -> Optional[Path]:
        path = self._path
        self._path = None
        self._started = None
        self._using_audio = False
        if self._ffmpeg_proc is not None:
            proc = self._ffmpeg_proc
            self._ffmpeg_proc = None
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            logger.info("Registrazione con audio salvata: %s", path)
            return path
        writer = self._writer
        self._writer = None
        if path:
            logger.info("Registrazione salvata: %s", path)
        if writer is not None:
            try:
                writer.release()
                logger.debug("Writer rilasciato correttamente")
            except Exception as exc:
                logger.error("Errore chiusura registrazione: %s", exc)
        return path

    def elapsed(self) -> float:
        if self._started is None:
            return 0.0
        return time.time() - self._started

    def is_recording(self) -> bool:
        return self._writer is not None or self._ffmpeg_proc is not None

    def __del__(self) -> None:
        if self._ffmpeg_proc is not None:
            try:
                if self._ffmpeg_proc.stdin is not None:
                    self._ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                self._ffmpeg_proc.terminate()
                self._ffmpeg_proc.wait(timeout=5)
            except Exception:
                try:
                    self._ffmpeg_proc.kill()
                except Exception:
                    pass
            self._ffmpeg_proc = None
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None
