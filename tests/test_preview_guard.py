import unittest
from unittest.mock import MagicMock, patch

import numpy as np

try:
    from app.ui import main_window
except ImportError:  # pragma: no cover - PyQt6 not installed on the test host
    main_window = None


def _make_window():
    """Build a MainWindow against an offscreen Qt application.

    The window is kept alive in a module level list: closing or garbage
    collecting it mid-test destroys the underlying C++ object and the wrapper
    stops working, which would hide what we actually want to assert.
    """
    if main_window is None:
        raise unittest.SkipTest("PyQt6 non disponibile")
    try:
        from PyQt6.QtWidgets import QApplication
        from app.ui.main_window import MainWindow
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest("PyQt6 non disponibile")
    global _APP
    if QApplication.instance() is None:
        _APP = QApplication([])  # kept alive: destroying it destroys the widgets
    window = MainWindow()
    _OPEN_WINDOWS.append(window)
    return window


_APP = None
_OPEN_WINDOWS = []


class PreviewPipelineGuardTest(unittest.TestCase):
    """A bad frame must not escape the preview callback.

    PyQt aborts the process when a slot raises, so _update_preview has to
    contain any exception coming from the per-frame processing steps
    (filter, face framing, motion, recorder, streaming).
    """

    def test_filter_error_does_not_raise(self):
        w = _make_window()
        w._current_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        w._apply_filter = lambda frame: (_ for _ in ()).throw(ValueError("frame non valido"))
        w._update_preview()  # must not raise
        self.assertGreaterEqual(w._preview_failures, 1)

    def test_repeated_errors_stop_the_timer(self):
        w = _make_window()
        w._current_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        w._apply_filter = lambda frame: (_ for _ in ()).throw(RuntimeError("boom"))
        w._show_status = MagicMock()
        for _ in range(10):
            w._update_preview()
        self.assertFalse(w._preview_timer.isActive())

    def test_good_frame_keeps_working_after_an_error(self):
        w = _make_window()
        w._current_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        original = w._apply_filter
        w._apply_filter = lambda frame: (_ for _ in ()).throw(RuntimeError("boom"))
        w._update_preview()
        w._apply_filter = original
        w._update_preview()  # must not raise and must not stop the timer
        self.assertTrue(w._preview_timer.isActive())


class FaceFramingFailureTest(unittest.TestCase):
    def test_feature_disables_after_repeated_failures(self):
        w = _make_window()
        w._face_framing_enabled = True
        w.chk_face = MagicMock()
        w._show_status = MagicMock()
        w._current_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # force the detector to fail on every frame
        with patch.object(main_window.cv2, "CascadeClassifier",
                          side_effect=RuntimeError("cascade rotta")):
            for _ in range(5):
                result = w._apply_face_framing(w._current_frame)
                self.assertIsNotNone(result)
        # after the limit the feature switches itself off and tells the user
        self.assertFalse(w._face_framing_enabled)
        w.chk_face.setChecked.assert_called_with(False)
        w._show_status.assert_called()
