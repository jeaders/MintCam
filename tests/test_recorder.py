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


class AudioRecordingTest(unittest.TestCase):
    """PulseAudio vs ALSA selection and audio_device passthrough."""

    def _get_audio_part(self, cmd):
        """Extract the audio input section: (-f <fmt>, -i <device>)."""
        indices = [i for i, x in enumerate(cmd) if x == "-f"]
        # Skip the video format (rawvideo) and the output format (mp4)
        for idx in indices:
            if cmd[idx + 1] in ("alsa", "pulse"):
                return cmd[idx + 1], cmd[idx + 3]  # (format, device)
        return None, None

    def test_pulseaudio_used_when_available(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pactl"
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stderr = MagicMock()
                mock_popen.return_value = proc
                ok = rec.start(frame, Path("/tmp/test.mp4"), fps=30, audio=True)
                self.assertTrue(ok)
                cmd = mock_popen.call_args[0][0]
                fmt, device = self._get_audio_part(cmd)
                self.assertEqual(fmt, "pulse")
                self.assertEqual(device, "@DEFAULT_SOURCE@")

    def test_alsa_fallback_when_no_pulseaudio(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stderr = MagicMock()
                mock_popen.return_value = proc
                ok = rec.start(frame, Path("/tmp/test.mp4"), fps=30, audio=True)
                self.assertTrue(ok)
                cmd = mock_popen.call_args[0][0]
                fmt, device = self._get_audio_part(cmd)
                self.assertEqual(fmt, "alsa")
                self.assertEqual(device, "default")

    def test_audio_device_override(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pactl"
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stderr = MagicMock()
                mock_popen.return_value = proc
                ok = rec.start(
                    frame, Path("/tmp/test.mp4"), fps=30,
                    audio=True, audio_device="alsa_input.usb-mic",
                )
                self.assertTrue(ok)
                cmd = mock_popen.call_args[0][0]
                fmt, device = self._get_audio_part(cmd)
                self.assertEqual(fmt, "pulse")
                self.assertEqual(device, "alsa_input.usb-mic")

    def test_missing_ffmpeg_returns_false(self) -> None:
        rec = Recorder()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pactl"
            with patch("subprocess.Popen", side_effect=FileNotFoundError("no ffmpeg")):
                ok = rec.start(frame, Path("/tmp/test.mp4"), fps=30, audio=True)
                self.assertFalse(ok)


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


class FocusAssistAdaptiveColourTest(unittest.TestCase):
    """The focus indicator compares against the recent best, not a threshold.

    A fixed threshold made the indicator red on every camera: the Laplacian
    variance depends on the scene and the resolution, and a real webcam values
    around 10 where the threshold was 80.
    """

    def _colour(self, score, best):
        ratio = score / (best or 1.0)
        if ratio >= 0.9:
            return "#5cd962"
        if ratio >= 0.6:
            return "#f59e0b"
        return "#ef4444"

    def test_bright_scene_is_green_even_with_a_low_score(self):
        # punteggio 11 su una webcam reale: con la soglia fissa era rosso
        self.assertEqual(self._colour(11, 12), "#5cd962")

    def test_blurred_frame_turns_red(self):
        self.assertEqual(self._colour(1, 100), "#ef4444")

    def test_slightly_blurred_is_amber(self):
        self.assertEqual(self._colour(70, 100), "#f59e0b")


class FaceFramingMinimumSizeTest(unittest.TestCase):
    """The minimum face size is relative to the frame, not a fixed pixel count.

    A fixed 60x60 minimum missed distant faces on small resolutions, which is
    why the framing looked broken.
    """

    @staticmethod
    def _min_size(height, width):
        min_side = min(height, width)
        return (max(24, int(min_side * 0.07)),) * 2

    def test_small_frame_gets_a_smaller_minimum(self):
        self.assertEqual(self._min_size(480, 640), (33, 33))

    def test_large_frame_gets_a_larger_minimum(self):
        self.assertEqual(self._min_size(1080, 1920), (75, 75))

    def test_never_below_the_floor(self):
        self.assertEqual(self._min_size(240, 320), (24, 24))
