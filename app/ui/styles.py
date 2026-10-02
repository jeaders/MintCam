from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#1e1e1e"))
    palette.setColor(QPalette.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.Base, QColor("#2b2b2b"))
    palette.setColor(QPalette.AlternateBase, QColor("#1e1e1e"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2b2b2b"))
    palette.setColor(QPalette.ToolTipText, QColor("#e0e0e0"))
    palette.setColor(QPalette.Text, QColor("#e0e0e0"))
    palette.setColor(QPalette.Button, QColor("#2b2b2b"))
    palette.setColor(QPalette.ButtonText, QColor("#e0e0e0"))
    palette.setColor(QPalette.BrightText, QColor("#ff5555"))
    palette.setColor(QPalette.Link, QColor("#4fc3f7"))
    palette.setColor(QPalette.Highlight, QColor("#4fc3f7"))
    palette.setColor(QPalette.HighlightedText, QColor("#1e1e1e"))
    app.setPalette(palette)
    app.setStyleSheet(
        """
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        QLabel {
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #3a3a3a;
            padding: 8px 12px;
            border-radius: 6px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #3a3a3a;
        }
        QPushButton:pressed {
            background-color: #4a4a4a;
        }
        QPushButton:disabled {
            background-color: #252525;
            color: #777777;
            border-color: #2b2b2b;
        }
        QPushButton#primary {
            background-color: #4fc3f7;
            color: #1e1e1e;
            border-color: #4fc3f7;
        }
        QPushButton#primary:hover {
            background-color: #81d4fa;
        }
        QPushButton#record {
            background-color: #ff5252;
            color: #1e1e1e;
            border-color: #ff5252;
        }
        QPushButton#record:hover {
            background-color: #ff867f;
        }
        QPushButton#stop {
            background-color: #ff9800;
            color: #1e1e1e;
            border-color: #ff9800;
        }
        QComboBox, QSpinBox, QSlider {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            padding: 4px;
            min-height: 28px;
        }
        QComboBox QAbstractItemView {
            background-color: #2b2b2b;
            color: #e0e0e0;
            selection-background-color: #4fc3f7;
        }
        QGroupBox {
            border: 1px solid #3a3a3a;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            color: #e0e0e0;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 6px;
            color: #4fc3f7;
        }
        QStatusBar {
            background-color: #252525;
            color: #e0e0e0;
        }
        QToolTip {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #3a3a3a;
        }
        QScrollBar:vertical {
            background: #2b2b2b;
            width: 12px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #4a4a4a;
            min-height: 24px;
            border-radius: 4px;
        }
        """
    )
