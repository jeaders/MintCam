import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

try:
    from pyzbar.pyzbar import decode as qr_decode
    _QR_AVAILABLE = True
except Exception:
    _QR_AVAILABLE = False

from app.camera import RESOLUTIONS, CameraWorker
from app.recorder import Recorder
from app.settings import Settings
from app.storage import Storage
from app.ui.styles import apply_dark_theme

logger = logging.getLogger("mintcam.ui")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MintCam")
        self.resize(1200, 780)
        self.setMinimumSize(860, 620)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setStyleSheet("QMainWindow { border: none; }")

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
        self._fullscreen: bool = False
        self._mirror: bool = False
        self._zoom: int = 100
        self._grid: bool = False
        self._burst_count: int = 1
        self._pause_preview: bool = False
        self._clip_seconds: int = 0
        self._photo_quality: int = 95
        self._burst_index: int = 0
        self._burst_timer: Optional[QTimer] = None
        self._recording_frame_size: Optional[tuple[int, int]] = None
        self._qr_enabled: bool = False
        self._qr_result: Optional[str] = None
        self._focus_assist_enabled: bool = False
        self._face_framing_enabled: bool = False
        self._timelapse_enabled: bool = False
        self._timelapse_interval: int = 1
        self._timelapse_timer: Optional[QTimer] = None
        self._timelapse_frames: list[np.ndarray] = []
        self._mintcast_enabled: bool = False
        self._mintcast_device: str = "/dev/video10"

        self._recent_media: list[Path] = []
        self._max_recent = 8

        self._init_ui()
        self._init_camera()
        self._load_recent_media()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        apply_dark_theme(QApplication.instance())
        central = QWidget()
        self.setCentralWidget(central)
        root = QGridLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bg = QFrame()
        bg.setStyleSheet("background-color: #0f1115;")
        bg_lay = QGridLayout(bg)
        bg_lay.setContentsMargins(16, 12, 16, 12)
        bg_lay.setSpacing(12)
        root.addWidget(bg, 0, 0, 1, 1)

        header = self._build_header()
        bg_lay.addWidget(header, 0, 0, 1, 2)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        sidebar = QWidget()
        sidebar.setMinimumWidth(260)
        sidebar.setMaximumWidth(320)
        sidebar_lay = QVBoxLayout(sidebar)
        sidebar_lay.setSpacing(10)
        sidebar_lay.setContentsMargins(0, 0, 0, 0)
        sidebar_scroll.setWidget(sidebar)

        sidebar_lay.addWidget(self._build_card_camera())
        sidebar_lay.addWidget(self._build_card_resolution())
        sidebar_lay.addWidget(self._build_card_filter())
        sidebar_lay.addWidget(self._build_card_format())
        sidebar_lay.addWidget(self._build_card_timer())
        sidebar_lay.addWidget(self._build_card_adjustments())
        sidebar_lay.addWidget(self._build_card_tools())
        sidebar_lay.addWidget(self._build_card_general())
        sidebar_lay.addStretch()

        bg_lay.addWidget(sidebar_scroll, 1, 1, 1, 1)

        preview_container = QWidget()
        preview_container.setStyleSheet("background-color: #0f1115;")
        preview_lay = QVBoxLayout(preview_container)
        preview_lay.setContentsMargins(0, 0, 0, 0)
        preview_lay.setSpacing(0)

        self.preview_container = QWidget()
        self.preview_container.setStyleSheet("background-color: #0f1115;")
        preview_container_lay = QGridLayout(self.preview_container)
        preview_container_lay.setContentsMargins(0, 0, 0, 0)
        preview_container_lay.setSpacing(0)

        self.preview = QLabel("Anteprima non disponibile")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640, 360)
        self.preview.setStyleSheet(
            "background-color: #0a0c10; color: #6b7280; font-size: 16px; border-radius: 12px;"
        )
        self.preview.setScaledContents(False)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_container_lay.addWidget(self.preview, 0, 0, 1, 1)

        self._build_overlays(preview_container_lay)

        preview_lay.addWidget(self.preview_container, 1)

        self.recent_strip = self._build_recent_strip()
        preview_lay.addWidget(self.recent_strip, 2)

        bg_lay.addWidget(preview_container, 1, 0, 1, 1)

        footer = self._build_footer()
        bg_lay.addWidget(footer, 2, 0, 1, 2)

        self.status = QStatusBar()
        self.status.setStyleSheet("QStatusBar { background-color: #0f1115; color: #9aa0ac; padding: 4px 12px; }")
        self.setStatusBar(self.status)

        self._restore_settings()
        self._install_shortcuts()
        self._connect_signals()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background-color: #0f1115;")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        logo_label = QLabel()
        logo_label.setFixedSize(40, 40)
        logo_pix = self._load_logo()
        if not logo_pix.isNull():
            logo_pix = logo_pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pix)
        else:
            logo_label.setText("📷")
        logo_label.setStyleSheet("font-size: 22px; padding: 4px; border-radius: 8px;")
        logo_label.setAlignment(Qt.AlignCenter)

        title = QLabel("MintCam")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #5cd962; letter-spacing: -0.3px;")
        title.setAlignment(Qt.AlignCenter)

        self.lbl_status = QLabel("Inizializzazione webcam…")
        self.lbl_status.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #6b7280; font-size: 12px;")

        center_widget = QWidget()
        center_lay = QHBoxLayout(center_widget)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(12)
        center_lay.addStretch()
        center_lay.addWidget(logo_label)
        center_lay.addWidget(title)
        center_lay.addStretch()

        lay.addWidget(center_widget, 1)
        lay.addStretch()
        lay.addWidget(self.lbl_status)
        lay.addSpacing(16)
        lay.addWidget(self.lbl_info)
        return header

    def _load_logo(self) -> QPixmap:
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "assets" / "mintcam-logo.jpg",
            Path("/usr/share/pixmaps/mintcam-logo.jpg"),
            Path("/usr/share/mintcam/assets/mintcam-logo.jpg"),
        ]
        for path in candidates:
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    return pix
        return QPixmap()

    def _build_card_camera(self) -> QGroupBox:
        grp = QGroupBox("Fotocamera")
        grp.setObjectName("sidebar-card")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_camera = QComboBox()
        self.combo_camera.setMinimumHeight(32)
        lay.addWidget(self.combo_camera)
        return grp

    def _build_card_resolution(self) -> QGroupBox:
        grp = QGroupBox("Risoluzione e FPS")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(list(RESOLUTIONS.keys()))
        self.combo_fps = QSpinBox()
        self.combo_fps.setRange(1, 120)
        self.combo_fps.setValue(30)
        lay.addWidget(QLabel("Risoluzione:"))
        lay.addWidget(self.combo_resolution)
        lay.addWidget(QLabel("FPS:"))
        lay.addWidget(self.combo_fps)
        return grp

    def _build_card_filter(self) -> QGroupBox:
        grp = QGroupBox("Filtro")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["Normale", "Bianco e nero", "Sepia", "Negativo", "Contrasto elevato"])
        lay.addWidget(self.combo_filter)
        return grp

    def _build_card_format(self) -> QGroupBox:
        grp = QGroupBox("Formato")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["16:9", "4:3", "9:16"])
        lay.addWidget(self.combo_format)
        return grp

    def _build_card_timer(self) -> QGroupBox:
        grp = QGroupBox("Timer foto")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_timer = QComboBox()
        self.combo_timer.addItems(["Nessun timer", "3 secondi", "5 secondi", "10 secondi"])
        lay.addWidget(self.combo_timer)
        return grp

    def _build_card_adjustments(self) -> QGroupBox:
        grp = QGroupBox("Regolazioni")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)
        self.slider_brightness = self._make_slider(-100, 100, 0, "Luminosità")
        self.slider_contrast = self._make_slider(-100, 100, 0, "Contrasto")
        self.slider_saturation = self._make_slider(-100, 100, 0, "Saturazione")
        lay.addWidget(self.slider_brightness["label"])
        lay.addWidget(self.slider_brightness["slider"])
        lay.addWidget(self.slider_contrast["label"])
        lay.addWidget(self.slider_contrast["slider"])
        lay.addWidget(self.slider_saturation["label"])
        lay.addWidget(self.slider_saturation["slider"])
        return grp

    def _build_card_tools(self) -> QGroupBox:
        grp = QGroupBox("Strumenti")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.chk_mirror = QCheckBox("Specchio")
        self.chk_mirror.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_mirror.toggled.connect(self._on_mirror_changed)
        lay.addWidget(self.chk_mirror)
        self.chk_grid = QCheckBox("Griglia")
        self.chk_grid.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_grid.toggled.connect(self._on_grid_changed)
        lay.addWidget(self.chk_grid)
        self.chk_pause = QCheckBox("Pausa anteprima")
        self.chk_pause.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_pause.toggled.connect(self._on_pause_changed)
        lay.addWidget(self.chk_pause)
        self.chk_qr = QCheckBox("QR/Barcode scanner")
        self.chk_qr.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_qr.setEnabled(_QR_AVAILABLE)
        self.chk_qr.toggled.connect(self._on_qr_changed)
        lay.addWidget(self.chk_qr)
        self.chk_focus = QCheckBox("Focus assist")
        self.chk_focus.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_focus.toggled.connect(self._on_focus_changed)
        lay.addWidget(self.chk_focus)
        self.chk_face = QCheckBox("Face auto-framing")
        self.chk_face.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_face.toggled.connect(self._on_face_changed)
        lay.addWidget(self.chk_face)
        self.chk_timelapse = QCheckBox("Time-lapse")
        self.chk_timelapse.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_timelapse.toggled.connect(self._on_timelapse_changed)
        lay.addWidget(self.chk_timelapse)
        self.spin_timelapse_interval = QSpinBox()
        self.spin_timelapse_interval.setRange(1, 60)
        self.spin_timelapse_interval.setSuffix(" s")
        self.spin_timelapse_interval.setValue(1)
        self.spin_timelapse_interval.valueChanged.connect(self._on_timelapse_interval_changed)
        lay.addWidget(QLabel("Intervallo time-lapse:"))
        lay.addWidget(self.spin_timelapse_interval)
        self.chk_mintcast = QCheckBox("MintCast virtual cam")
        self.chk_mintcast.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_mintcast.toggled.connect(self._on_mintcast_changed)
        lay.addWidget(self.chk_mintcast)
        self.combo_burst = QComboBox()
        self.combo_burst.addItems(["Singolo", "Burst 3", "Burst 5", "Burst 10"])
        self.combo_burst.currentIndexChanged.connect(self._on_burst_changed)
        lay.addWidget(QLabel("Modalità scatto:"))
        lay.addWidget(self.combo_burst)
        self.spin_clip = QSpinBox()
        self.spin_clip.setRange(0, 3600)
        self.spin_clip.setSpecialValueText("Illimitato")
        self.spin_clip.setValue(0)
        self.spin_clip.valueChanged.connect(self._on_clip_changed)
        lay.addWidget(QLabel("Durata max registrazione (s):"))
        lay.addWidget(self.spin_clip)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(50, 100)
        self.spin_quality.setValue(95)
        self.spin_quality.valueChanged.connect(self._on_quality_changed)
        lay.addWidget(QLabel("Qualità foto:"))
        lay.addWidget(self.spin_quality)
        self.combo_folder = QComboBox()
        self.combo_folder.addItems(["Foto", "Registrazioni"])
        self.combo_folder.currentIndexChanged.connect(self._on_folder_changed)
        lay.addWidget(QLabel("Cartella apertura:"))
        lay.addWidget(self.combo_folder)
        btn_reset_adj = QPushButton("Reset regolazioni")
        btn_reset_adj.setObjectName("ghost")
        btn_reset_adj.clicked.connect(self._reset_adjustments)
        lay.addWidget(btn_reset_adj)
        return grp

    def _build_card_general(self) -> QGroupBox:
        grp = QGroupBox("Generale")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.chk_autostart = QCheckBox("Avvio automatico con il sistema")
        self.chk_autostart.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_autostart.toggled.connect(self._on_autostart_changed)
        lay.addWidget(self.chk_autostart)
        return grp

    def _make_slider(self, minv: int, maxv: int, value: int, name: str) -> dict:
        label = QLabel(f"{name}: {value}")
        label.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        s = QSlider(Qt.Horizontal)
        s.setRange(minv, maxv)
        s.setValue(value)
        s.setTickPosition(QSlider.TicksBelow)
        s.setTickInterval(25)
        s.valueChanged.connect(lambda v: label.setText(f"{name}: {v}"))
        return {"label": label, "slider": s}

    def _build_recent_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedHeight(90)
        strip.setStyleSheet("background-color: #0f1115; border-top: 1px solid #1e222b;")
        lay = QHBoxLayout(strip)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(8)
        lbl = QLabel("Recenti")
        lbl.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 700;")
        lay.addWidget(lbl)
        self._recent_labels: list[QLabel] = []
        for _ in range(self._max_recent):
            thumb = QLabel()
            thumb.setFixedSize(72, 54)
            thumb.setStyleSheet("background-color: #1e222b; border-radius: 8px; border: 1px solid #252a35;")
            thumb.setAlignment(Qt.AlignCenter)
            thumb.setToolTip("")
            lay.addWidget(thumb)
            self._recent_labels.append(thumb)
        lay.addStretch()
        return strip

    def _build_overlays(self, parent_layout) -> None:
        # Flash
        self.flash = QWidget(self.preview_container)
        self.flash.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.flash.setStyleSheet("background-color: rgba(255,255,255,200); border-radius: 12px;")
        self.flash.hide()
        parent_layout.addWidget(self.flash, 0, 0, 1, 1)

        # Grid
        self.grid_overlay = QWidget(self.preview_container)
        self.grid_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.grid_overlay.setStyleSheet("background-color: transparent;")
        self.grid_overlay.hide()
        parent_layout.addWidget(self.grid_overlay, 0, 0, 1, 1)

        # Countdown
        self.lbl_countdown = QLabel(self.preview_container)
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet(
            "background-color: rgba(15,17,21,200); color: #5cd962; font-size: 80px; font-weight: 900;"
            "border: 3px solid #5cd962; border-radius: 20px; padding: 20px;"
        )
        self.lbl_countdown.hide()
        parent_layout.addWidget(self.lbl_countdown, 0, 0, 1, 1)

        # REC indicator - small red light at bottom
        self.lbl_rec = QLabel(self.preview_container)
        self.lbl_rec.setAlignment(Qt.AlignCenter)
        self.lbl_rec.setStyleSheet(
            "background-color: #ef4444; color: white; font-size: 11px; font-weight: 700;"
            "padding: 4px 10px; border-radius: 10px;"
        )
        self.lbl_rec.hide()
        self.lbl_rec.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lbl_rec.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        parent_layout.addWidget(self.lbl_rec, 0, 0, 1, 1)

        # QR result
        self.lbl_qr = QLabel(self.preview_container)
        self.lbl_qr.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.lbl_qr.setWordWrap(True)
        self.lbl_qr.setStyleSheet(
            "background-color: rgba(15,17,21,200); color: #5cd962; font-size: 16px; font-weight: 700;"
            "border: 2px solid #5cd962; border-radius: 10px; padding: 10px;"
        )
        self.lbl_qr.hide()
        self.lbl_qr.setAttribute(Qt.WA_TransparentForMouseEvents)
        parent_layout.addWidget(self.lbl_qr, 0, 0, 1, 1)

        # Focus assist indicator
        self.lbl_focus = QLabel(self.preview_container)
        self.lbl_focus.setAlignment(Qt.AlignBottom | Qt.AlignRight)
        self.lbl_focus.setFixedSize(24, 24)
        self.lbl_focus.setStyleSheet("border-radius: 12px; border: 3px solid #6b7280; background-color: transparent;")
        self.lbl_focus.hide()
        self.lbl_focus.setAttribute(Qt.WA_TransparentForMouseEvents)
        parent_layout.addWidget(self.lbl_focus, 0, 0, 1, 1)

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet("background-color: #0f1115; border-top: 1px solid #1e222b;")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.btn_photo = QPushButton("📷 Scatta Foto")
        self.btn_photo.setObjectName("primary")
        self.btn_photo.setMinimumHeight(44)
        self.btn_photo.clicked.connect(self._on_photo)

        self.btn_record = QPushButton("Avvia registrazione")
        self.btn_record.setObjectName("record")
        self.btn_record.setMinimumHeight(44)
        self.btn_record.clicked.connect(self._on_record_toggle)

        self.btn_folder = QPushButton("Apri cartella")
        self.btn_folder.setObjectName("ghost")
        self.btn_folder.setMinimumHeight(44)
        self.btn_folder.clicked.connect(self._on_open_folder)

        self.btn_fullscreen = QPushButton("Schermo intero")
        self.btn_fullscreen.setObjectName("ghost")
        self.btn_fullscreen.setMinimumHeight(44)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)

        self.btn_exit = QPushButton("Esci")
        self.btn_exit.setObjectName("ghost")
        self.btn_exit.setMinimumHeight(44)
        self.btn_exit.clicked.connect(self.close)

        lay.addWidget(self.btn_photo)
        lay.addWidget(self.btn_record)
        lay.addWidget(self.btn_folder)
        lay.addWidget(self.btn_fullscreen)
        lay.addWidget(self.btn_exit)
        return footer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _install_shortcuts(self) -> None:
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Space"), self, self._on_photo)
        QShortcut(QKeySequence("R"), self, self._on_record_toggle)
        QShortcut(QKeySequence("F"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, self._exit_fullscreen_or_close)

    def _exit_fullscreen_or_close(self) -> None:
        if self._fullscreen:
            self._toggle_fullscreen()
        else:
            self.close()

    def _restore_settings(self) -> None:
        self.combo_camera.setCurrentIndex(self.settings.get("camera_index", 0))
        self.combo_resolution.setCurrentText(self.settings.get("resolution", "640x480"))
        self.combo_fps.setValue(self.settings.get("fps", 30))
        self.combo_filter.setCurrentText(self.settings.get("filter", "Normale"))
        self.combo_format.setCurrentText(self.settings.get("format", "16:9"))
        self.combo_timer.setCurrentIndex(self.settings.get("timer_seconds", 0))
        self._current_filter = self.combo_filter.currentText()
        self._current_format = self.combo_format.currentText()
        self._fps = self.combo_fps.value()
        self._brightness = self.settings.get("brightness", 0)
        self._contrast = self.settings.get("contrast", 0)
        self._saturation = self.settings.get("saturation", 0)
        self.slider_brightness["slider"].setValue(self._brightness)
        self.slider_contrast["slider"].setValue(self._contrast)
        self.slider_saturation["slider"].setValue(self._saturation)
        self._mirror = self.settings.get("mirror", False)
        self._grid = self.settings.get("grid", False)
        self._burst_count = self.settings.get("burst_count", 1)
        self._pause_preview = self.settings.get("pause_preview", False)
        self._clip_seconds = self.settings.get("clip_seconds", 0)
        self._photo_quality = self.settings.get("photo_quality", 95)
        self._qr_enabled = self.settings.get("qr_enabled", False)
        if not _QR_AVAILABLE:
            self._qr_enabled = False
            self.settings.set("qr_enabled", False)
        self._focus_assist_enabled = self.settings.get("focus_assist", False)
        self._face_framing_enabled = self.settings.get("face_framing", False)
        self._timelapse_enabled = self.settings.get("timelapse", False)
        self._timelapse_interval = self.settings.get("timelapse_interval", 1)
        self._mintcast_enabled = self.settings.get("mintcast", False)
        self.chk_mirror.setChecked(self._mirror)
        self.chk_grid.setChecked(self._grid)
        self.chk_pause.setChecked(self._pause_preview)
        self.chk_qr.setChecked(self._qr_enabled)
        self.chk_focus.setChecked(self._focus_assist_enabled)
        self.chk_face.setChecked(self._face_framing_enabled)
        self.chk_timelapse.setChecked(self._timelapse_enabled)
        self.chk_mintcast.blockSignals(True)
        self.chk_mintcast.setChecked(self._mintcast_enabled)
        self.chk_mintcast.blockSignals(False)
        self.spin_clip.setValue(self._clip_seconds)
        self.spin_quality.setValue(self._photo_quality)
        self.spin_timelapse_interval.setValue(self._timelapse_interval)
        burst_map = {1: 0, 3: 1, 5: 2, 10: 3}
        self.combo_burst.setCurrentIndex(burst_map.get(self._burst_count, 0))
        self._load_autostart_state()

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
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(int(1000 / max(self._fps, 1)))
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start()

    def _enumerate_cameras(self) -> None:
        from app.camera import enumerate_cameras as _enumerate
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()
        devices = _enumerate()
        for idx, label in devices:
            self.combo_camera.addItem(label, idx)
        if not devices:
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
        self._show_status(f"Webcam: {self.combo_camera.currentText()}")

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

    def _on_mirror_changed(self, checked: bool) -> None:
        self._mirror = checked
        self.settings.set("mirror", checked)

    def _on_grid_changed(self, checked: bool) -> None:
        self._grid = checked
        self.settings.set("grid", checked)
        self._position_overlays()

    def _on_pause_changed(self, checked: bool) -> None:
        self._pause_preview = checked
        self.settings.set("pause_preview", checked)

    def _on_burst_changed(self, index: int) -> None:
        self._burst_count = [1, 3, 5, 10][index] if index < 4 else 1
        self.settings.set("burst_count", self._burst_count)

    def _on_clip_changed(self, value: int) -> None:
        self._clip_seconds = value
        self.settings.set("clip_seconds", value)

    def _on_quality_changed(self, value: int) -> None:
        self._photo_quality = value
        self.settings.set("photo_quality", value)

    def _on_folder_changed(self, index: int) -> None:
        folder = Storage.photos_dir() if index == 0 else Storage.recordings_dir()
        Storage.open_folder(folder)

    def _reset_adjustments(self) -> None:
        self._brightness = 0
        self._contrast = 0
        self._saturation = 0
        self.slider_brightness["slider"].setValue(0)
        self.slider_contrast["slider"].setValue(0)
        self.slider_saturation["slider"].setValue(0)
        self.settings.set("brightness", 0)
        self.settings.set("contrast", 0)
        self.settings.set("saturation", 0)
        self._show_status("Regolazioni reset")

    def _on_qr_changed(self, checked: bool) -> None:
        self._qr_enabled = checked
        self.settings.set("qr_enabled", checked)
        if not checked:
            self._qr_result = None
            if hasattr(self, "lbl_qr"):
                self.lbl_qr.hide()
        else:
            if hasattr(self, "lbl_qr"):
                self.lbl_qr.show()
                self.lbl_qr.raise_()
        self._show_status("QR/Barcode " + ("attivo" if checked else "disattivato"))

    def _on_focus_changed(self, checked: bool) -> None:
        self._focus_assist_enabled = checked
        self.settings.set("focus_assist", checked)
        self._show_status("Focus assist " + ("attivo" if checked else "disattivato"))

    def _on_face_changed(self, checked: bool) -> None:
        self._face_framing_enabled = checked
        self.settings.set("face_framing", checked)
        self._show_status("Face framing " + ("attivo" if checked else "disattivato"))

    def _on_timelapse_changed(self, checked: bool) -> None:
        self._timelapse_enabled = checked
        self.settings.set("timelapse", checked)
        if checked and self._timelapse_timer is None:
            self._timelapse_frames = []
            self._timelapse_timer = QTimer(self)
            self._timelapse_timer.setInterval(self._timelapse_interval * 1000)
            self._timelapse_timer.timeout.connect(self._capture_timelapse_frame)
            self._timelapse_timer.start()
        elif not checked:
            if self._timelapse_timer is not None:
                self._timelapse_timer.stop()
                self._timelapse_timer.deleteLater()
                self._timelapse_timer = None
            if len(self._timelapse_frames) > 1:
                self._assemble_timelapse()
        self._show_status("Time-lapse " + ("avviato" if checked else "fermo"))

    def _on_timelapse_interval_changed(self, value: int) -> None:
        self._timelapse_interval = value
        self.settings.set("timelapse_interval", value)
        if self._timelapse_timer is not None:
            self._timelapse_timer.setInterval(value * 1000)

    def _on_mintcast_changed(self, checked: bool) -> None:
        if checked and not self._mintcast_enabled:
            self._start_virtual_cam()
        elif not checked and self._mintcast_enabled:
            self._stop_virtual_cam()
            self._show_status("MintCast disattivato")
        self._mintcast_enabled = checked
        if checked and self._mintcast_enabled:
            self.settings.set("mintcast", True)

    def _on_frame_ready(self, frame: np.ndarray) -> None:
        self._current_frame = frame

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def _update_preview(self) -> None:
        if getattr(self, "_pause_preview", False):
            return
        frame = self._current_frame
        if frame is None:
            return
        processed = self._apply_adjustments(self._apply_filter(frame.copy()))
        processed = self._apply_format(processed)
        if self._mirror:
            processed = cv2.flip(processed, 1)
        if self._grid:
            processed = self._draw_grid_on_frame(processed)
        if getattr(self, "_face_framing_enabled", False):
            processed = self._apply_face_framing(processed)
        self._processed_frame = processed
        if self._recording and self.recorder.is_recording():
            rec_frame = processed
            if rec_frame.ndim != 3 or rec_frame.shape[2] != 3:
                if rec_frame.ndim == 2:
                    rec_frame = cv2.cvtColor(rec_frame, cv2.COLOR_GRAY2BGR)
                else:
                    rec_frame = cv2.cvtColor(rec_frame, cv2.COLOR_BGR2RGB)
            if self._recording_frame_size is not None:
                th, tw = self._recording_frame_size
                h, w = rec_frame.shape[:2]
                if (w, h) != (tw, th):
                    if w >= tw or h >= th:
                        y1 = max(0, (h - th) // 2)
                        x1 = max(0, (w - tw) // 2)
                        rec_frame = rec_frame[y1 : y1 + th, x1 : x1 + tw]
                    else:
                        canvas = np.zeros((th, tw, 3), dtype=np.uint8)
                        y1 = max(0, (th - h) // 2)
                        x1 = max(0, (tw - w) // 2)
                        canvas[y1 : y1 + h, x1 : x1 + w] = rec_frame
                        rec_frame = canvas
                if rec_frame.shape[:2] != (th, tw):
                    rec_frame = cv2.resize(rec_frame, (tw, th))
            self.recorder.write(rec_frame)
            if self._clip_seconds > 0 and self.recorder.elapsed() >= self._clip_seconds:
                self._stop_recording()
                self._show_status(f"Registrazione fermata dopo {self._clip_seconds}s")
        if getattr(self, "_qr_enabled", False):
            self._scan_qr(processed)
            self.lbl_qr.setText("Scanning…" if not getattr(self, "_qr_result", None) else self._qr_result)
            self.lbl_qr.show()
            self.lbl_qr.raise_()
        else:
            self.lbl_qr.hide()
        if getattr(self, "_focus_assist_enabled", False):
            score = self._compute_focus_score(processed)
            color = "#ef4444" if score < 80 else "#f59e0b" if score < 180 else "#5cd962"
            self.lbl_focus.setStyleSheet(
                f"border-radius: 12px; border: 3px solid {color}; background-color: {color};"
            )
            self.lbl_focus.show()
            self.lbl_focus.raise_()
            self.lbl_status.setText(f"Focus score: {score:.1f}")
        else:
            self.lbl_focus.hide()
        if getattr(self, "_mintcast_enabled", False):
            self._write_mintcast_frame(processed)
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

    def _draw_grid_on_frame(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        overlay = frame.copy()
        color = (0, 255, 0)
        thickness = 1
        rows, cols = 3, 3
        for i in range(1, cols):
            x = int(w * i / cols)
            cv2.line(overlay, (x, 0), (x, h), color, thickness)
        for i in range(1, rows):
            y = int(h * i / rows)
            cv2.line(overlay, (0, y), (w, y), color, thickness)
        return overlay

    def _position_overlays(self) -> None:
        if hasattr(self, "lbl_countdown"):
            self.lbl_countdown.setFixedSize(self.preview.width() // 2, self.preview.height() // 3)
            self.lbl_countdown.move(
                (self.preview.width() - self.lbl_countdown.width()) // 2,
                (self.preview.height() - self.lbl_countdown.height()) // 2,
            )
        if hasattr(self, "lbl_rec"):
            self.lbl_rec.move(12, self.preview.height() - 36)
            self.lbl_rec.adjustSize()
            self.lbl_rec.raise_()
        if hasattr(self, "flash"):
            self.flash.setGeometry(self.preview_container.rect())
        if hasattr(self, "grid_overlay"):
            self.grid_overlay.setGeometry(self.preview_container.rect())
        if hasattr(self, "lbl_qr"):
            self.lbl_qr.setFixedWidth(min(self.preview.width() // 2, 400))
            self.lbl_qr.adjustSize()
            self.lbl_qr.move(
                (self.preview.width() - self.lbl_qr.width()) // 2,
                (self.preview.height() - self.lbl_qr.height()) // 2,
            )
            self.lbl_qr.raise_()
        if hasattr(self, "lbl_focus"):
            self.lbl_focus.move(self.preview.width() - 40, self.preview.height() - 40)
            self.lbl_focus.raise_()

    def _draw_grid(self) -> None:
        if not getattr(self, "_grid", False):
            self.grid_overlay.hide()
            return
        self.grid_overlay.show()
        self.grid_overlay.update()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_overlays()

    # ------------------------------------------------------------------
    # Photo / Timer / Flash
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
        self._flash_effect()
        count = self._burst_count
        if count <= 1:
            path = Storage.save_photo(frame, quality=self._photo_quality)
            if path is None:
                self._show_status("Errore salvataggio foto", error=True)
                return
            self._show_status(f"Foto salvata: {path}")
            self.status.showMessage(f"Foto salvata: {path}", 5000)
            self._add_recent_media(path)
        else:
            self._burst_index = 0
            self._burst_frames = [frame.copy() for _ in range(count)]
            self._burst_timer = QTimer(self)
            self._burst_timer.setInterval(300)
            self._burst_timer.timeout.connect(self._save_next_burst)
            self._burst_timer.start()
            self.btn_photo.setEnabled(False)
            self._show_status(f"Burst {count} foto…")

    def _save_next_burst(self) -> None:
        if self._burst_index >= len(self._burst_frames):
            self._burst_timer.stop()
            self._burst_timer.deleteLater()
            self._burst_timer = None
            self.btn_photo.setEnabled(True)
            self._show_status(f"Burst completato: {len(self._burst_frames)} foto")
            return
        frame = self._burst_frames[self._burst_index]
        path = Storage.save_photo(frame, quality=self._photo_quality)
        self._burst_index += 1
        if path is not None:
            self._add_recent_media(path)

    def _flash_effect(self) -> None:
        self.flash.show()
        self.flash.setGeometry(self.preview_container.rect())
        self.flash.raise_()
        QTimer.singleShot(80, self._fade_flash)

    def _fade_flash(self) -> None:
        self.flash.hide()
        self.flash.setGraphicsEffect(None)

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
        self._recording_frame_size = frame.shape[:2][::-1]
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
        self.combo_resolution.setEnabled(False)
        self.combo_format.setEnabled(False)
        self.lbl_rec.show()
        self.lbl_rec.raise_()
        self.lbl_rec.setText("● REC")
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
        self.combo_resolution.setEnabled(True)
        self.combo_format.setEnabled(True)
        self.lbl_rec.hide()
        if hasattr(self, "_rec_timer") and self._rec_timer is not None:
            self._rec_timer.stop()
            self._rec_timer.deleteLater()
            self._rec_timer = None
        self._recording_frame_size = None
        if path:
            self._show_status(f"Registrazione salvata: {path}")
            self.status.showMessage(f"Registrazione salvata: {path}", 5000)
            self._add_recent_media(path)
        else:
            self._show_status("Registrazione interrotta senza salvataggio", error=True)

    def _update_rec_time(self) -> None:
        elapsed = self.recorder.elapsed()
        m, s = divmod(int(elapsed), 60)
        self.lbl_rec.setText(f"● REC {m:02d}:{s:02d}")

    # ------------------------------------------------------------------
    # Recent media
    # ------------------------------------------------------------------
    def _load_recent_media(self) -> None:
        self._recent_media = []
        for folder in (Storage.photos_dir(), Storage.recordings_dir()):
            if not folder.exists():
                continue
            try:
                files = [p for p in folder.glob("*") if p.is_file()]
                files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[: self._max_recent]
                self._recent_media.extend(files)
            except Exception as exc:
                logger.debug("Impossibile caricare i file recenti da %s: %s", folder, exc)
        self._recent_media = self._recent_media[: self._max_recent]
        self._refresh_recent_strip()

    def _add_recent_media(self, path: Path) -> None:
        self._recent_media.insert(0, path)
        self._recent_media = self._recent_media[: self._max_recent]
        self._refresh_recent_strip()

    def _refresh_recent_strip(self) -> None:
        for i, lbl in enumerate(self._recent_labels):
            if i < len(self._recent_media):
                path = self._recent_media[i]
                pix = QPixmap(str(path))
                if not pix.isNull():
                    pix = pix.scaled(72, 54, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    rect = pix.rect()
                    rect.moveCenter(QPoint(36, 27))
                    pix = pix.copy(rect)
                    lbl.setPixmap(pix)
                else:
                    lbl.setPixmap(QPixmap())
                    lbl.setText("🎬" if path.suffix.lower() == ".mp4" else "🖼")
                lbl.setToolTip(str(path))
                lbl.setCursor(QCursor(Qt.PointingHandCursor))
                lbl.mousePressEvent = lambda ev, p=path: self._open_recent(p)
            else:
                lbl.clear()
                lbl.setToolTip("")

    def _open_recent(self, path: Path) -> None:
        if path.exists():
            Storage.open_folder(path.parent)

    # ------------------------------------------------------------------
    # Folder / Fullscreen
    # ------------------------------------------------------------------
    def _on_open_folder(self) -> None:
        if self.combo_folder.currentIndex() == 0:
            Storage.open_folder(Storage.photos_dir())
        else:
            Storage.open_folder(Storage.recordings_dir())

    def _toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.showFullScreen()
            self.btn_fullscreen.setText("Esci da schermo intero")
        else:
            self.showNormal()
            self.btn_fullscreen.setText("Schermo intero")

    # ------------------------------------------------------------------
    # Autostart
    # ------------------------------------------------------------------
    def _autostart_desktop_path(self) -> Path:
        return Path.home() / ".config" / "autostart" / "mintcam.desktop"

    def _autostart_launcher_path(self) -> Path:
        candidates = [Path.home() / ".local/bin/mintcam", Path("/usr/bin/mintcam")]
        for path in candidates:
            if path.exists():
                return path
        exe = shutil.which("mintcam")
        if exe:
            return Path(exe)
        return candidates[0]

    def _is_autostart_enabled(self) -> bool:
        path = self._autostart_desktop_path()
        if not path.exists():
            return False
        try:
            content = path.read_text(encoding="utf-8")
            if "X-GNOME-Autostart-enabled=false" in content:
                return False
            return True
        except Exception:
            return False

    def _set_autostart(self, enabled: bool) -> None:
        path = self._autostart_desktop_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if enabled:
                launcher = self._autostart_launcher_path()
                content = (
                    "[Desktop Entry]\n"
                    "Name=MintCam\n"
                    f"Exec={launcher}\n"
                    "Icon=camera-photo\n"
                    "Terminal=false\n"
                    "Type=Application\n"
                    "Categories=AudioVideo;Video;Recorder;\n"
                    "X-GNOME-Autostart-enabled=true\n"
                )
                path.write_text(content, encoding="utf-8")
                path.chmod(0o644)
            else:
                if path.exists():
                    path.unlink()
        except Exception as exc:
            logger.error("Impossibile %s l'avvio automatico: %s", "abilitare" if enabled else "disabilitare", exc)

    def _load_autostart_state(self) -> None:
        enabled = self._is_autostart_enabled()
        self.chk_autostart.blockSignals(True)
        self.chk_autostart.setChecked(enabled)
        self.chk_autostart.blockSignals(False)

    def _on_autostart_changed(self, checked: bool) -> None:
        self.settings.set("autostart", checked)
        self._set_autostart(checked)
        self._show_status("Avvio automatico " + ("abilitato" if checked else "disabilitato"))

    # ------------------------------------------------------------------
    # Header / status
    # ------------------------------------------------------------------
    def _update_header_info(self) -> None:
        self.lbl_info.setText(f"{self._width}x{self._height} · {self._fps} FPS")

    def _show_status(self, message: str, error: bool = False) -> None:
        color = "#ef4444" if error else "#5cd962"
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.lbl_status.setText(message)
        logger.info(message)

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.combo_camera.currentIndexChanged.connect(self._on_camera_changed)
        self.combo_resolution.currentTextChanged.connect(self._on_resolution_changed)
        self.combo_fps.valueChanged.connect(self._on_fps_changed)
        self.combo_filter.currentTextChanged.connect(self._on_filter_changed)
        self.combo_format.currentTextChanged.connect(self._on_format_changed)
        self.combo_timer.currentIndexChanged.connect(self._on_timer_changed)
        self.slider_brightness["slider"].valueChanged.connect(self._on_brightness_changed)
        self.slider_contrast["slider"].valueChanged.connect(self._on_contrast_changed)
        self.slider_saturation["slider"].valueChanged.connect(self._on_saturation_changed)
        self.chk_mirror.toggled.connect(self._on_mirror_changed)
        self.chk_grid.toggled.connect(self._on_grid_changed)
        self.chk_pause.toggled.connect(self._on_pause_changed)
        self.chk_qr.toggled.connect(self._on_qr_changed)
        self.chk_focus.toggled.connect(self._on_focus_changed)
        self.chk_face.toggled.connect(self._on_face_changed)
        self.chk_timelapse.toggled.connect(self._on_timelapse_changed)
        self.spin_timelapse_interval.valueChanged.connect(self._on_timelapse_interval_changed)
        self.chk_mintcast.toggled.connect(self._on_mintcast_changed)
        self.combo_burst.currentIndexChanged.connect(self._on_burst_changed)
        self.spin_clip.valueChanged.connect(self._on_clip_changed)
        self.spin_quality.valueChanged.connect(self._on_quality_changed)
        self.combo_folder.currentIndexChanged.connect(self._on_folder_changed)

    # ------------------------------------------------------------------
    # QR/Barcode
    # ------------------------------------------------------------------
    def _scan_qr(self, frame: np.ndarray) -> None:
        if not _QR_AVAILABLE or not getattr(self, "_qr_enabled", False):
            return
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            results = qr_decode(gray)
            if results:
                text = " | ".join([r.data.decode("utf-8", errors="ignore") for r in results])
                self._qr_result = text
            else:
                self._qr_result = None
        except Exception as exc:
            logger.debug("Errore scansione QR: %s", exc)

    # ------------------------------------------------------------------
    # Focus assist
    # ------------------------------------------------------------------
    def _compute_focus_score(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # ------------------------------------------------------------------
    # Face auto-framing
    # ------------------------------------------------------------------
    def _apply_face_framing(self, frame: np.ndarray) -> np.ndarray:
        if not getattr(self, "_face_framing_enabled", False):
            return frame
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                return frame
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(faces) == 0:
                return frame
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            cx, cy = x + w // 2, y + h // 2
            fh, fw = frame.shape[:2]
            target_zoom = 1.6
            new_w = int(fw / target_zoom)
            new_h = int(fh / target_zoom)
            x1 = max(0, min(fw - new_w, cx - new_w // 2))
            y1 = max(0, min(fh - new_h, cy - new_h // 2))
            return frame[y1 : y1 + new_h, x1 : x1 + new_w]
        except AttributeError:
            logger.debug("CascadeClassifier non disponibile in questo OpenCV")
            return frame
        except Exception as exc:
            logger.debug("Errore face framing: %s", exc)
            return frame

    # ------------------------------------------------------------------
    # Time-lapse
    # ------------------------------------------------------------------
    def _capture_timelapse_frame(self) -> None:
        frame = self._processed_frame if self._processed_frame is not None else self._current_frame
        if frame is None:
            return
        self._timelapse_frames.append(frame.copy())
        self._show_status(f"Time-lapse: {len(self._timelapse_frames)} frame")

    def _assemble_timelapse(self) -> None:
        if len(self._timelapse_frames) < 2:
            return
        path = Storage.recordings_dir() / f"timelapse_{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4"
        h, w = self._timelapse_frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, 30, (w, h))
        for frame in self._timelapse_frames:
            if frame.shape[:2] != (h, w):
                frame = cv2.resize(frame, (w, h))
            if frame.ndim != 3 or frame.shape[2] != 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            writer.write(frame)
        writer.release()
        self._show_status(f"Time-lapse salvato: {path}")
        self.status.showMessage(f"Time-lapse salvato: {path}", 5000)
        self._add_recent_media(path)

    # ------------------------------------------------------------------
    # MintCast virtual cam
    # ------------------------------------------------------------------
    def _start_virtual_cam(self) -> bool:
        try:
            import os
            import subprocess

            if not os.path.exists(self._mintcast_device):
                self._show_status(
                    "MintCast: /dev/video10 non disponibile. "
                    "Per attivarlo:\n"
                    "  sudo apt install v4l2loopback-dkms\n"
                    "  sudo modprobe v4l2loopback devices=1 video_nr=10 exclusive_caps=1\n"
                    "  sudo usermod -aG video $USER  (poi riavvia)",
                    error=True,
                )
                return False
            try:
                self._mintcast_writer = open(self._mintcast_device, "wb", buffering=0)
            except PermissionError:
                self._show_status(
                    f"MintCast: permessi insufficienti per {self._mintcast_device}. "
                    "Aggiungi l'utente al gruppo video: sudo usermod -aG video $USER",
                    error=True,
                )
                return False
            self._show_status(f"MintCast attivo su {self._mintcast_device}")
            return True
        except Exception as exc:
            logger.error("Impossibile avviare MintCast: %s", exc)
            self._show_status(f"MintCast errore: {exc}", error=True)
            return False

    def _stop_virtual_cam(self) -> None:
        try:
            if hasattr(self, "_mintcast_writer") and self._mintcast_writer is not None:
                self._mintcast_writer.close()
                self._mintcast_writer = None
        except Exception:
            pass

    def _write_mintcast_frame(self, frame: np.ndarray) -> None:
        if not getattr(self, "_mintcast_enabled", False):
            return
        try:
            if hasattr(self, "_mintcast_writer") and self._mintcast_writer is not None:
                self._mintcast_writer.write(frame.tobytes())
        except BrokenPipeError:
            self._show_status("MintCast: dispositivo non disponibile", error=True)
            self._mintcast_enabled = False
            if hasattr(self, "chk_mintcast"):
                self.chk_mintcast.setChecked(False)
        except Exception as exc:
            logger.debug("Errore scrittura MintCast: %s", exc)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._fullscreen:
            self._toggle_fullscreen()
        if self._recording:
            self._stop_recording()
        if self.camera is not None:
            self.camera.stop()
            self.camera = None
        if hasattr(self, "_preview_timer") and self._preview_timer is not None:
            self._preview_timer.stop()
        event.accept()
