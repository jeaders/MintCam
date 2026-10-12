import logging
import time
import os
import shutil
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# NOTE: tested with Logitech C920 and C270 on Mint 21. Using V4L2 backend
logger = logging.getLogger("mintcam.camera")

# Finestra usata per misurare la frequenza reale della webcam.
_FPS_WINDOW_SECONDS = 3.0

RESOLUTIONS = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
}


def _get_device_name(index: int) -> str:
    path = f"/sys/class/video4linux/video{index}/name"
    try:
        with open(path, "r", encoding="utf-8") as f:
            name = f.read().strip()
        if name:
            return name
    except Exception:
        pass
    return ""


def list_video_devices() -> list[int]:
    """The /dev/video* nodes that exist, whether or not they can be opened.

    Used to tell "no webcam at all" apart from "the webcam is being used by
    another application": the second case is temporary and the message has to
    say so, otherwise the user thinks the camera is broken.
    """
    import glob
    indices = []
    for path in sorted(glob.glob("/dev/video*")):
        try:
            indices.append(int(path.replace("/dev/video", "")))
        except ValueError:
            continue
    return indices


def enumerate_cameras() -> list[tuple[int, str]]:
    """Webcams that can actually be opened right now."""
    devices: list[tuple[int, str]] = []
    for idx in list_video_devices():
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        ok = cap.isOpened()
        if ok:
            ret, _ = cap.read()
            ok = ret
        cap.release()
        if ok:
            name = _get_device_name(idx)
            label = name if name else f"Webcam {idx}"
            devices.append((idx, label))
    return devices


class CameraWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    camera_changed = pyqtSignal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._device_index: int = 0
        self._width: int = 640
        self._height: int = 480
        self._fps: int = 30
        self._last_frame: Optional[np.ndarray] = None
        self._max_frames: int = 0
        self._frame_count: int = 0
        self._frame_times: list = []

    def set_device(self, index: int, name: str = "") -> None:
        self._device_index = index
        self._reopen()
        self.camera_changed.emit(index, name)

    def set_resolution(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._reopen()

    def set_fps(self, fps: int) -> None:
        self._fps = fps
        if self._cap is not None and self._cap.isOpened():
            self._cap.set(cv2.CAP_PROP_FPS, float(fps))

    def _reopen(self) -> None:
        self._release()
        self._open()

    def _open(self) -> None:
        try:
            self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_V4L2)
            if not self._cap.isOpened():
                raise RuntimeError(f"Impossibile aprire il dispositivo /dev/video{self._device_index}")
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._width))
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._height))
            self._cap.set(cv2.CAP_PROP_FPS, float(self._fps))
            logger.info("Webcam aperta: indice %d, risoluzione %dx%d", self._device_index, self._width, self._height)
        except Exception as exc:
            logger.error("Errore apertura webcam %d: %s", self._device_index, exc)
            self.error.emit(str(exc))
            self._cap = None

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as exc:
                logger.debug("Errore chiusura webcam: %s", exc)
            finally:
                self._cap = None

    def run(self) -> None:
        self._running = True
        self._open()
        frame_count = 0
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self.msleep(100)
                continue
            try:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    logger.warning("Frame non ricevuto dalla webcam")
                    self.msleep(30)
                    continue
                self._last_frame = frame
                self._frame_count += 1
                self._frame_times.append(time.monotonic())
                # finestra di tre secondi: il primo secondo dopo l'apertura
                # della webcam è più lento e falserebbe la misura
                cutoff = time.monotonic() - _FPS_WINDOW_SECONDS
                while self._frame_times and self._frame_times[0] < cutoff:
                    self._frame_times.pop(0)
                self.frame_ready.emit(frame)
            except Exception as exc:
                logger.error("Errore lettura frame: %s", exc)
                self.error.emit(str(exc))
            frame_count += 1
            if 0 < self._max_frames <= frame_count:
                break
            self.msleep(int(1000 / max(self._fps, 1)))

    def stop(self) -> None:
        self._running = False
        self._release()
        self.wait(1500)
        if self.isRunning():
            self.terminate()

    def last_frame(self) -> Optional[np.ndarray]:
        return self._last_frame

    def frame_count(self) -> int:
        """Frames delivered since the camera was opened.

        The recording uses it to write only real frames: the preview timer can
        tick faster than the camera delivers, and writing the same frame again
        makes the video play back faster than it was recorded.
        """
        return self._frame_count

    def measured_fps(self) -> Optional[float]:
        """Actual frame rate over the last second, or None if unknown.

        The requested fps is only a request: a camera that cannot deliver it
        runs slower, and the recording has to use the real number or the video
        plays at the wrong speed.
        """
        if len(self._frame_times) < 2:
            return None
        span = self._frame_times[-1] - self._frame_times[0]
        if span <= 0:
            return None
        return (len(self._frame_times) - 1) / span

