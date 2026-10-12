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


class AudioLevelParsingTest(unittest.TestCase):
    """ffmpeg reports the loudness on stderr through the ebur128 filter.

    The recorder parses those lines to draw the level meter, so the parser
    has to cope with the number formats ffmpeg actually produces, including
    -nan on silent input and the values that mean clipping.
    """

    def test_real_line(self):
        from app.recorder import _LEVEL_PATTERN, _to_float
        line = ("[Parsed_ebur128_0 @ 0x6086799c4280] t: 1.20  TARGET:-23 LUFS"
                "    M:-31.4 S:-31.2     I:-31.2 LUFS       LRA:   0.0 LU"
                "  FTPK:-25.9 -25.9 dBFS  TPK:-25.9 -25.9 dBFS")
        m = _LEVEL_PATTERN.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(_to_float(m.group("m")), -31.4)
        self.assertEqual(_to_float(m.group("tpk")), -25.9)

    def test_line_with_spaces_after_colon(self):
        from app.recorder import _LEVEL_PATTERN, _to_float
        line = ("t: 0.0999  TARGET:-23 LUFS    M:-120.7 S:-120.7     I: -70.0 LUFS"
                "       LRA:   0.0 LU  FTPK: -21.6 -21.6 dBFS  TPK: -21.6 -21.6 dBFS")
        m = _LEVEL_PATTERN.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(_to_float(m.group("tpk")), -21.6)

    def test_nan_and_inf_become_none(self):
        from app.recorder import _to_float
        self.assertIsNone(_to_float("-nan"))
        self.assertIsNone(_to_float(" nan"))
        self.assertIsNone(_to_float("inf"))
        self.assertIsNone(_to_float("-inf"))
        self.assertIsNone(_to_float(None))

    def test_clipping_values_are_parsed(self):
        from app.recorder import _LEVEL_PATTERN, _to_float
        line = "t: 5.0  M: -nan S:-120.7  I:-31.2 LUFS  TPK: -0.8 -0.8 dBFS"
        m = _LEVEL_PATTERN.search(line)
        self.assertIsNotNone(m)
        self.assertIsNone(_to_float(m.group("m")))
        self.assertEqual(_to_float(m.group("tpk")), -0.8)

    def test_other_lines_are_ignored(self):
        from app.recorder import _LEVEL_PATTERN
        for line in ("Input #0, alsa, from 'default':",
                     "Stream #0:0: Audio: pcm_s16le, 48000 Hz, 2 channels",
                     "frame=  120 fps= 30 q=28.0 size=     256kB time=00:00:04"):
            self.assertIsNone(_LEVEL_PATTERN.search(line))
