import logging
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("mintcam.recorder")

# ebur128 prints M (momentary loudness) and TPK (true peak, one value per
# channel, so the first one is taken).
_LEVEL_PATTERN = re.compile(
    r"\bM:(?P<m>\s*-?\d+\.\d+|\s*-?nan|\s*-?inf)"
    r".*?\bTPK:(?P<tpk>\s*-?\d+\.\d+|\s*-?nan|\s*-?inf)")


def _to_float(value) -> Optional[float]:
    """ffmpeg prints -nan, inf or -inf when the signal is undefined."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number

# TODO: handle case where ffmpeg is missing but audio=True (show error dialog?)


class Recorder:
    def __init__(self) -> None:
        self._writer: Optional[cv2.VideoWriter] = None
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._using_audio: bool = False
        self._meter_thread: Optional[threading.Thread] = None
        self._last_levels: dict = {"momentary": None, "peak": None}
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
            "-af", "ebur128=peak=true",
            "-pix_fmt", "yuv420p",
            "-f", "mp4",
            str(path),
        ]
        # Linux Mint XFCE typically uses PulseAudio/ALSA shim. Try PulseAudio
        # first (captures from the default input source), fall back to ALSA.
        if shutil.which("pactl") is not None:
            ffmpeg_cmd[11:13] = ["-f", "pulse", "-i", "@DEFAULT_SOURCE@"]
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
        # stderr must be drained: ffmpeg writes the ebur128 report there, and
        # an unread pipe fills up after about 64 KB and blocks the recording.
        self._meter_thread = threading.Thread(target=self._read_meter, daemon=True)
        self._meter_thread.start()
        logger.info("Registrazione avviata con audio: %s", path)
        return True

    def _read_meter(self) -> None:
        """Parse the ebur128 report ffmpeg prints on stderr.

        Each line looks like:
        [Parsed_ebur128_0 @ 0x...] t: 1.20  TARGET:-23 LUFS  M:-31.4 S:-31.2
        I:-31.2 LUFS  LRA: 0.0 LU  FTPK:-25.9 -25.9 dBFS  TPK:-25.9 -25.9 dBFS
        The useful numbers are M (momentary loudness) and TPK (true peak).
        """
        if self._ffmpeg_proc is None or self._ffmpeg_proc.stderr is None:
            return
        for raw in self._ffmpeg_proc.stderr:
            try:
                line = raw.decode("utf-8", "replace")
            except Exception:
                continue
            values = _LEVEL_PATTERN.search(line)
            if values:
                self._last_levels = {
                    "momentary": _to_float(values.group("m")),
                    "peak": _to_float(values.group("tpk")),
                }

    def audio_level(self) -> dict:
        """Last level reported by ffmpeg, in dBFS. Silence is about -60."""
        return dict(self._last_levels)

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
            if self._meter_thread is not None and self._meter_thread.is_alive():
                self._meter_thread.join(timeout=2)
            self._meter_thread = None
            self._last_levels = {"momentary": None, "peak": None}
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
