import logging
import sys
from pathlib import Path

import cv2
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow

# Limit OpenCV threads to avoid audio crackling on some setups
cv2.setNumThreads(1)


def setup_logging() -> None:
    log_dir = Path.home() / "MintCam" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mintcam.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("mintcam").info("Avvio MintCam")


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("MintCam")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
