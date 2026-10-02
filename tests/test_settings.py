import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.settings import Settings, DEFAULTS


class SettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(Settings, "FILE", Path(self._tmp.name) / "settings.json")
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def test_defaults(self) -> None:
        s = Settings()
        for key, value in DEFAULTS.items():
            self.assertEqual(s.get(key), value)

    def test_set_and_get(self) -> None:
        s = Settings()
        s.set("brightness", 50)
        self.assertEqual(s.get("brightness"), 50)
        s2 = Settings()
        self.assertEqual(s2.get("brightness"), 50)

    def test_save_creates_file(self) -> None:
        s = Settings()
        s.set("fps", 60)
        self.assertTrue(Path(s.FILE).exists())


if __name__ == "__main__":
    unittest.main()
