import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.settings import Settings, DEFAULTS


class SettingsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        s = Settings()
        for key, value in DEFAULTS.items():
            self.assertEqual(s.get(key), value)

    def test_set_and_get(self) -> None:
        with patch.object(Settings, "FILE", Path("/tmp/mintcam_test_settings.json")):
            s = Settings()
            s.set("brightness", 50)
            self.assertEqual(s.get("brightness"), 50)
            # reload
            s2 = Settings()
            self.assertEqual(s2.get("brightness"), 50)
            Path("/tmp/mintcam_test_settings.json").unlink(missing_ok=True)

    def test_save_creates_file(self) -> None:
        with patch.object(Settings, "FILE", Path("/tmp/mintcam_test_save.json")):
            s = Settings()
            s.set("fps", 60)
            self.assertTrue(Path("/tmp/mintcam_test_save.json").exists())
            Path("/tmp/mintcam_test_save.json").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
