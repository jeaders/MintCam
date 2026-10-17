"""Audio device enumeration for MintCam.

On Linux the audio capture goes through either PulseAudio or ALSA, depending
on what the desktop session provides. PulseAudio is the default on Mint XFCE;
pure ALSA shows up on minimal installations.

The recorder picks @DEFAULT_SOURCE@ when PulseAudio is available and falls
back to the ALSA "default" device, but the user may want to choose a specific
microphone (for example a USB headset when several are plugged in).
"""

import logging
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger("mintcam.audio")


def has_pulseaudio() -> bool:
    """True when a PulseAudio server is reachable on this host."""
    return shutil.which("pactl") is not None


def list_audio_sources() -> list[tuple[str, str]]:
    """Enumerate capture-capable audio sources.

    Returns a list of (device_name, display_label) pairs. When PulseAudio is
    not available the list contains a single entry for the ALSA "default"
    device so the UI still gives the user a choice.
    """
    if has_pulseaudio():
        try:
            output = subprocess.run(
                ["pactl", "--format=json", "list", "sources"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if output:
                import json as _json
                sources = _json.loads(output)
                result: list[tuple[str, str]] = []
                for src in sources:
                    name = src.get("Name", "")
                    desc = src.get("Description", name)
                    # only sources that can actually record
                    if src.get("MonitorOfSinkName") and src.get("MonitorOfSinkName"):
                        continue
                    if src.get("State") != "RUNNING" and src.get("State") != "IDLE" and src.get("State") != "SUSPENDED":
                        continue
                    mute = src.get("Mute", False)
                    if mute:
                        continue
                    result.append((name, desc or name))
                if result:
                    return result
                # fall through: no usable sources found
        except Exception as exc:
            logger.debug("pactl enumeration failed: %s", exc)
        # no PulseAudio sources found, but PulseAudio exists
        return []
    # ALSA fallback
    return [("default", "Predefinito (ALSA)")]


def default_source_name() -> str:
    """Return the source name the recorder should use by default."""
    if has_pulseaudio():
        return "@DEFAULT_SOURCE@"
    return "default"
