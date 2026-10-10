from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Mint green palette — inspired by Linux Mint branding
MINT = "#3eb34a"
MINT_LIGHT = "#5cd962"
BG_0 = "#0f1115"
BG_1 = "#16191f"
BG_2 = "#1e222b"
BG_3 = "#252a35"
BG_4 = "#2c333f"
TEXT_1 = "#e6e9ef"
TEXT_2 = "#9aa0ac"
TEXT_3 = "#6b7280"
ACCENT_RED = "#ef4444"
ACCENT_ORANGE = "#f59e0b"
ACCENT_BLUE = "#60a5fa"

CARD_QSS = """
QGroupBox {
    background-color: #16191f;
    border: 1px solid #252a35;
    border-radius: 12px;
    margin-top: 14px;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 12px;
    color: #5cd962;
    font-weight: 700;
}
"""


def apply_dark_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG_1))
    palette.setColor(QPalette.WindowText, QColor(TEXT_1))
    palette.setColor(QPalette.Base, QColor(BG_2))
    palette.setColor(QPalette.AlternateBase, QColor(BG_1))
    palette.setColor(QPalette.ToolTipBase, QColor(BG_3))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT_1))
    palette.setColor(QPalette.Text, QColor(TEXT_1))
    palette.setColor(QPalette.Button, QColor(BG_3))
    palette.setColor(QPalette.ButtonText, QColor(TEXT_1))
    palette.setColor(QPalette.BrightText, QColor(ACCENT_RED))
    palette.setColor(QPalette.Link, QColor(ACCENT_BLUE))
    palette.setColor(QPalette.Highlight, QColor(MINT))
    palette.setColor(QPalette.HighlightedText, QColor(BG_0))
    app.setPalette(palette)
    app.setStyleSheet(
        """
        * {
            font-family: "Segoe UI", "Ubuntu", "Roboto", "Helvetica Neue", sans-serif;
            font-size: 13px;
        }
        QMainWindow, QWidget {
            background-color: #0f1115;
            color: #e6e9ef;
        }
        QLabel {
            color: #e6e9ef;
            background-color: transparent;
        }
        QPushButton {
            background-color: #252a35;
            color: #e6e9ef;
            border: 1px solid #2c333f;
            padding: 8px 14px;
            border-radius: 8px;
            font-weight: 600;
            min-height: 36px;
        }
        QPushButton:hover {
            background-color: #2c333f;
            border-color: #3a424f;
        }
        QPushButton:pressed {
            background-color: #343c4a;
        }
        QPushButton:disabled {
            background-color: #1a1d24;
            color: #6b7280;
            border-color: #252a35;
        }
        QPushButton#primary {
            background-color: #3eb34a;
            color: #0f1115;
            border-color: #3eb34a;
            font-weight: 700;
            padding: 10px 18px;
        }
        QPushButton#primary:hover {
            background-color: #5cd962;
            border-color: #5cd962;
        }
        QPushButton#primary:pressed {
            background-color: #2f8c39;
        }
        QPushButton#record {
            background-color: #ef4444;
            color: #ffffff;
            border-color: #ef4444;
            font-weight: 700;
            padding: 10px 18px;
        }
        QPushButton#record:hover {
            background-color: #f87171;
            border-color: #f87171;
        }
        QPushButton#record:pressed {
            background-color: #dc2626;
        }
        QPushButton#stop {
            background-color: #dc2626;
            color: #ffffff;
            border-color: #dc2626;
            font-weight: 700;
            padding: 10px 18px;
        }
        QPushButton#stop:hover {
            background-color: #ef4444;
            border-color: #ef4444;
        }
        QPushButton#ghost {
            background-color: transparent;
            border: 1px solid transparent;
            color: #9aa0ac;
        }
        QPushButton#ghost:hover {
            background-color: #1e222b;
            border-color: #2c333f;
            color: #e6e9ef;
        }
        QComboBox, QSpinBox {
            background-color: #1e222b;
            color: #e6e9ef;
            border: 1px solid #2c333f;
            border-radius: 8px;
            padding: 6px 10px;
            min-height: 32px;
        }
        QComboBox:hover, QSpinBox:hover {
            border-color: #3a424f;
        }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox QAbstractItemView {
            background-color: #1e222b;
            color: #e6e9ef;
            border: 1px solid #2c333f;
            border-radius: 8px;
            selection-background-color: #3eb34a;
            outline: none;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #252a35;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #3eb34a;
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }
        QSlider::handle:horizontal:hover {
            background: #5cd962;
        }
        QSlider::sub-page:horizontal {
            background: #2f8c39;
            border-radius: 3px;
        }
        QCheckBox {
            color: #9aa0ac;
            font-size: 12px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #2c333f;
            border-radius: 3px;
            background-color: #1e222b;
        }
        QCheckBox::indicator:checked {
            background-color: #3eb34a;
            border-color: #3eb34a;
        }
        QCheckBox::indicator:hover {
            border-color: #3a424f;
        }
        QStatusBar {
            background-color: #0f1115;
            color: #9aa0ac;
            border-top: 1px solid #1e222b;
            padding: 4px 12px;
        }
        QToolTip {
            background-color: #252a35;
            color: #e6e9ef;
            border: 1px solid #2c333f;
            border-radius: 6px;
            padding: 6px 10px;
        }
        QScrollBar:vertical {
            background: #16191f;
            width: 10px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #343c4a;
            min-height: 28px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #3eb34a;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QMenuBar {
            background-color: #0f1115;
            color: #e6e9ef;
            border-bottom: 1px solid #1e222b;
        }
        QMenuBar::item {
            background: transparent;
            padding: 6px 12px;
        }
        QMenuBar::item:selected {
            background: #1e222b;
        }
        QMenu {
            background-color: #1e222b;
            color: #e6e9ef;
            border: 1px solid #2c333f;
            border-radius: 8px;
        }
        QMenu::item {
            padding: 8px 24px;
        }
        QMenu::item:selected {
            background-color: #3eb34a;
            color: #0f1115;
        }
        """
        + CARD_QSS
    )

