import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from app.camera import CameraWorker, RESOLUTIONS


class CameraWorkerTest(unittest.TestCase):
    def test_resolutions(self) -> None:
        self.assertIn("640x480", RESOLUTIONS)
        self.assertEqual(RESOLUTIONS["640x480"], (640, 480))

    def test_no_camera_emits_error(self) -> None:
        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.isOpened.return_value = False
            worker = CameraWorker()
            errors = []
            worker.error.connect(lambda msg: errors.append(msg))
            worker._open()
            self.assertTrue(len(errors) > 0)

    def test_open_and_release(self) -> None:
        with patch("cv2.VideoCapture") as mock_cap:
            cap = MagicMock()
            cap.isOpened.return_value = True
            mock_cap.return_value = cap
            worker = CameraWorker()
            worker._open()
            self.assertIsNotNone(worker._cap)
            worker._release()
            self.assertIsNone(worker._cap)
            cap.release.assert_called_once()

    def test_frame_emission(self) -> None:
        with patch("cv2.VideoCapture") as mock_cap:
            cap = MagicMock()
            cap.isOpened.return_value = True
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cap.read.return_value = (True, frame)
            mock_cap.return_value = cap
            worker = CameraWorker()
            worker._max_frames = 3
            worker.start()
            worker.wait(5000)
            self.assertIsNotNone(worker.last_frame())


if __name__ == "__main__":
    unittest.main()
