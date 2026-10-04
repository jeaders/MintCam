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
        self._temp_dir: Optional[str] = None
        self._frame_index: int = 0
        self._fps: int = 30
        self._width: int = 640
        self._height: int = 480
        self._ext: str = ".mp4"
        self._assembly_thread: Optional[threading.Thread] = None

    def start(self, frame: np.ndarray, path: Path, fps: int = 30) -> bool:
        if self._writer is not None:
            return False
        height, width = frame.shape[:2]
        self._height = height
        self._width = width
        self._fps = int(fps)
        self._frame_index = 0
        self._ext = path.suffix.lower() or ".mp4"

        try:
            self._temp_dir = tempfile.mkdtemp(prefix="mintcam_rec_")
        except Exception as exc:
            logger.error("Impossibile creare directory temporanea: %s", exc)
            return False

        writer = None
        used_path = None
        for fourcc_code, ext in [("mp4v", ".mp4"), ("XVID", ".avi"), ("MJPG", ".avi")]:
            try:
                test_path = path.with_suffix(ext)
                writer = cv2.VideoWriter(
                    str(test_path),
                    cv2.VideoWriter_fourcc(*fourcc_code),
                    float(fps),
                    (width, height),
                )
                if writer.isOpened():
                    used_path = test_path
                    self._ext = ext
                    break
            except Exception as exc:
                logger.debug("Fourcc %s non supportato: %s", fourcc_code, exc)
            finally:
                if writer is not None and used_path is None:
                    try:
                        writer.release()
                    except Exception:
                        pass

        if used_path is None:
            self._cleanup_temp()
            self._temp_dir = None
            logger.error("Nessun codec disponibile per la registrazione video")
            return False

        self._writer = writer
        self._started = time.time()
        self._path = used_path
        logger.info("Registrazione avviata: %s (codec=%s, %dx%d)", used_path, "frame-sequence", width, height)
        return True

    def write(self, frame: np.ndarray) -> None:
        if self._temp_dir is None:
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
            image_path = os.path.join(self._temp_dir, f"frame_{self._frame_index:08d}.jpg")
            cv2.imwrite(image_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            self._frame_index += 1
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

        temp_dir = self._temp_dir
        frame_index = self._frame_index
        fps = self._fps
        width = self._width
        height = self._height
        self._temp_dir = None
        self._frame_index = 0

        if temp_dir is not None and frame_index > 0 and path is not None:
            self._assembly_thread = threading.Thread(
                target=self._assemble,
                args=(path, temp_dir, frame_index, fps, width, height),
                daemon=True,
            )
            self._assembly_thread.start()
        else:
            self._cleanup_temp(temp_dir)

        return path

    def elapsed(self) -> float:
        if self._started is None:
            return 0.0
        return time.time() - self._started

    def is_recording(self) -> bool:
        return self._writer is not None or self._temp_dir is not None

    def _assemble(self, path: Path, temp_dir: str, frame_index: int, fps: int, width: int, height: int) -> None:
        try:
            files = sorted(Path(temp_dir).glob("frame_*.jpg"))
            if not files:
                return
            list_path = Path(temp_dir) / "files.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for item in files:
                    f.write(f"file '{item.as_posix()}'\n")
            ffmpeg_exe = shutil.which("ffmpeg")
            if ffmpeg_exe is None:
                logger.error("ffmpeg non trovato, impossibile assemblare il video")
                return
            cmd = [
                ffmpeg_exe,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-framerate",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Video assemblato: %s (%d frames)", path, frame_index)
        except Exception as exc:
            logger.error("Errore assemblaggio video: %s", exc)
        finally:
            self._cleanup_temp(temp_dir)

    def _cleanup_temp(self, temp_dir: Optional[str] = None) -> None:
        target = temp_dir or self._temp_dir
        if target and os.path.isdir(target):
            try:
                shutil.rmtree(target, ignore_errors=True)
            except Exception:
                pass
