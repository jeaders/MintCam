import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from app.storage import Storage


class StorageTest(unittest.TestCase):
    def test_photo_filename(self) -> None:
        name = Storage.photo_filename()
        self.assertTrue(name.startswith("foto_"))
        self.assertTrue(name.endswith(".jpg"))

    def test_video_filename(self) -> None:
        name = Storage.video_filename()
        self.assertTrue(name.startswith("video_"))
        self.assertTrue(name.endswith(".mp4"))

    def test_save_photo_creates_file(self) -> None:
        frame = MagicMock()
        with patch("cv2.imwrite", return_value=True) as mock_write, patch.object(Storage, "photos_dir", return_value=Path("/tmp")):
            path = Storage.save_photo(frame, Path("/tmp/test.jpg"))
            self.assertIsNotNone(path)
            mock_write.assert_called_once()

    def test_ensure_dir_creates_missing_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "dir"
            Storage._ensure_dir(target)
            self.assertTrue(target.exists())

    def test_save_photo_handles_error(self) -> None:
        frame = MagicMock()
        with patch("cv2.imwrite", side_effect=OSError("no space")):
            path = Storage.save_photo(frame, Path("/tmp/test_err.jpg"))
            self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
