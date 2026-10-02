import logging
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.camera import CameraWorker, RESOLUTIONS
from app.recorder import Recorder
from app.settings import Settings
from app.storage import Storage
from app.ui.styles import apply_dark_theme

logger = logging.getLogger("mintcam.ui")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MintCam")
        self.resize(1000, 700)
        self.setMinimumSize(720, 480)

        self.settings = Settings()
        self.recorder = Recorder()
        self.camera: Optional[CameraWorker] = None

        self._current_frame: Optional[np.ndarray] = None
        self._processed_frame: Optional[np.ndarray] = None
        self._timer_seconds: int = 0
        self._timer_active: bool = False
        self._timer_count: int = 0
        self._recording: bool = False
        self._current_filter: str = "Normale"
        self._current_format: str = "16:9"
        self._brightness: int = 0
        self._contrast: int = 0
        self._saturation: int = 0
        self._fps: int = 30
        self._width: int = 640
        self._height: int = 480

        self._init_ui()
        self._init_camera()
        self._start_preview_timer()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        apply_dark_theme(QApplication.instance())
        central = QWidget()
        self.setCentralWidget(central)
        root = QGridLayout(central)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        # Header
        header = QFrame()
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        title = QLabel("MintCam")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #4fc3f7;")
        self.lbl_status = QLabel("Webcam: inizializzazione...")
        self.lbl_status.setStyleSheet("color: #aaaaaa;")
        self.lbl_info = QLabel("Risoluzione: - | FPS: -")
        self.lbl_info.setStyleSheet("color: #aaaaaa;")
        header_lay.addWidget(title)
        header_lay.addStretch()
        header_lay.addWidget(self.lbl_status)
        header_lay.addSpacing(16)
        header_lay.addWidget(self.lbl_info)
        root.addWidget(header, 0, 0, 1, 2)

        # Preview area
        self.preview = QLabel("Anteprima non disponibile")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640, 360)
        self.preview.setStyleSheet(
            "background-color: #111111; color: #777777; font-size: 18px; border-radius: 8px;"
        )
        self.preview.setScaledContents(False)
        root.addWidget(self.preview, 1, 0, 1, 1)

        # Countdown / REC overlay labels (positioned on preview via parent widget stack)
        self.lbl_countdown = QLabel(self.preview)
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet(
            "background-color: rgba(0,0,0,160); color: #ff5252; font-size: 72px; font-weight: bold; border-radius: 12px; padding: 20px;"
        )
        self.lbl_countdown.hide()

        self.lbl_rec = QLabel(self.preview)
        self.lbl_rec.setAlignment(Qt.AlignCenter)
        self.lbl_rec.setStyleSheet(
            "background-color: rgba(200,0,0,180); color: white; font-size: 20px; font-weight: bold; padding: 6px 12px; border-radius: 6px;"
        )
        self.lbl_rec.hide()

        # Controls
        controls = QFrame()
        controls_lay = QVBoxLayout(controls)
        controls_lay.setSpacing(10)

        # Camera selection
        grp_cam = QGroupBox("Fotocamera")
        cam_lay = QVBoxLayout(grp_cam)
        self.combo_camera = QComboBox()
        cam_lay.addWidget(self.combo_camera)
        controls_lay.addWidget(grp_cam)

        # Resolution / FPS
        grp_res = QGroupBox("Risoluzione e FPS")
        res_lay = QVBoxLayout(grp_res)
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(list(RESOLUTIONS.keys()))
        self.combo_fps = QSpinBox()
        self.combo_fps.setRange(1, 120)
        self.combo_fps.setValue(30)
        res_lay.addWidget(QLabel("Risoluzione:"))
        res_lay.addWidget(self.combo_resolution)
        res_lay.addWidget(QLabel("FPS:"))
        res_lay.addWidget(self.combo_fps)
        controls_lay.addWidget(grp_res)

        # Filter
        grp_filter = QGroupBox("Filtro")
        filter_lay = QVBoxLayout(grp_filter)
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["Normale", "Bianco e nero", "Sepia", "Negativo", "Contrasto elevato", "Specchio orizzontale"])
        filter_lay.addWidget(self.combo_filter)
        controls_lay.addWidget(grp_filter)

        # Format
        grp_format = QGroupBox("Formato")
        format_lay = QVBoxLayout(grp_format)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["16:9", "4:3", "9:16"])
        format_lay.addWidget(self.combo_format)
        controls_lay.addWidget(grp_format)

        # Timer
        grp_timer = QGroupBox("Timer foto")
        timer_lay = QVBoxLayout(grp_timer)
        self.combo_timer = QComboBox()
        self.combo_timer.addItems(["Nessun timer", "3 secondi", "5 secondi", "10 secondi"])
        timer_lay.addWidget(self.combo_timer)
        controls_lay.addWidget(grp_timer)

        # Brightness / Contrast / Saturation
        grp_adj = QGroupBox("Regolazioni")
        adj_lay = QVBoxLayout(grp_adj)
        self.slider_brightness = self._make_slider(-100, 100, 0)
        self.slider_contrast = self._make_slider(-100, 100, 0)
        self.slider_saturation = self._make_slider(-100, 100, 0)
        adj_lay.addWidget(QLabel("Luminosità:"))
        adj_lay.addWidget(self.slider_brightness)
        adj_lay.addWidget(QLabel("Contrasto:"))
        adj_lay.addWidget(self.slider_contrast)
        adj_lay.addWidget(QLabel("Saturazione:"))
        adj_lay.addWidget(self.slider_saturation)
        controls_lay.addWidget(grp_adj)

        controls_lay.addStretch()
        root.addWidget(controls, 1, 1, 1, 1)

        # Footer
        footer = QFrame()
        footer_lay = QHBoxLayout(footer)
        footer_lay.setSpacing(12)
        self.btn_photo = QPushButton("Scatta foto")
        self.btn_photo.setObjectName("primary")
        self.btn_photo.setMinimumHeight(48)
        self.btn_photo.clicked.connect(self._on_photo)
        self.btn_record = QPushButton("Avvia registrazione")
        self.btn_record.setObjectName("record")
        self.btn_record.setMinimumHeight(48)
        self.btn_record.clicked.connect(self._on_record_toggle)
        self.btn_folder = QPushButton("Apri cartella foto")
        self.btn_folder.setMinimumHeight(48)
        self.btn_folder.clicked.connect(self._on_open_folder)
        self.btn_exit = QPushButton("Esci")
        self.btn_exit.setMinimumHeight(48)
        self.btn_exit.clicked.connect(self.close)
        footer_lay.addWidget(self.btn_photo)
        footer_lay.addWidget(self.btn_record)
        footer_lay.addWidget(self.btn_folder)
        footer_lay.addWidget(self.btn_exit)
        root.addWidget(footer, 2, 0, 1, 2)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Restore settings
        self.combo_camera.setCurrentIndex(self.settings.get("camera_index", 0))
        self.combo_resolution.setCurrentText(self.settings.get("resolution", "640x480"))
        self.combo_fps.setValue(self.settings.get("fps", 30))
        self.combo_filter.setCurrentText(self.settings.get("filter", "Normale"))
        self.combo_format.setCurrentText(self.settings.get("format", "16:9"))
        self.combo_timer.setCurrentIndex(self.settings.get("timer_seconds", 0))
        self._current_filter = self.combo_filter.currentText()
        self._current_format = self.combo_format.currentText()
        self._fps = self.combo_fps.value()

        # Connections
        self.combo_camera.currentIndexChanged.connect(self._on_camera_changed)
        self.combo_resolution.currentTextChanged.connect(self._on_resolution_changed)
        self.combo_fps.valueChanged.connect(self._on_fps_changed)
        self.combo_filter.currentTextChanged.connect(self._on_filter_changed)
        self.combo_format.currentTextChanged.connect(self._on_format_changed)
        self.combo_timer.currentIndexChanged.connect(self._on_timer_changed)
        self.slider_brightness.valueChanged.connect(self._on_brightness_changed)
        self.slider_contrast.valueChanged.connect(self._on_contrast_changed)
        self.slider_saturation.valueChanged.connect(self._on_saturation_changed)

        # Preview update timer
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(int(1000 / max(self._fps, 1)))
        self._preview_timer.timeout.connect(self._update_preview)

    def _make_slider(self, minv: int, maxv: int, value: int) -> QSlider:
        s = QSlider(Qt.Horizontal)
        s.setRange(minv, maxv)
        s.setValue(value)
        s.setTickPosition(QSlider.TicksBelow)
        s.setTickInterval(25)
        return s

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------
    def _init_camera(self) -> None:
        self.camera = CameraWorker()
        self.camera.frame_ready.connect(self._on_frame_ready)
        self.camera.error.connect(self._on_camera_error)
        self.camera.camera_changed.connect(self._on_camera_changed_signal)
        self._enumerate_cameras()
        self.camera.start()
        self._preview_timer.start()

    def _enumerate_cameras(self) -> None:
        import glob
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()
        found = False
        for path in sorted(glob.glob("/dev/video*")):
            idx = int(path.replace("/dev/video", ""))
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            ok = cap.isOpened()
            if ok:
                ret, _ = cap.read()
                ok = ret
            cap.release()
            if ok:
                self.combo_camera.addItem(f"Webcam {idx}", idx)
                found = True
        if not found:
            self.combo_camera.addItem("Nessuna webcam rilevata", -1)
        self.combo_camera.blockSignals(False)

    def _on_camera_changed(self, index: int) -> None:
        idx = self.combo_camera.currentData()
        if idx is None or idx == -1:
            self._show_status("Webcam non disponibile", error=True)
            return
        self.settings.set("camera_index", idx)
        if self.camera is not None:
            self.camera.set_device(idx, self.combo_camera.currentText())
        self._show_status(f"Webcam selezionata: {self.combo_camera.currentText()}")

    def _on_camera_changed_signal(self, index: int, name: str) -> None:
        self._show_status(f"Webcam cambiata: {name or f'/dev/video{index}'}")

    def _on_camera_error(self, message: str) -> None:
        logger.error("Errore webcam: %s", message)
        self._show_status(f"Errore webcam: {message}", error=True)

    def _on_resolution_changed(self, text: str) -> None:
        self.settings.set("resolution", text)
        wh = RESOLUTIONS.get(text, (640, 480))
        self._width, self._height = wh
        if self.camera is not None:
            self.camera.set_resolution(self._width, self._height)
        self._update_header_info()

    def _on_fps_changed(self, value: int) -> None:
        self.settings.set("fps", value)
        self._fps = value
        if self.camera is not None:
            self.camera.set_fps(value)
        self._preview_timer.setInterval(int(1000 / max(value, 1)))
        self._update_header_info()

    def _on_filter_changed(self, text: str) -> None:
        self._current_filter = text
        self.settings.set("filter", text)

    def _on_format_changed(self, text: str) -> None:
        self._current_format = text
        self.settings.set("format", text)

    def _on_timer_changed(self, index: int) -> None:
        self._timer_seconds = [0, 3, 5, 10][index] if index < 4 else 0
        self.settings.set("timer_seconds", self._timer_seconds)

    def _on_brightness_changed(self, value: int) -> None:
        self._brightness = value
        self.settings.set("brightness", value)

    def _on_contrast_changed(self, value: int) -> None:
        self._contrast = value
        self.settings.set("contrast", value)

    def _on_saturation_changed(self, value: int) -> None:
        self._saturation = value
        self.settings.set("saturation", value)

    def _on_frame_ready(self, frame: np.ndarray) -> None:
        self._current_frame = frame

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def _start_preview_timer(self) -> None:
        self._preview_timer.start()

    def _update_preview(self) -> None:
        frame = self._current_frame
        if frame is None:
            return
        processed = self._apply_adjustments(self._apply_filter(frame.copy()))
        processed = self._apply_format(processed)
        self._processed_frame = processed
        rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        img = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(img)
        scaled = pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(scaled)
        self._position_overlays()

    def _apply_filter(self, frame: np.ndarray) -> np.ndarray:
        f = self._current_filter
        if f == "Bianco e nero":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        if f == "Sepia":
            kernel = np.array([[0.272, 0.534, 0.131], [0.349, 0.686, 0.168], [0.393, 0.769, 0.189]])
            return cv2.transform(frame, kernel).astype(np.uint8)
        if f == "Negativo":
            return cv2.bitwise_not(frame)
        if f == "Contrasto elevato":
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        if f == "Specchio orizzontale":
            return cv2.flip(frame, 1)
        return frame

    def _apply_adjustments(self, frame: np.ndarray) -> np.ndarray:
        brightness = self._brightness / 100.0
        contrast = (self._contrast + 100) / 100.0
        saturation = (self._saturation + 100) / 100.0
        if abs(brightness) > 1e-6:
            frame = cv2.convertScaleAbs(frame, alpha=1.0, beta=int(brightness * 255))
        if abs(contrast - 1.0) > 1e-6:
            frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=0)
        if abs(saturation - 1.0) > 1e-6:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            s = cv2.convertScaleAbs(s, alpha=saturation, beta=0)
            hsv = cv2.merge([h, s, v])
            frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return frame

    def _apply_format(self, frame: np.ndarray) -> np.ndarray:
        fmt = self._current_format
        h, w = frame.shape[:2]
        target_ratio = {"16:9": 16 / 9, "4:3": 4 / 3, "9:16": 9 / 16}.get(fmt, 16 / 9)
        current_ratio = w / h
        if abs(current_ratio - target_ratio) < 0.01:
            return frame
        if target_ratio > current_ratio:
            new_w = w
            new_h = int(w / target_ratio)
            y1 = max(0, (h - new_h) // 2)
            return frame[y1 : y1 + new_h, : new_w]
        else:
            new_h = h
            new_w = int(h * target_ratio)
            x1 = max(0, (w - new_w) // 2)
            return frame[:new_h, x1 : x1 + new_w]

    def _position_overlays(self) -> None:
        self.lbl_countdown.setFixedSize(self.preview.width() // 2, self.preview.height() // 3)
        self.lbl_countdown.move(
            (self.preview.width() - self.lbl_countdown.width()) // 2,
            (self.preview.height() - self.lbl_countdown.height()) // 2,
        )
        self.lbl_rec.move(12, 12)
        self.lbl_rec.adjustSize()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_overlays()

    # ------------------------------------------------------------------
    # Photo / Timer
    # ------------------------------------------------------------------
    def _on_photo(self) -> None:
        if self._timer_active:
            return
        if self._timer_seconds > 0:
            self._start_timer(self._timer_seconds)
            return
        self._take_photo()

    def _start_timer(self, seconds: int) -> None:
        self._timer_active = True
        self._timer_count = seconds
        self.btn_photo.setEnabled(False)
        self._show_countdown()

    def _show_countdown(self) -> None:
        if self._timer_count <= 0:
            self.lbl_countdown.hide()
            self._timer_active = False
            self.btn_photo.setEnabled(True)
            self._take_photo()
            return
        self.lbl_countdown.setText(str(self._timer_count))
        self.lbl_countdown.show()
        self._position_overlays()
        QTimer.singleShot(1000, self._decrement_timer)

    def _decrement_timer(self) -> None:
        self._timer_count -= 1
        self._show_countdown()

    def _take_photo(self) -> None:
        frame = self._processed_frame if self._processed_frame is not None else self._current_frame
        if frame is None:
            self._show_status("Nessun frame disponibile per la foto", error=True)
            return
        path = Storage.save_photo(frame)
        if path is None:
            self._show_status("Errore salvataggio foto", error=True)
            return
        self._show_status(f"Foto salvata: {path}")
        self.status.showMessage(f"Foto salvata: {path}", 5000)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def _on_record_toggle(self) -> None:
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        frame = self._processed_frame if self._processed_frame is not None else self._current_frame
        if frame is None:
            self._show_status("Nessun frame disponibile per la registrazione", error=True)
            return
        path = Storage.recordings_dir() / Storage.video_filename()
        ok = self.recorder.start(frame, path, fps=self._fps)
        if not ok:
            self._show_status("Impossibile avviare la registrazione: codec non disponibile", error=True)
            return
        self._recording = True
        self.btn_record.setText("Ferma registrazione")
        self.btn_record.setObjectName("stop")
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.lbl_rec.show()
        self.lbl_rec.setText("REC")
        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(500)
        self._rec_timer.timeout.connect(self._update_rec_time)
        self._rec_timer.start()
        self._show_status("Registrazione avviata")

    def _stop_recording(self) -> None:
        path = self.recorder.stop()
        self._recording = False
        self.btn_record.setText("Avvia registrazione")
        self.btn_record.setObjectName("record")
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.lbl_rec.hide()
        if hasattr(self, "_rec_timer") and self._rec_timer is not None:
            self._rec_timer.stop()
            self._rec_timer.deleteLater()
            self._rec_timer = None
        if path:
            self._show_status(f"Registrazione salvata: {path}")
            self.status.showMessage(f"Registrazione salvata: {path}", 5000)
        else:
            self._show_status("Registrazione interrotta senza salvataggio", error=True)

    def _update_rec_time(self) -> None:
        elapsed = self.recorder.elapsed()
        m, s = divmod(int(elapsed), 60)
        self.lbl_rec.setText(f"REC {m:02d}:{s:02d}")

    # ------------------------------------------------------------------
    # Folder
    # ------------------------------------------------------------------
    def _on_open_folder(self) -> None:
        Storage.open_folder(Storage.photos_dir())

    # ------------------------------------------------------------------
    # Header / status
    # ------------------------------------------------------------------
    def _update_header_info(self) -> None:
        self.lbl_info.setText(f"Risoluzione: {self._width}x{self._height} | FPS: {self._fps}")

    def _show_status(self, message: str, error: bool = False) -> None:
        color = "#ff5252" if error else "#4fc3f7"
        self.lbl_status.setStyleSheet(f"color: {color};")
        self.lbl_status.setText(message)
        logger.info(message)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._recording:
            self._stop_recording()
        if self.camera is not None:
            self.camera.stop()
            self.camera = None
        if hasattr(self, "_preview_timer") and self._preview_timer is not None:
            self._preview_timer.stop()
        event.accept()
