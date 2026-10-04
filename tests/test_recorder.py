import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from app.recorder import Recorder


class RecorderTest(unittest.TestCase):
    def test_start_and_stop(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("cv2.VideoWriter") as mock_writer:
            writer = MagicMock()
            writer.isOpened.return_value = True
            mock_writer.return_value = writer
            path = Path("/tmp/test.mp4")
            ok = rec.start(frame, path, fps=30)
            self.assertTrue(ok)
            self.assertTrue(rec.is_recording())
            rec.write(frame)
            result = rec.stop()
            self.assertIsNotNone(result)
            self.assertFalse(rec.is_recording())

    def test_no_double_start(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("cv2.VideoWriter") as mock_writer:
            writer = MagicMock()
            writer.isOpened.return_value = True
            mock_writer.return_value = writer
            rec.start(frame, Path("/tmp/test.mp4"), fps=30)
            ok = rec.start(frame, Path("/tmp/test2.mp4"), fps=30)
            self.assertFalse(ok)

    def test_codec_fallback(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        calls = []
        with patch("cv2.VideoWriter") as mock_writer:
            def side_effect(*args, **kwargs):
                w = MagicMock()
                if len(calls) == 0:
                    w.isOpened.return_value = False
                else:
                    w.isOpened.return_value = True
                calls.append(1)
                return w
            mock_writer.side_effect = side_effect
            path = Path("/tmp/test.mp4")
            ok = rec.start(frame, path, fps=30)
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
