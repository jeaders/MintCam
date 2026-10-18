import logging
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import QCursor, QDesktopServices, QGuiApplication, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
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
from app.version import __version__

logger = logging.getLogger("mintcam.ui")

# How many consecutive failures before a feature gives up visibly instead of
# failing silently on every frame.
class _RecordingCancelled(Exception):
    """Raised when the user declines to record (for example low disk space)."""


# How often the device list is re-checked for hotplug.
_CAMERA_WATCH_INTERVAL_MS = 5000

# Quantità di punteggi di messa a fuoco conservati per il confronto.
_FOCUS_HISTORY = 40

_FACE_FAILURE_LIMIT = 5
_PREVIEW_FAILURE_LIMIT = 10

# Per-frame processing is guarded: an exception in any step (filter, face
# framing, motion, recorder, streaming) must not take the whole application
# down, because PyQt aborts the process on an unhandled exception in a slot.
# See _update_preview and _apply_face_framing.


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("MintCam"))
        self.resize(1200, 780)
        self.setMinimumSize(860, 620)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
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
        self._audio_enabled: bool = False
        self._background_blur: bool = False
        self._blur_strength: int = 15
        self._motion_detection: bool = False
        self._motion_sensitivity: int = 20
        self._motion_reference: Optional[np.ndarray] = None
        self._motion_inactive_timer: Optional[QTimer] = None
        self._motion_last_detected: float = 0.0
        self._presets: dict = {}
        self._face_failures: int = 0
        self._preview_failures: int = 0
        self._last_recorded_frame: int = -1
        self._focus_scores: list = []
        self._face_seen: bool = False
        self._language: str = "it"
        self._face_cascade: Optional[Path] = None
        self._last_camera_devices: list = list(self._camera_devices_initial())
        self._face_classifier_obj = None
        self._fps_counter: int = 0
        self._fps_last_time: Optional[float] = None
        self._actual_fps: float = 0.0
        self._update_checking: bool = False
        self._audio_devices: list[tuple[str, str]] = []

        self._streaming: bool = False
        self._stream_process: Optional[subprocess.Popen] = None
        self._stream_url: str = ""
        self._stream_width: int = 640
        self._stream_height: int = 480
        self._stream_fps: int = 30
        self._stream_frame_count: int = 0
        self._stream_lock = threading.Lock()

        self._recent_media: list[Path] = []
        self._max_recent = 8

        from app.i18n import install as _install_language
        self._language = self.settings.get("language") or "it"
        if self._language not in ("it", "en"):
            self._language = "it"
        _install_language(QApplication.instance(), self._language)

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
        bg.setObjectName("bg")
        bg.setStyleSheet("QWidget#bg { background-color: #0f1115; }")
        bg_lay = QGridLayout(bg)
        bg_lay.setContentsMargins(16, 12, 16, 12)
        bg_lay.setSpacing(12)
        root.addWidget(bg, 0, 0, 1, 1)

        header = self._build_header()
        bg_lay.addWidget(header, 0, 0, 1, 2)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
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
        preview_container.setObjectName("preview_container")
        preview_container.setStyleSheet("QWidget#preview_container { background-color: #0f1115; }")
        preview_lay = QVBoxLayout(preview_container)
        preview_lay.setContentsMargins(0, 0, 0, 0)
        preview_lay.setSpacing(0)

        self.preview_container = QWidget()
        self.preview_container.setObjectName("preview_overlay")
        self.preview_container.setStyleSheet(
            "QWidget#preview_overlay { background-color: #0f1115; }")
        preview_container_lay = QGridLayout(self.preview_container)
        preview_container_lay.setContentsMargins(0, 0, 0, 0)
        preview_container_lay.setSpacing(0)

        self.preview = QLabel(self.tr("Anteprima non disponibile"))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 360)
        self.preview.setStyleSheet(
            "background-color: #0a0c10; color: #6b7280; font-size: 16px; border-radius: 12px;"
        )
        self.preview.setScaledContents(False)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        self._refresh_presets()
        self._install_shortcuts()
        self._connect_signals()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("header")
        header.setStyleSheet("QWidget#header { background-color: #0f1115; }")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        logo_label = QLabel()
        logo_label.setFixedSize(40, 40)
        logo_pix = self._load_logo()
        if not logo_pix.isNull():
            logo_pix = logo_pix.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pix)
        else:
            logo_label.setText(self.tr("📷"))
        logo_label.setStyleSheet("font-size: 22px; padding: 4px; border-radius: 8px;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(self.tr("MintCam"))
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #5cd962; letter-spacing: -0.3px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel(self.tr("Inizializzazione webcam…"))
        self.lbl_status.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.lbl_info = QLabel(self.tr(""))
        self.lbl_info.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.lbl_fps = QLabel(self.tr(""))
        self.lbl_fps.setStyleSheet("color: #6b7280; font-size: 11px;")

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
        lay.addWidget(self.lbl_fps)
        return header

    def _load_logo(self) -> QPixmap:
        # PNG first: it is built into Qt, while JPEG needs an image format
        # plugin that Debian keeps in a separate package and is not always
        # installed, which used to leave the header with a placeholder glyph.
        candidates = [
            Path("/usr/share/pixmaps/mintcam.png"),
            Path(__file__).resolve().parent.parent.parent / "assets" / "mintcam.png",
            Path("/usr/share/mintcam/assets/mintcam.png"),
            Path(__file__).resolve().parent.parent.parent / "assets" / "mintcam-logo.jpg",
            Path("/usr/share/mintcam/assets/mintcam-logo.jpg"),
        ]
        for path in candidates:
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    return pix
        return QPixmap()

    def _build_card_camera(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Fotocamera"))
        grp.setObjectName("sidebar-card")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_camera = QComboBox()
        self.combo_camera.setMinimumHeight(32)
        lay.addWidget(self.combo_camera)
        return grp

    def _build_card_resolution(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Risoluzione e FPS"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(list(RESOLUTIONS.keys()))
        self.combo_fps = QSpinBox()
        self.combo_fps.setRange(1, 120)
        self.combo_fps.setValue(30)
        lay.addWidget(QLabel(self.tr("Risoluzione:")))
        lay.addWidget(self.combo_resolution)
        lay.addWidget(QLabel(self.tr("FPS:")))
        lay.addWidget(self.combo_fps)
        return grp

    def _build_card_filter(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Filtro"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_filter = QComboBox()
        self.combo_filter.addItems([self.tr("Normale"), self.tr("Bianco e nero"), self.tr("Sepia"), self.tr("Negativo"), self.tr("Contrasto elevato")])
        lay.addWidget(self.combo_filter)
        return grp

    def _build_card_format(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Formato"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_format = QComboBox()
        self.combo_format.addItems([self.tr("16:9"), self.tr("4:3"), self.tr("9:16")])
        lay.addWidget(self.combo_format)
        return grp

    def _build_card_timer(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Timer foto"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.combo_timer = QComboBox()
        self.combo_timer.addItems([self.tr("Nessun timer"), self.tr("3 secondi"), self.tr("5 secondi"), self.tr("10 secondi")])
        lay.addWidget(self.combo_timer)
        return grp

    def _build_card_adjustments(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Regolazioni"))
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
        grp = QGroupBox(self.tr("Strumenti"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        self.chk_mirror = QCheckBox(self.tr("Effetto specchio"))
        self.chk_mirror.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_mirror.toggled.connect(self._on_mirror_changed)
        lay.addWidget(self.chk_mirror)
        self.chk_grid = QCheckBox(self.tr("Griglia"))
        self.chk_grid.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_grid.toggled.connect(self._on_grid_changed)
        lay.addWidget(self.chk_grid)
        self.chk_pause = QCheckBox(self.tr("Pausa anteprima"))
        self.chk_pause.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_pause.toggled.connect(self._on_pause_changed)
        lay.addWidget(self.chk_pause)
        self.chk_qr = QCheckBox(self.tr("Scanner QR e codici a barre"))
        self.chk_qr.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_qr.setEnabled(_QR_AVAILABLE)
        self.chk_qr.toggled.connect(self._on_qr_changed)
        lay.addWidget(self.chk_qr)
        self.chk_focus = QCheckBox(self.tr("Aiuto messa a fuoco"))
        self.chk_focus.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_focus.toggled.connect(self._on_focus_changed)
        lay.addWidget(self.chk_focus)
        self.chk_face = QCheckBox(self.tr("Inquadratura sul volto"))
        self.chk_face.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_face.toggled.connect(self._on_face_changed)
        lay.addWidget(self.chk_face)

        self.chk_audio = QCheckBox(self.tr("Audio durante registrazione"))
        self.chk_audio.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_audio.toggled.connect(self._on_audio_changed)
        lay.addWidget(self.chk_audio)

        self.chk_blur_bg = QCheckBox(self.tr("Sfondo sfocato"))
        self.chk_blur_bg.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_blur_bg.toggled.connect(self._on_blur_bg_changed)
        lay.addWidget(self.chk_blur_bg)
        self.slider_blur = self._make_slider(5, 51, 15, "Intensità blur")
        self.slider_blur["slider"].setEnabled(False)
        self.chk_blur_bg.toggled.connect(lambda checked: self.slider_blur["slider"].setEnabled(checked))
        lay.addWidget(self.slider_blur["label"])
        lay.addWidget(self.slider_blur["slider"])

        self.chk_motion = QCheckBox(self.tr("Rilevamento movimento"))
        self.chk_motion.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_motion.toggled.connect(self._on_motion_changed)
        lay.addWidget(self.chk_motion)
        self.slider_motion = self._make_slider(5, 50, 20, "Sensibilità:")
        lay.addWidget(self.slider_motion["label"])
        lay.addWidget(self.slider_motion["slider"])

        # Preset manager
        self.lbl_preset_title = QLabel(self.tr("Preset"))
        self.lbl_preset_title.setStyleSheet("color: #5cd962; font-size: 11px; font-weight: 700;")
        lay.addWidget(self.lbl_preset_title)
        self.combo_preset = QComboBox()
        self.combo_preset.setMinimumHeight(32)
        lay.addWidget(self.combo_preset)
        preset_btns = QHBoxLayout()
        preset_btns.setSpacing(6)
        self.btn_save_preset = QPushButton(self.tr("Salva"))
        self.btn_save_preset.setObjectName("ghost")
        self.btn_save_preset.setMinimumHeight(28)
        self.btn_save_preset.clicked.connect(self._save_preset)
        self.btn_load_preset = QPushButton(self.tr("Carica"))
        self.btn_load_preset.setObjectName("ghost")
        self.btn_load_preset.setMinimumHeight(28)
        self.btn_load_preset.clicked.connect(self._load_preset)
        self.btn_delete_preset = QPushButton(self.tr("Elimina"))
        self.btn_delete_preset.setObjectName("ghost")
        self.btn_delete_preset.setMinimumHeight(28)
        self.btn_delete_preset.clicked.connect(self._delete_preset)
        preset_btns.addWidget(self.btn_save_preset)
        preset_btns.addWidget(self.btn_load_preset)
        preset_btns.addWidget(self.btn_delete_preset)
        lay.addLayout(preset_btns)

        self.slider_zoom = self._make_slider(100, 300, 100, "Zoom:")
        self.slider_zoom["slider"].valueChanged.connect(self._on_zoom_changed)
        lay.addWidget(self.slider_zoom["label"])
        lay.addWidget(self.slider_zoom["slider"])

        # Streaming
        self.txt_stream_url = QLineEdit()
        self.txt_stream_url.setPlaceholderText("rtmp://server/app/key")
        self.txt_stream_url.setStyleSheet(
            "background-color: #1e222b; color: #e6e9ef; border: 1px solid #2c333f; border-radius: 8px; padding: 6px 10px;"
        )
        lay.addWidget(QLabel(self.tr("URL stream RTMP:")))
        lay.addWidget(self.txt_stream_url)
        self.btn_stream = QPushButton(self.tr("Avvia streaming"))
        self.btn_stream.setObjectName("ghost")
        self.btn_stream.setMinimumHeight(32)
        self.btn_stream.clicked.connect(self._on_stream_toggle)
        lay.addWidget(self.btn_stream)
        self.chk_timelapse = QCheckBox(self.tr("Time-lapse (foto in sequenza)"))
        self.chk_timelapse.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_timelapse.toggled.connect(self._on_timelapse_changed)
        lay.addWidget(self.chk_timelapse)
        self.spin_timelapse_interval = QSpinBox()
        self.spin_timelapse_interval.setRange(1, 60)
        self.spin_timelapse_interval.setSuffix(" s")
        self.spin_timelapse_interval.setValue(1)
        self.spin_timelapse_interval.valueChanged.connect(self._on_timelapse_interval_changed)
        lay.addWidget(QLabel(self.tr("Intervallo time-lapse:")))
        lay.addWidget(self.spin_timelapse_interval)
        self.combo_burst = QComboBox()
        self.combo_burst.addItems([self.tr("Singolo"), self.tr("Burst 3"), self.tr("Burst 5"), self.tr("Burst 10")])
        self.combo_burst.currentIndexChanged.connect(self._on_burst_changed)
        lay.addWidget(QLabel(self.tr("Modalità scatto:")))
        lay.addWidget(self.combo_burst)
        self.spin_clip = QSpinBox()
        self.spin_clip.setRange(0, 3600)
        self.spin_clip.setSpecialValueText("Illimitato")
        self.spin_clip.setValue(0)
        self.spin_clip.valueChanged.connect(self._on_clip_changed)
        lay.addWidget(QLabel(self.tr("Durata max registrazione (s):")))
        lay.addWidget(self.spin_clip)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(50, 100)
        self.spin_quality.setValue(95)
        self.spin_quality.valueChanged.connect(self._on_quality_changed)
        lay.addWidget(QLabel(self.tr("Qualità foto:")))
        lay.addWidget(self.spin_quality)
        self.combo_folder = QComboBox()
        self.combo_folder.addItems([self.tr("Foto"), self.tr("Registrazioni")])
        self.combo_folder.currentIndexChanged.connect(self._on_folder_changed)
        lay.addWidget(QLabel(self.tr("Cartella apertura:")))
        lay.addWidget(self.combo_folder)
        btn_reset_adj = QPushButton(self.tr("Reset regolazioni"))
        btn_reset_adj.setObjectName("ghost")
        btn_reset_adj.clicked.connect(self._reset_adjustments)
        lay.addWidget(btn_reset_adj)
        return grp

    def _build_card_general(self) -> QGroupBox:
        grp = QGroupBox(self.tr("Generale"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        from app.i18n import available as _available_languages
        lay.addWidget(QLabel(self.tr("Lingua:")))
        self.combo_language = QComboBox()
        self.combo_language.setMinimumHeight(32)
        for _code, _name in _available_languages():
            self.combo_language.addItem(_name, _code)
        lay.addWidget(self.combo_language)
        # preseleziona la lingua attiva: senza, il selettore mostra la prima
        # della lista e l'utente non sa quale è in uso
        _current = self.combo_language.findData(self._language)
        self.combo_language.blockSignals(True)
        if _current >= 0:
            self.combo_language.setCurrentIndex(_current)
        self.combo_language.blockSignals(False)
        self.combo_language.currentIndexChanged.connect(self._on_language_changed)

        self.chk_autostart = QCheckBox(self.tr("Avvio automatico con il sistema"))
        self.chk_autostart.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        self.chk_autostart.toggled.connect(self._on_autostart_changed)
        lay.addWidget(self.chk_autostart)

        lay.addSpacing(6)
        lay.addWidget(QLabel(self.tr("Dispositivo audio:")))
        self.combo_audio_device = QComboBox()
        self.combo_audio_device.setMinimumHeight(32)
        self._refresh_audio_devices()
        lay.addWidget(self.combo_audio_device)
        self.combo_audio_device.currentIndexChanged.connect(self._on_audio_device_changed)

        lay.addSpacing(6)
        self.btn_check_update = QPushButton(self.tr("Cerca aggiornamenti"))
        self.btn_check_update.setMinimumHeight(32)
        self.btn_check_update.setObjectName("ghost")
        lay.addWidget(self.btn_check_update)
        self.btn_check_update.clicked.connect(self._on_check_update)
        return grp

    def _make_slider(self, minv: int, maxv: int, value: int, name: str) -> dict:
        label = QLabel(f"{name}: {value}")
        label.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(minv, maxv)
        s.setValue(value)
        s.setTickPosition(QSlider.TickPosition.TicksBelow)
        s.setTickInterval(25)
        s.valueChanged.connect(lambda v: label.setText(f"{name}: {v}"))
        return {"label": label, "slider": s}

    def _build_recent_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedHeight(90)
        strip.setObjectName("recent_strip")
        strip.setStyleSheet(
            "QWidget#recent_strip { background-color: #0f1115; border-top: 1px solid #1e222b; }")
        lay = QHBoxLayout(strip)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(8)
        lbl = QLabel(self.tr("Recenti"))
        lbl.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 700;")
        lay.addWidget(lbl)
        self._recent_labels: list[QLabel] = []
        for _ in range(self._max_recent):
            thumb = QLabel()
            thumb.setFixedSize(72, 54)
            thumb.setStyleSheet("background-color: #1e222b; border-radius: 8px; border: 1px solid #252a35;")
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setToolTip(self.tr(""))
            lay.addWidget(thumb)
            self._recent_labels.append(thumb)
        lay.addStretch()
        return strip

    def _build_overlays(self, parent_layout) -> None:
        # Flash
        self.flash = QWidget(self.preview_container)
        self.flash.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.flash.setStyleSheet("background-color: rgba(255,255,255,200); border-radius: 12px;")
        self.flash.hide()
        parent_layout.addWidget(self.flash, 0, 0, 1, 1)

        # Grid
        self.grid_overlay = QWidget(self.preview_container)
        self.grid_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.grid_overlay.setStyleSheet("background-color: transparent;")
        self.grid_overlay.hide()
        parent_layout.addWidget(self.grid_overlay, 0, 0, 1, 1)

        # Countdown
        self.lbl_countdown = QLabel(self.preview_container)
        self.lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_countdown.setStyleSheet(
            "background-color: rgba(15,17,21,200); color: #5cd962; font-size: 80px; font-weight: 900;"
            "border: 3px solid #5cd962; border-radius: 20px; padding: 20px;"
        )
        self.lbl_countdown.hide()
        parent_layout.addWidget(self.lbl_countdown, 0, 0, 1, 1)

        # REC indicator - small red light at bottom
        self.lbl_rec = QLabel(self.preview_container)
        self.lbl_rec.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_rec.setStyleSheet(
            "background-color: #ef4444; color: white; font-size: 11px; font-weight: 700;"
            "padding: 4px 10px; border-radius: 10px;"
        )
        self.lbl_rec.hide()
        self.lbl_rec.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_rec.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        parent_layout.addWidget(self.lbl_rec, 0, 0, 1, 1)

        # Audio level meter, shown while recording with audio. It reads the
        # loudness ffmpeg reports on stderr, so it needs no extra capture.
        self.lbl_level = QLabel(self.preview_container)
        self.lbl_level.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_level.setStyleSheet(
            "background-color: rgba(17, 19, 25, 0.85); color: #5cd962;"
            "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 10px;"
        )
        self.lbl_level.setText(self.tr("Livello audio"))
        self.lbl_level.hide()
        self.lbl_level.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_level.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        parent_layout.addWidget(self.lbl_level, 0, 0, 1, 1)

        # QR result
        self.lbl_qr = QLabel(self.preview_container)
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.lbl_qr.setWordWrap(True)
        self.lbl_qr.setStyleSheet(
            "background-color: rgba(15,17,21,200); color: #5cd962; font-size: 16px; font-weight: 700;"
            "border: 2px solid #5cd962; border-radius: 10px; padding: 10px;"
        )
        self.lbl_qr.hide()
        self.lbl_qr.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        parent_layout.addWidget(self.lbl_qr, 0, 0, 1, 1)

        # Focus assist indicator
        self.lbl_focus = QLabel(self.preview_container)
        self.lbl_focus.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self.lbl_focus.setFixedSize(24, 24)
        self.lbl_focus.setStyleSheet("border-radius: 12px; border: 3px solid #6b7280; background-color: transparent;")
        self.lbl_focus.hide()
        self.lbl_focus.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        parent_layout.addWidget(self.lbl_focus, 0, 0, 1, 1)

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("footer")
        footer.setStyleSheet(
            "QWidget#footer { background-color: #0f1115; border-top: 1px solid #1e222b; }")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.btn_photo = QPushButton(self.tr("Scatta foto"))
        self.btn_photo.setObjectName("primary")
        self.btn_photo.setMinimumHeight(44)
        self.btn_photo.clicked.connect(self._on_photo)

        self.btn_record = QPushButton(self.tr("Registra"))
        self.btn_record.setObjectName("record")
        self.btn_record.setMinimumHeight(44)
        self.btn_record.clicked.connect(self._on_record_toggle)

        self.btn_folder = QPushButton(self.tr("Apri cartella"))
        self.btn_folder.setObjectName("ghost")
        self.btn_folder.setMinimumHeight(44)
        self.btn_folder.clicked.connect(self._on_open_folder)

        self.btn_fullscreen = QPushButton(self.tr("Schermo intero"))
        self.btn_fullscreen.setObjectName("ghost")
        self.btn_fullscreen.setMinimumHeight(44)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)

        # Clipboard copy: the photo goes straight into the system clipboard,
        # so it can be pasted into Telegram, Discord, GIMP or anything else.
        self.btn_copy = QPushButton(self.tr("Copia scatto"))
        self.btn_copy.setObjectName("ghost")
        self.btn_copy.setMinimumHeight(44)
        self.btn_copy.setToolTip(
            "Copia l'ultima foto negli appunti (Ctrl+Maiusc+C). "
            "Per i video usa il pacchetto .deb o il confronto con la cartella.")
        self.btn_copy.clicked.connect(self._copy_last_media_to_clipboard)

        # Reveal: opens the folder of the last photo or recording selected
        self.btn_reveal = QPushButton(self.tr("Mostra file"))
        self.btn_reveal.setObjectName("ghost")
        self.btn_reveal.setMinimumHeight(44)
        self.btn_reveal.setToolTip(
            "Apre la cartella dell'ultimo file salvato, selezionandolo")
        self.btn_reveal.clicked.connect(self._reveal_last_media)

        self.btn_share = QPushButton(self.tr("Condividi"))
        self.btn_share.setObjectName("ghost")
        self.btn_share.setMinimumHeight(44)
        self.btn_share.setToolTip(
            "Prepara l'ultimo file per la condivisione: la foto la copia negli "
            "appunti, il video apre la cartella da cui trascinarlo")
        self.btn_share.clicked.connect(self._share_last_media)

        self.btn_stream_footer = QPushButton(self.tr("Avvia streaming"))
        self.btn_stream_footer.setObjectName("ghost")
        self.btn_stream_footer.setMinimumHeight(44)
        self.btn_stream_footer.clicked.connect(self._on_stream_toggle)

        self.btn_exit = QPushButton(self.tr("Esci"))
        self.btn_exit.setObjectName("ghost")
        self.btn_exit.setMinimumHeight(44)
        self.btn_exit.clicked.connect(self.close)

        lay.addWidget(self.btn_photo)
        lay.addWidget(self.btn_record)
        lay.addWidget(self.btn_folder)
        lay.addWidget(self.btn_fullscreen)
        lay.addWidget(self.btn_copy)
        lay.addWidget(self.btn_share)
        lay.addWidget(self.btn_reveal)
        lay.addWidget(self.btn_stream_footer)
        lay.addWidget(self.btn_exit)
        return footer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _install_shortcuts(self) -> None:
        from PyQt6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Space"), self, self._on_photo)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._copy_last_media_to_clipboard)
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
        self._zoom = self.settings.get("zoom", 100)
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
        self._audio_enabled = self.settings.get("audio_enabled", False)
        self._background_blur = self.settings.get("background_blur", False)
        self._blur_strength = self.settings.get("blur_strength", 15)
        self._motion_detection = self.settings.get("motion_detection", False)
        self._motion_sensitivity = self.settings.get("motion_sensitivity", 20)
        self._refresh_audio_devices()
        self.chk_mirror.setChecked(self._mirror)

        self.chk_grid.setChecked(self._grid)
        self.chk_pause.setChecked(self._pause_preview)
        self.chk_qr.setChecked(self._qr_enabled)
        self.chk_focus.setChecked(self._focus_assist_enabled)
        self.chk_face.setChecked(self._face_framing_enabled)
        self.chk_audio.setChecked(self._audio_enabled)
        self.chk_blur_bg.setChecked(self._background_blur)
        self.slider_blur["slider"].setValue(self._blur_strength)
        self.chk_motion.setChecked(self._motion_detection)
        self.slider_motion["slider"].setValue(self._motion_sensitivity)
        self.slider_zoom["slider"].setValue(self._zoom)
        self.chk_timelapse.setChecked(self._timelapse_enabled)
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
        self._camera_watch = QTimer(self)
        self._camera_watch.setInterval(_CAMERA_WATCH_INTERVAL_MS)
        self._camera_watch.timeout.connect(self._watch_cameras)
        self._camera_watch.start()
        self.camera.start()
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(int(1000 / max(self._fps, 1)))
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start()

    @staticmethod
    def _camera_devices_initial() -> list:
        from app.camera import enumerate_cameras as _enumerate
        try:
            return list(_enumerate())
        except Exception:
            return []

    def _camera_signature(self) -> list:
        """Device list in a comparable form, used to detect hotplug."""
        from app.camera import enumerate_cameras as _enumerate
        return [(idx, label) for idx, label in _enumerate()]

    def _watch_cameras(self) -> None:
        """Re-check the device list so unplugged and replugged cameras appear.

        The combo box is only rebuilt when the list actually changed, so an
        user selection is never lost while the cameras stay the same.
        """
        try:
            devices = self._camera_signature()
        except Exception as exc:
            logger.debug("Enumerazione camere fallita: %s", exc)
            return
        previous = list(self._last_camera_devices)
        if devices == previous:
            return
        self._last_camera_devices = devices
        current_index = self.combo_camera.currentData()
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()
        for idx, label in devices:
            self.combo_camera.addItem(label, idx)
        if not devices:
            self.combo_camera.addItem("Nessuna webcam rilevata", -1)
        # keep the same camera if it is still there, otherwise take the first
        restore = None
        for row in range(self.combo_camera.count()):
            if self.combo_camera.itemData(row) == current_index:
                restore = row
                break
        if restore is None and devices:
            restore = 0
        if restore is not None:
            self.combo_camera.setCurrentIndex(restore)
        self.combo_camera.blockSignals(False)
        if [d[0] for d in devices] != [d[0] for d in previous]:
            labels = ", ".join(label for _, label in devices) or "nessuna"
            self._show_status(f"Webcam rilevate: {labels}")
            if restore is not None and current_index != devices[restore][0]:
                self._init_camera()

    def _enumerate_cameras(self) -> None:
        from app.camera import enumerate_cameras as _enumerate
        from app.camera import list_video_devices
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()
        devices = _enumerate()
        for idx, label in devices:
            self.combo_camera.addItem(label, idx)
        if not devices:
            nodes = list_video_devices()
            if nodes:
                # La webcam esiste ma non si apre: quasi sempre è occupata da
                # un'altra applicazione, e non va confusa con "assente".
                self.combo_camera.addItem("Webcam occupata da un'altra app", -1)
                self._show_status(
                    "Webcam occupata da un'altra applicazione. Chiudila e "
                    "attendi qualche secondo: il rilevamento riparte da solo.",
                    error=True)
            else:
                self.combo_camera.addItem("Nessuna webcam rilevata", -1)
                self._show_status(self.tr("Nessuna webcam collegata"), error=True)
        self.combo_camera.blockSignals(False)

    def _on_camera_changed(self, index: int) -> None:
        idx = self.combo_camera.currentData()
        if idx is None or idx == -1:
            self._show_status(self.tr("Webcam non disponibile"), error=True)
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

    def _on_zoom_changed(self, value: int) -> None:
        self._zoom = value
        self.settings.set("zoom", value)

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
        self._show_status(self.tr("Regolazioni reset"))

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
        self._show_status(self.tr("QR/Barcode ") + ("attivo" if checked else "disattivato"))

    def _on_focus_changed(self, checked: bool) -> None:
        self._focus_assist_enabled = checked
        self._focus_scores = []
        self.settings.set("focus_assist", checked)
        self._show_status(self.tr("Focus assist ") + ("attivo" if checked else "disattivato"))

    def _on_face_changed(self, checked: bool) -> None:
        self._face_framing_enabled = checked
        self.settings.set("face_framing", checked)
        self._show_status(self.tr("Face framing ") + ("attivo" if checked else "disattivato"))

    def _on_audio_changed(self, checked: bool) -> None:
        self._audio_enabled = checked
        self.settings.set("audio_enabled", checked)
        self._show_status(self.tr("Audio registrazione ") + ("attivo" if checked else "disattivato"))

    def _on_blur_bg_changed(self, checked: bool) -> None:
        self._background_blur = checked
        self.settings.set("background_blur", checked)
        self._show_status(self.tr("Sfoca sfondo ") + ("attivo" if checked else "disattivato"))

    def _on_blur_strength_changed(self, value: int) -> None:
        self._blur_strength = value
        self.settings.set("blur_strength", value)

    def _on_motion_changed(self, checked: bool) -> None:
        self._motion_detection = checked
        self.settings.set("motion_detection", checked)
        if checked:
            self._motion_reference = None
            self._motion_last_detected = time.time()
            self._show_status(self.tr("Rilevamento movimento attivo"))
        else:
            self._motion_reference = None
            if self._motion_inactive_timer is not None:
                self._motion_inactive_timer.stop()
                self._motion_inactive_timer = None
            self._show_status(self.tr("Rilevamento movimento disattivato"))

    def _on_motion_sensitivity_changed(self, value: int) -> None:
        self._motion_sensitivity = value
        self.settings.set("motion_sensitivity", value)

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
        self._show_status(self.tr("Time-lapse ") + ("avviato" if checked else "fermo"))

    def _on_timelapse_interval_changed(self, value: int) -> None:
        self._timelapse_interval = value
        self.settings.set("timelapse_interval", value)
        if self._timelapse_timer is not None:
            self._timelapse_timer.setInterval(value * 1000)

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
        try:
            self._process_and_paint(frame)
        except Exception as exc:
            # PyQt aborts the process on an unhandled exception raised inside a
            # slot, so a single bad frame must never escape this method.
            self._preview_failures += 1
            logger.error("Errore elaborazione anteprima (%d): %s",
                         self._preview_failures, exc, exc_info=True)
            if self._preview_failures >= _PREVIEW_FAILURE_LIMIT:
                self._preview_timer.stop()
                self._show_status(
                    "Anteprima fermata dopo errori ripetuti. Controlla i log.",
                    error=True)

    def _process_and_paint(self, frame: np.ndarray) -> None:
        processed = self._apply_adjustments(self._apply_filter(frame.copy()))
        processed = self._apply_format(processed)
        processed = self._apply_zoom(processed)
        if self._background_blur:
            processed = self._apply_background_blur(processed)
        if self._mirror:
            processed = cv2.flip(processed, 1)
        if self._grid:
            processed = self._draw_grid_on_frame(processed)
        if getattr(self, "_face_framing_enabled", False):
            processed = self._apply_face_framing(processed)
        self._processed_frame = processed
        if getattr(self, "_motion_detection", False):
            if self._detect_motion(processed):
                self._handle_motion_detected()
            self._check_inactivity()
        if (self._recording and self.recorder.is_recording()
                and getattr(self, "camera", None) is not None):
            frame_number = self.camera.frame_count()
            if frame_number != self._last_recorded_frame:
                # Solo frame nuovi: il timer dell'anteprima può scattare più
                # spesso di quanto la webcam produca, e riscrivere lo stesso
                # frame farebbe avanzare il video più veloce del reale.
                self._last_recorded_frame = frame_number
                rec_frame = processed.copy()
                if rec_frame.ndim == 2:
                    rec_frame = cv2.cvtColor(rec_frame, cv2.COLOR_GRAY2BGR)
                if rec_frame.shape[2] == 4:
                    rec_frame = cv2.cvtColor(rec_frame, cv2.COLOR_BGRA2BGR)
                if self._recording_frame_size is not None:
                    th, tw = self._recording_frame_size
                    h, w = rec_frame.shape[:2]
                    if (w, h) != (tw, th):
                        rec_frame = cv2.resize(rec_frame, (tw, th))
                self.recorder.write(rec_frame)
                if self._clip_seconds > 0 and self.recorder.elapsed() >= self._clip_seconds:
                    self._stop_recording()
                    self._show_status(
                        f"Registrazione fermata dopo {self._clip_seconds}s")

        if self._streaming:
            stream_frame = processed.copy()
            if stream_frame.ndim == 2:
                stream_frame = cv2.cvtColor(stream_frame, cv2.COLOR_GRAY2BGR)
            if stream_frame.ndim == 3 and stream_frame.shape[2] == 4:
                stream_frame = cv2.cvtColor(stream_frame, cv2.COLOR_BGRA2BGR)
            if stream_frame.shape[:2] != (self._stream_height, self._stream_width):
                stream_frame = cv2.resize(stream_frame, (self._stream_width, self._stream_height))
            self._stream_frame(stream_frame)
        if getattr(self, "_qr_enabled", False):
            self._scan_qr(processed)
            self.lbl_qr.setText("Scansione…" if not getattr(self, "_qr_result", None) else self._qr_result)
            self.lbl_qr.show()
            self.lbl_qr.raise_()
        else:
            self.lbl_qr.hide()
        if getattr(self, "_focus_assist_enabled", False):
            score = self._compute_focus_score(processed)
            # Il punteggio dipende dalla scena e dalla risoluzione: confrontarlo
            # con una soglia fissa dava sempre rosso. Si misura quindi contro il
            # meglio ottenuto negli ultimi secondi, così verde vuol dire
            # "sei a fuoco" su qualsiasi webcam.
            self._focus_scores.append(score)
            if len(self._focus_scores) > _FOCUS_HISTORY:
                self._focus_scores.pop(0)
            best = max(self._focus_scores) or 1.0
            ratio = score / best
            if ratio >= 0.9:
                color = "#5cd962"
            elif ratio >= 0.6:
                color = "#f59e0b"
            else:
                color = "#ef4444"
            self.lbl_focus.setStyleSheet(
                f"border-radius: 12px; border: 3px solid {color}; background-color: {color};"
            )
            self.lbl_focus.show()
            self.lbl_focus.raise_()
            self.lbl_status.setText(
                f"Messa a fuoco: {score:.0f} (migliore {best:.0f})")
        else:
            self.lbl_focus.hide()
        rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

        h, w = rgb.shape[:2]
        img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        pix = QPixmap.fromImage(img)
        scaled = pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(scaled)
        self._position_overlays()
        self._update_fps_counter()

    def _update_fps_counter(self) -> None:
        now = time.time()
        if self._fps_last_time is not None:
            self._fps_counter += 1
            elapsed = now - self._fps_last_time
            if elapsed >= 1.0:
                self._actual_fps = self._fps_counter / elapsed if elapsed > 0 else 0.0
                if self._fps_counter > 0:
                    self.lbl_fps.setText(f"{self._actual_fps:.1f} FPS")
                self._fps_counter = 0
                self._fps_last_time = now
        else:
            self._fps_last_time = now

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

    def _apply_background_blur(self, frame: np.ndarray) -> np.ndarray:
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
            lower_skin = np.array([0, 80, 130], dtype=np.uint8)
            upper_skin = np.array([255, 120, 170], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.GaussianBlur(mask.astype(float), (21, 21), 0)
            mask_3ch = np.dstack([mask, mask, mask]) / 255.0
            blurred = cv2.GaussianBlur(frame, (0, 0), self._blur_strength)
            return (frame * mask_3ch + blurred * (1 - mask_3ch)).astype(np.uint8)
        except Exception as exc:
            logger.debug("Errore applicazione blur sfondo: %s", exc)
            return frame

    def _apply_zoom(self, frame: np.ndarray) -> np.ndarray:
        if self._zoom <= 100:
            return frame
        try:
            h, w = frame.shape[:2]
            zoom_factor = self._zoom / 100.0
            new_w = int(w / zoom_factor)
            new_h = int(h / zoom_factor)
            x = (w - new_w) // 2
            y = (h - new_h) // 2
            cropped = frame[y : y + new_h, x : x + new_w]
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        except Exception as exc:
            logger.debug("Errore zoom: %s", exc)
            return frame

    # ------------------------------------------------------------------
    # Motion detection
    # ------------------------------------------------------------------
    def _detect_motion(self, frame: np.ndarray) -> bool:
        try:
            small = cv2.resize(frame, (320, 240))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            if self._motion_reference is None:
                self._motion_reference = gray.copy()
                return False
            diff = cv2.absdiff(gray, self._motion_reference)
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=2)
            changed = int(np.count_nonzero(thresh)) / (thresh.shape[0] * thresh.shape[1]) * 100
            self._motion_reference = gray.copy()
            return changed > self._motion_sensitivity
        except Exception as exc:
            logger.debug("Errore rilevamento movimento: %s", exc)
            return False

    def _handle_motion_detected(self) -> None:
        self._motion_last_detected = time.time()
        if not self._recording and not self._streaming:
            self._start_recording()

    def _check_inactivity(self) -> None:
        if not self._motion_detection:
            return
        if not self._recording:
            return
        if self._motion_last_detected == 0.0:
            # Recording started manually (not by motion): reset the timer
            self._motion_last_detected = time.time()
            return
        elapsed = time.time() - self._motion_last_detected
        if elapsed >= 10.0:
            self._stop_recording()
            self._show_status(self.tr("Registrazione ferma: nessun movimento"))

    # ------------------------------------------------------------------
    # Preset manager
    # ------------------------------------------------------------------
    def _refresh_presets(self) -> None:
        self._presets = self.settings.get_presets()
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItem(self.tr("Predefinito"), "<default>")
        for name in sorted(self._presets.keys()):
            self.combo_preset.addItem(name, name)
        self.combo_preset.blockSignals(False)

    def _current_settings_snapshot(self) -> dict:
        burst_map = {0: 1, 1: 3, 2: 5, 3: 10}
        return {
            "filter": self.combo_filter.currentText(),
            "format": self.combo_format.currentText(),
            "resolution": self.combo_resolution.currentText(),
            "fps": self.combo_fps.value(),
            "brightness": self.slider_brightness["slider"].value(),
            "contrast": self.slider_contrast["slider"].value(),
            "saturation": self.slider_saturation["slider"].value(),
            "mirror": self.chk_mirror.isChecked(),
            "grid": self.chk_grid.isChecked(),
            "blur_strength": self.slider_blur["slider"].value(),
            "burst_count": burst_map.get(self.combo_burst.currentIndex(), 1),
            "audio_enabled": self.chk_audio.isChecked(),
            "background_blur": self.chk_blur_bg.isChecked(),
        }

    def _save_preset(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, self.tr("Salva preset"), self.tr("Nome preset:"))
        if not ok or not name.strip():
            return
        name = name.strip()
        self.settings.save_preset(name, self._current_settings_snapshot())
        self._refresh_presets()
        idx = self.combo_preset.findData(name)
        if idx >= 0:
            self.combo_preset.setCurrentIndex(idx)
        self._show_status(f"Preset salvato: {name}")

    def _load_preset(self) -> None:
        key = self.combo_preset.currentData()
        if key == "<default>":
            self._show_status(self.tr("Preset predefinito caricato"))
            return
        presets = self._presets
        if key not in presets:
            return
        values = presets[key]
        self.combo_filter.setCurrentText(values.get("filter", "Normale"))
        self._current_filter = self.combo_filter.currentText()
        self.combo_format.setCurrentText(values.get("format", "16:9"))
        self._current_format = self.combo_format.currentText()
        self.combo_resolution.setCurrentText(values.get("resolution", "640x480"))
        self.combo_fps.setValue(values.get("fps", 30))
        self.slider_brightness["slider"].setValue(values.get("brightness", 0))
        self.slider_contrast["slider"].setValue(values.get("contrast", 0))
        self.slider_saturation["slider"].setValue(values.get("saturation", 0))
        self.chk_mirror.setChecked(values.get("mirror", False))
        self.chk_grid.setChecked(values.get("grid", False))
        self.slider_blur["slider"].setValue(values.get("blur_strength", 15))
        self.chk_audio.setChecked(values.get("audio_enabled", False))
        self.chk_blur_bg.setChecked(values.get("background_blur", False))
        burst_map = {1: 0, 3: 1, 5: 2, 10: 3}
        self.combo_burst.setCurrentIndex(burst_map.get(values.get("burst_count", 1), 0))
        wh = RESOLUTIONS.get(self.combo_resolution.currentText(), (640, 480))
        self._width, self._height = wh
        if self.camera is not None:
            self.camera.set_resolution(self._width, self._height)
            self.camera.set_fps(self.combo_fps.value())
        self._update_header_info()
        self._show_status(f"Preset caricato: {key}")

    def _delete_preset(self) -> None:
        key = self.combo_preset.currentData()
        if key == "<default>":
            self._show_status(self.tr("Impossibile eliminare il preset predefinito"), error=True)
            return
        if key not in self._presets:
            self._show_status(self.tr("Nessun preset da eliminare"), error=True)
            return
        self.settings.delete_preset(key)
        self._refresh_presets()
        self._show_status(f"Preset eliminato: {key}")

    def _position_overlays(self) -> None:
        if hasattr(self, "lbl_countdown"):
            self.lbl_countdown.setFixedSize(self.preview.width() // 2, self.preview.height() // 3)
            self.lbl_countdown.move(
                (self.preview.width() - self.lbl_countdown.width()) // 2,
                (self.preview.height() - self.lbl_countdown.height()) // 2,
            )
        if hasattr(self, "lbl_rec"):
            self.lbl_rec.adjustSize()
            self.lbl_rec.move(12, self.preview.height() - self.lbl_rec.height() - 12)
            self.lbl_rec.raise_()
        if hasattr(self, "lbl_level"):
            self.lbl_level.adjustSize()
            self.lbl_level.move(12, self.preview.height() - self.lbl_rec.height() - self.lbl_level.height() - 20)
            self.lbl_level.raise_()
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
    def _share_last_media(self) -> None:
        """Share the last photo or recording.

        Photo: copied to the clipboard, so it can be pasted straight into
        Telegram, Discord or anything else. Video: the clipboard cannot hold a
        file, so the folder is opened and the user drags it. No web page is
        opened pretending to share, and nothing is uploaded anywhere: the user
        keeps control of what leaves the machine.
        """
        path = self._last_media_path()
        if path is None or not path.exists():
            self._show_status(self.tr("Nessun file recente da condividere"), error=True)
            return
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            image = QImage(str(path))
            if not image.isNull():
                QGuiApplication.clipboard().setImage(image)
                self._show_status(
                    f"Foto copiata negli appunti: {path.name} "
                    "(incollala in Telegram, Discord o dove vuoi)")
                return
            self._show_status(f"Impossibile leggere {path.name}", error=True)
            return
        self._reveal_last_media()
        self._show_status(
            f"{path.name} è un video: trascinalo dalla cartella aperta")

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
            self._show_status(self.tr("Nessun frame disponibile per la foto"), error=True)
            return
        self._flash_effect()
        count = self._burst_count
        if count <= 1:
            path = Storage.save_photo(frame, quality=self._photo_quality)
            if path is None:
                self._show_status(self.tr("Errore salvataggio foto"), error=True)
                return
            self._show_status(f"Foto salvata: {path}")
            self.status.showMessage(f"Foto salvata: {path}", 5000)
            self._add_recent_media(path)
            self._last_media = path
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
            return
        try:
            self._start_recording()
        except _RecordingCancelled:
            self._show_status(self.tr("Registrazione annullata: spazio insufficiente"))

    def _free_space_warning(self) -> Optional[str]:
        """Space needed is unknown, so warn conservatively.

        A recording at 30 fps 640x480 is roughly 2 MB per minute, but the
        chosen resolution can be much larger, so a fixed margin is used
        instead of an estimate that could be wrong in either direction.
        """
        target = Storage.recordings_dir()
        try:
            free = shutil.disk_usage(target).free
        except OSError as exc:
            logger.debug("Impossibile leggere lo spazio libero: %s", exc)
            return None
        margin = 64 * 1024 * 1024
        if free < margin:
            return (f"Spazio libero su {target}: {free / 1024 / 1024:.0f} MB. "
                    f"La registrazione potrebbe interrompersi prima della fine.")
        return None

    def _check_free_space_before_recording(self) -> None:
        warning = self._free_space_warning()
        if warning is None:
            return
        answer = QMessageBox.warning(
            self,
            self.tr("Spazio quasi esaurito"),
            warning + "\n\nRegistrare comunque?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            raise _RecordingCancelled()

    def _start_recording(self) -> None:
        frame = self._processed_frame if self._processed_frame is not None else self._current_frame
        if frame is None:
            self._show_status(self.tr("Nessun frame disponibile per la registrazione"), error=True)
            return
        self._check_free_space_before_recording()
        if self._audio_enabled and shutil.which("ffmpeg") is None:
            QMessageBox.critical(
                self,
                self.tr("ffmpeg non trovato"),
                "La registrazione con audio richiede ffmpeg, che non è installato.\n\n"
                "Installa il pacchetto ffmpeg (sudo apt install ffmpeg) oppure "
                "disattiva l'audio per registrare solo il video.",
            )
            self._show_status(self.tr("Registrazione con audio annullata: ffmpeg mancante"), error=True)
            return
        self._recording_frame_size = frame.shape[:2][::-1]
        path = Storage.recordings_dir() / Storage.video_filename()
        measured = self.camera.measured_fps() if self.camera is not None else None
        record_fps = int(round(measured)) if measured else self._fps
        logger.info("Registrazione: fps richiesti %d, misurati %s, uso %d",
                    self._fps, measured, record_fps)
        _audio_device = self.settings.get("audio_device") or None
        ok = self.recorder.start(frame, path, fps=record_fps, audio=self._audio_enabled, audio_device=_audio_device)
        if not ok:
            self._show_status(self.tr("Impossibile avviare la registrazione: codec non disponibile"), error=True)
            return
        self._recording = True
        self._last_recorded_frame = -1
        self.btn_record.setText(self.tr("Ferma"))
        self.btn_record.setObjectName("stop")
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.combo_resolution.setEnabled(False)
        self.combo_format.setEnabled(False)
        self.lbl_rec.show()
        self.lbl_rec.raise_()
        self.lbl_rec.setText(self.tr("REC"))
        if self._audio_enabled:
            self._update_level_meter()
        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(500)
        self._rec_timer.timeout.connect(self._update_rec_time)
        self._rec_timer.start()
        self._show_status(self.tr("Registrazione avviata"))

    def _stop_recording(self) -> None:
        path = self.recorder.stop()
        self._recording = False
        self.btn_record.setText(self.tr("Registra"))
        self.btn_record.setObjectName("record")
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.combo_resolution.setEnabled(True)
        self.combo_format.setEnabled(True)
        self.lbl_rec.hide()
        self.lbl_level.hide()
        if path is not None:
            self._last_media = path
            self._add_recent_media(path)
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
            self._show_status(self.tr("Registrazione interrotta senza salvataggio"), error=True)

    def _update_rec_time(self) -> None:
        elapsed = self.recorder.elapsed()
        m, s = divmod(int(elapsed), 60)
        self.lbl_rec.setText(f"REC {m:02d}:{s:02d}")
        self._update_level_meter()

    def _update_level_meter(self) -> None:
        """Draw the audio level while a recording with audio is running."""
        if not getattr(self, "_recording", False) or not self._audio_enabled:
            if getattr(self, "lbl_level", None) is not None:
                self.lbl_level.hide()
            return
        levels = self.recorder.audio_level()
        peak = levels.get("peak")
        if peak is None:
            self.lbl_level.setText(self.tr("Livello audio —"))
            self.lbl_level.setStyleSheet(
                "background-color: rgba(17, 19, 25, 0.85); color: #9aa0ac;"
                "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 10px;")
            self.lbl_level.show()
            return
        # barra fatta di blocchi: 12 segmenti fra -60 e 0 dBFS
        steps = 12
        value = max(-60.0, min(0.0, peak))
        filled = int(round((value + 60.0) / 60.0 * steps))
        bar = "█" * filled + "░" * (steps - filled)
        if peak >= -1.0:
            colour = "#ef4444"      # in saturazione
            hint = "troppo alto"
        elif peak <= -45.0:
            colour = "#f59e0b"      # quasi silenzio
            hint = "troppo basso"
        else:
            colour = "#5cd962"
            hint = ""
        self.lbl_level.setText(f"{bar} {peak:5.1f} dBFS {hint}".rstrip())
        self.lbl_level.setStyleSheet(
            f"background-color: rgba(17, 19, 25, 0.85); color: {colour};"
            "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 10px;")
        self.lbl_level.show()

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
                if path.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv"):
                    lbl.setPixmap(QPixmap())
                    lbl.setText(self.tr("🎬"))
                else:
                    pix = QPixmap(str(path))
                    if not pix.isNull():
                        pix = pix.scaled(72, 54, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        rect = pix.rect()
                        rect.moveCenter(QPoint(36, 27))
                        pix = pix.copy(rect)
                        lbl.setPixmap(pix)
                    else:
                        lbl.setPixmap(QPixmap())
                        lbl.setText(self.tr("🖼"))
                lbl.setToolTip(str(path))
                lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                lbl.mousePressEvent = lambda ev, p=path: self._open_recent(p)
            else:
                lbl.clear()
                lbl.setToolTip(self.tr(""))

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
            self.btn_fullscreen.setText(self.tr("Esci da schermo intero"))
        else:
            self.showNormal()
            self.btn_fullscreen.setText(self.tr("Schermo intero"))
        # Reposition overlays (REC/labels) for the new preview size
        QTimer.singleShot(100, self._adjust_overlays)

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
                    "Icon=mintcam\n"
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

    def _on_language_changed(self, index: int) -> None:
        """Switch language: install the translator and rebuild the window."""
        code = self.combo_language.itemData(index)
        if not code or code == self._language:
            return
        self._language = code
        self.settings.set("language", code)
        from app.i18n import install as _install_language
        _install_language(QApplication.instance(), code)
        # _init_ui ricostruisce la finestra: ogni etichetta passa da self.tr(),
        # quindi con il nuovo traduttore installato prende la lingua nuova.
        self._init_ui()
        self._show_status(
            self.tr("Lingua cambiata in {name}").format(
                name=self.combo_language.currentText()))

    def _on_autostart_changed(self, checked: bool) -> None:
        self.settings.set("autostart", checked)
        self._set_autostart(checked)
        self._show_status(self.tr("Avvio automatico ") + ("abilitato" if checked else "disabilitato"))

    def _refresh_audio_devices(self) -> None:
        """Populate the audio device combo from the system, keeping selection."""
        from app.audio import list_audio_sources, has_pulseaudio
        self.combo_audio_device.blockSignals(True)
        self.combo_audio_device.clear()
        self._audio_devices: list[tuple[str, str]] = []
        if has_pulseaudio():
            self._audio_devices = list_audio_sources()
            if self._audio_devices:
                for _name, _label in self._audio_devices:
                    self.combo_audio_device.addItem(_label, _name)
            else:
                self.combo_audio_device.addItem(
                    self.tr("Nessun dispositivo disponibile"), "")
        else:
            self.combo_audio_device.addItem(self.tr("Predefinito (ALSA)"), "default")
        self.combo_audio_device.blockSignals(False)

        _saved = self.settings.get("audio_device")
        if _saved:
            _idx = self.combo_audio_device.findData(_saved)
            if _idx >= 0:
                self.combo_audio_device.setCurrentIndex(_idx)

    def _on_audio_device_changed(self, index: int) -> None:
        device = self.combo_audio_device.itemData(index) or ""
        self.settings.set("audio_device", device)
        self._show_status(self.tr("Dispositivo audio selezionato"))

    def _on_check_update(self) -> None:
        """Check GitHub releases for a newer version."""
        import json as _json
        import urllib.request as _urlrequest
        self._update_checking = True
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText(self.tr("Ricerca..."))

        def _check() -> None:
            latest = None
            error = False
            try:
                req = _urlrequest.Request(
                    "https://api.github.com/repos/jeaders/MintCam/releases/latest",
                    headers={"User-Agent": "MintCam"},
                )
                with _urlrequest.urlopen(req, timeout=10) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                latest = data.get("tag_name", "").lstrip("v")
            except Exception as exc:
                logger.warning("Update check failed: %s", exc)
                error = True

            def _finish() -> None:
                self._update_checking = False
                self.btn_check_update.setEnabled(True)
                self.btn_check_update.setText(self.tr("Cerca aggiornamenti"))
                if error:
                    self._show_status(self.tr("Impossibile verificare gli aggiornamenti"), error=True)
                elif latest and self._newer_version_available(latest):
                    self._show_status(self.tr("Aggiornamento disponibile: v") + latest)
                    self._show_update_dialog(latest)
                else:
                    self._show_status(self.tr("Sei aggiornato alla v") + __version__)

            QTimer.singleShot(0, _finish)

        threading.Thread(target=_check, daemon=True).start()

    def _newer_version_available(self, latest: str) -> bool:
        """Returns True if latest is newer than current __version__."""
        try:
            from packaging.version import Version
            return Version(latest) > Version(__version__)
        except Exception:
            # Simple string fallback
            return latest != __version__

    def _show_update_dialog(self, latest: str) -> None:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("Aggiornamento disponibile"))
        msg.setText(
            self.tr("MintCam v{latest} è disponibile (ora su v{current}).\n\n"
                    "Visita GitHub per scaricare l'aggiornamento.").format(
                latest=latest, current=__version__))
        msg.setIcon(QMessageBox.Icon.Information)
        btn = msg.addButton(self.tr("Apri GitHub"), QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.ButtonRole.AcceptRole:
            import webbrowser
            webbrowser.open("https://github.com/jeaders/MintCam/releases/latest")
        self._show_status(self.tr("Verifica aggiornamenti completata"))

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
        self.chk_audio.toggled.connect(self._on_audio_changed)
        self.chk_blur_bg.toggled.connect(self._on_blur_bg_changed)
        self.slider_blur["slider"].valueChanged.connect(self._on_blur_strength_changed)
        self.chk_motion.toggled.connect(self._on_motion_changed)
        self.slider_motion["slider"].valueChanged.connect(self._on_motion_sensitivity_changed)
        self.chk_timelapse.toggled.connect(self._on_timelapse_changed)
        self.spin_timelapse_interval.valueChanged.connect(self._on_timelapse_interval_changed)
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
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        logger.debug("Focus score: %.1f", score)
        return score

    # ------------------------------------------------------------------
    # Face auto-framing
    # ------------------------------------------------------------------
    def _find_face_cascade(self) -> Optional[Path]:
        """Locate the Haar cascade used by the face auto-framing.

        opencv-python from pip exposes it through cv2.data; on Debian and
        Ubuntu the xml files ship in the separate opencv-data package, so both
        locations are tried. The result is cached in self._face_cascade.
        """
        cached = getattr(self, "_face_cascade", None)
        if cached is not None:
            return cached
        candidates = []
        data = getattr(cv2, "data", None)
        if data is not None and getattr(data, "haarcascades", None):
            candidates.append(Path(str(data.haarcascades)) / "haarcascade_frontalface_default.xml")
        candidates += [
            Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"),
            Path("/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml"),
            Path("/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"),
        ]
        for path in candidates:
            if path.is_file():
                self._face_cascade = path
                return path
        self._face_cascade = None
        return None

    def _apply_face_framing(self, frame: np.ndarray) -> np.ndarray:
        """Crop the preview around the largest detected face (digital zoom)."""
        if not getattr(self, "_face_framing_enabled", False):
            return frame
        try:
            cascade_path = self._find_face_cascade()
            if cascade_path is None:
                self._face_failures += 1
                logger.debug("Cascade volti non trovata (%d/%d)",
                             self._face_failures, _FACE_FAILURE_LIMIT)
                if self._face_failures >= _FACE_FAILURE_LIMIT:
                    self._face_framing_enabled = False
                    if getattr(self, "chk_face", None) is not None:
                        self.chk_face.setChecked(False)
                    self._show_status(
                        "Inquadratura volti disattivata: dati mancanti. "
                        "Installa il pacchetto opencv-data.", error=True)
                return frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cascade = self._face_classifier()
            if cascade is None or cascade.empty():
                self._face_failures += 1
                logger.debug("Cascade non caricabile (%d/%d)",
                             self._face_failures, _FACE_FAILURE_LIMIT)
                if self._face_failures >= _FACE_FAILURE_LIMIT:
                    self._face_framing_enabled = False
                    if getattr(self, "chk_face", None) is not None:
                        self.chk_face.setChecked(False)
                    self._show_status(
                        "Inquadratura volto disattivata: impossibile caricare "
                        "i dati del riconoscimento.", error=True)
                return frame
            # Dimensione minima relativa al frame: un valore fisso in pixel
            # perde i volti lontani sulle risoluzioni basse, ed è il motivo per
            # cui l'inquadratura sembrava non funzionare.
            min_side = min(frame.shape[:2])
            min_size = (max(24, int(min_side * 0.07)),) * 2
            faces = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=min_size)
            logger.debug("Face framing: volti rilevati=%d", len(faces))
            self._face_failures = 0
            if len(faces) == 0:
                if self._face_seen:
                    self._face_seen = False
                    self._show_status(self.tr("Inquadratura volto: nessun volto nel quadro"))
                return frame
            if not self._face_seen:
                self._face_seen = True
                self._show_status(self.tr("Inquadratura volto: volto rilevato"))
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            cx, cy = x + w // 2, y + h // 2
            fh, fw = frame.shape[:2]
            new_w = int(fw / 1.6)
            new_h = int(fh / 1.6)
            x1 = max(0, min(fw - new_w, cx - new_w // 2))
            y1 = max(0, min(fh - new_h, cy - new_h // 2))
            return frame[y1 : y1 + new_h, x1 : x1 + new_w]
        except Exception as exc:
            self._face_failures += 1
            logger.debug("Errore face framing (%d/%d): %s",
                         self._face_failures, _FACE_FAILURE_LIMIT, exc)
            if self._face_failures >= _FACE_FAILURE_LIMIT:
                self._face_framing_enabled = False
                if getattr(self, "chk_face", None) is not None:
                    self.chk_face.setChecked(False)
                self._show_status(self.tr("Inquadratura volti disattivata dopo errori ripetuti"),
                                  error=True)
            return frame

    def _face_classifier(self):
        """Build the cascade classifier once and reuse it.

        Loading the xml on every frame costs milliseconds and is the main
        reason the feature felt broken under load.
        """
        classifier = getattr(self, "_face_classifier_obj", None)
        if classifier is not None:
            return classifier
        path = self._find_face_cascade()
        if path is None:
            return None
        try:
            self._face_classifier_obj = cv2.CascadeClassifier(str(path))
            return self._face_classifier_obj
        except Exception as exc:
            logger.debug("Impossibile caricare il cascade: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Time-lapse
    # ------------------------------------------------------------------
    def _capture_timelapse_frame(self) -> None:
        frame = self._processed_frame if self._processed_frame is not None else self._current_frame
        if frame is None:
            logger.debug("Time-lapse: frame non disponibile")
            return
        self._timelapse_frames.append(frame.copy())
        logger.debug("Time-lapse: frame catturato, totale=%d", len(self._timelapse_frames))
        self._show_status(f"Time-lapse: {len(self._timelapse_frames)} frame")

    def _assemble_timelapse(self) -> None:
        if len(self._timelapse_frames) < 2:
            logger.debug("Time-lapse: frame insufficienti (%d)", len(self._timelapse_frames))
            return
        path = Storage.recordings_dir() / f"timelapse_{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4"
        h, w = self._timelapse_frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, 30, (w, h))
        if not writer.isOpened():
            logger.error("Impossibile creare il video time-lapse: codec non supportato")
            self._show_status(self.tr("Time-lapse: codec non supportato"), error=True)
            self._timelapse_frames = []
            return
        for frame in self._timelapse_frames:
            if frame.shape[:2] != (h, w):
                frame = cv2.resize(frame, (w, h))
            if frame.ndim != 3 or frame.shape[2] != 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            writer.write(frame)
        writer.release()
        logger.debug("Time-lapse: video salvato in %s", path)
        self._show_status(f"Time-lapse salvato: {path}")
        self.status.showMessage(f"Time-lapse salvato: {path}", 5000)
        self._add_recent_media(path)
        self._timelapse_frames = []

    # ------------------------------------------------------------------
    # Live streaming (RTMP)
    # ------------------------------------------------------------------
    def _on_stream_toggle(self) -> None:
        if self._streaming:
            self._stop_streaming()
        else:
            self._start_streaming()

    def _start_streaming(self) -> None:
        url = self.txt_stream_url.text().strip()
        if not url:
            self._show_status(self.tr("Inserisci un URL di stream RTMP"), error=True)
            return
        if not url.startswith("rtmp://") and not url.startswith("rtmps://"):
            self._show_status(self.tr("URL RTMP non valido"), error=True)
            return
        self._stream_url = url
        self._stream_width = self._width
        self._stream_height = self._height
        self._stream_fps = self._fps

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self._stream_width}x{self._stream_height}",
            "-r", str(self._stream_fps),
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-f", "flv",
            url,
        ]
        try:
            self._stream_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self._show_status(self.tr("ffmpeg non trovato: installa ffmpeg"), error=True)
            return
        except Exception as exc:
            self._show_status(f"Errore stream: {exc}", error=True)
            return

        self._streaming = True
        self._stream_frame_count = 0
        self.btn_stream.setText(self.tr("Ferma stream"))
        self.btn_stream.setObjectName("stop")
        self.btn_stream.style().unpolish(self.btn_stream)
        self.btn_stream.style().polish(self.btn_stream)
        self.combo_resolution.setEnabled(False)
        self.lbl_rec.show()
        self.lbl_rec.raise_()
        self.lbl_rec.setText(self.tr("● STREAM"))
        self._show_status(f"Stream avviato: {url}")

    def _stop_streaming(self) -> None:
        if self._stream_process is not None:
            try:
                if self._stream_process.stdin is not None:
                    self._stream_process.stdin.close()
            except Exception:
                pass
            try:
                self._stream_process.terminate()
                self._stream_process.wait(timeout=5)
            except Exception:
                try:
                    self._stream_process.kill()
                except Exception:
                    pass
            self._stream_process = None
        self._streaming = False
        self._stream_frame_count = 0
        self.btn_stream.setText(self.tr("Avvia streaming"))
        self.btn_stream.setObjectName("ghost")
        self.btn_stream.style().unpolish(self.btn_stream)
        self.btn_stream.style().polish(self.btn_stream)
        self.combo_resolution.setEnabled(True)
        if not self._recording:
            self.lbl_rec.hide()
        self._show_status(self.tr("Stream fermato"))

    def _stream_frame(self, frame: np.ndarray) -> None:
        if not self._streaming or self._stream_process is None:
            return
        if self._stream_process.stdin is None:
            return
        with self._stream_lock:
            if self._stream_process is None or self._stream_process.stdin is None:
                return
            try:
                data = frame.tobytes()
                self._stream_process.stdin.write(data)
                self._stream_process.stdin.flush()
                self._stream_frame_count += 1
            except (BrokenPipeError, OSError):
                self._streaming = False
                self.btn_stream.setText(self.tr("Avvia streaming"))
                if getattr(self, "btn_stream_footer", None) is not None:
                    self.btn_stream_footer.setText(self.tr("Avvia streaming"))
                self.btn_stream.setObjectName("ghost")
                self.btn_stream.style().unpolish(self.btn_stream)
                self.btn_stream.style().polish(self.btn_stream)
                self.combo_resolution.setEnabled(True)
                if not self._recording:
                    self.lbl_rec.hide()
                self._stream_process = None
                self._show_status(self.tr("Stream interrotto (connessione chiusa)"), error=True)

    # ------------------------------------------------------------------
    # Social sharing
    # ------------------------------------------------------------------
    def _latest_media_path(self) -> Optional[Path]:
        if self._recent_media:
            return self._recent_media[0]
        for folder in (Storage.recordings_dir(), Storage.photos_dir()):
            if folder.exists():
                files = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if files:
                    return files[0]
        return None

    # ------------------------------------------------------------------
    # Clipboard and file manager
    # ------------------------------------------------------------------
    def _last_media_path(self) -> Optional[Path]:
        """The file the user last produced, used by copy and reveal."""
        return getattr(self, "_last_media", None)

    def _copy_last_media_to_clipboard(self) -> None:
        """Copy the last photo to the system clipboard.

        Only images can go to the clipboard, so a video is not copied: the
        user is told and the folder is opened instead, which is what they
        need anyway.
        """
        path = self._last_media_path()
        if path is None or not path.exists():
            self._show_status(self.tr("Nessun file recente da copiare"), error=True)
            return
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
            self._show_status(
                f"{path.name} è un video: apro la cartella per trascinarlo",
                error=False)
            self._reveal_last_media()
            return
        image = QImage(str(path))
        if image.isNull():
            self._show_status(f"Impossibile leggere {path.name}", error=True)
            return
        QGuiApplication.clipboard().setImage(image)
        self._show_status(f"Foto copiata negli appunti: {path.name}")

    def _reveal_last_media(self) -> None:
        """Open the folder containing the last produced file."""
        path = self._last_media_path()
        if path is None or not path.exists():
            self._show_status(self.tr("Nessun file recente da mostrare"), error=True)
            return
        folder = path.parent
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if not opened:
            self._show_status(f"Impossibile aprire {folder}", error=True)
            return
        self._show_status(f"Aperta la cartella di {path.name}")

    def closeEvent(self, event) -> None:  # type: ignore[override]

        if self._fullscreen:
            self._toggle_fullscreen()
        if self._streaming:
            self._stop_streaming()
        if self._recording:
            self._stop_recording()
        if self._motion_inactive_timer is not None:
            self._motion_inactive_timer.stop()
            self._motion_inactive_timer.deleteLater()
            self._motion_inactive_timer = None
        if self.camera is not None:
            self.camera.stop()
            self.camera = None
        if hasattr(self, "_preview_timer") and self._preview_timer is not None:
            self._preview_timer.stop()
        event.accept()
