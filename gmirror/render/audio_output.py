"""
G-Mirror Audio Output.

Routes decoded PCM audio to a Windows audio output device using sounddevice.
Supports device selection, volume control, and mute.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import List, Optional

import numpy as np

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False
    log = logging.getLogger(__name__)
    log.warning("sounddevice not available — audio output disabled.")

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2
BLOCKSIZE = 512  # samples per callback (~11ms at 44100 Hz)


def list_output_devices() -> List[str]:
    """Return names of available audio output devices."""
    if not _SD_AVAILABLE:
        return ["Default"]
    try:
        devices = sd.query_devices()
        names = ["Default"]
        for d in devices:
            if d["max_output_channels"] > 0:
                names.append(d["name"])
        return names
    except Exception as e:
        log.warning("Audio device enumeration failed: %s", e)
        return ["Default"]


class AudioOutput:
    """
    Streams PCM audio to an output device using sounddevice.

    Consumes numpy arrays from a queue and feeds them to the OS audio API.
    """

    def __init__(self, device: str = "Default") -> None:
        self._device = None if device == "Default" else device
        self._volume = 1.0
        self._muted = False
        self._stream: Optional["sd.OutputStream"] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=32)
        self._buf = np.zeros((0, CHANNELS), dtype=np.float32)
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        if not _SD_AVAILABLE or self._running:
            return
        try:
            self._stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=BLOCKSIZE,
                device=self._device,
                callback=self._audio_callback,
                latency="low",
            )
            self._stream.start()
            self._running = True
            log.info("Audio output started (device=%s)", self._device or "Default")
        except Exception as e:
            log.error("Audio output failed to start: %s", e)

    def stop(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        log.info("Audio output stopped.")

    def feed(self, pcm: np.ndarray) -> None:
        """Feed decoded PCM data (float32, shape=[N, 2]) into the output buffer."""
        if not self._running:
            return
        try:
            self._audio_queue.put_nowait(pcm)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            self._audio_queue.put_nowait(pcm)

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        """sounddevice callback — called from CFFI PortAudio thread.
        MUST NEVER raise an exception, otherwise CFFI pops up a Windows MessageBox!
        """
        try:
            # Refill buffer from queue
            while len(self._buf) < frames:
                try:
                    chunk = self._audio_queue.get_nowait()
                    if chunk.ndim == 1:
                        chunk = chunk.reshape(-1, 1)
                    if chunk.shape[1] < CHANNELS:
                        chunk = np.tile(chunk, (1, CHANNELS))[:, :CHANNELS]
                    elif chunk.shape[1] > CHANNELS:
                        chunk = chunk[:, :CHANNELS]
                    self._buf = np.vstack([self._buf, chunk]) if len(self._buf) > 0 else chunk
                except queue.Empty:
                    break

            if len(self._buf) >= frames:
                data = self._buf[:frames]
                self._buf = self._buf[frames:]
            else:
                # Underrun — pad with silence
                data = np.zeros((frames, CHANNELS), dtype=np.float32)
                if len(self._buf) > 0:
                    data[:len(self._buf), :CHANNELS] = self._buf[:, :CHANNELS]
                    self._buf = np.zeros((0, CHANNELS), dtype=np.float32)

            # Apply volume / mute
            if self._muted:
                outdata.fill(0.0)
            else:
                outdata[:] = np.clip(data[:, :CHANNELS] * self._volume, -1.0, 1.0)
        except Exception:
            outdata.fill(0.0)
            self._buf = np.zeros((0, CHANNELS), dtype=np.float32)

    def set_volume(self, volume: float) -> None:
        """Set volume 0.0–1.0."""
        self._volume = max(0.0, min(1.0, volume))

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def set_device(self, device: str) -> None:
        was_running = self._running
        self.stop()
        self._device = None if device == "Default" else device
        if was_running:
            self.start()

    @property
    def is_running(self) -> bool:
        return self._running
