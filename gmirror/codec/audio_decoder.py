"""
G-Mirror Audio Decoder.

Decodes AAC-ELD / ALAC audio packets from the AirPlay audio stream
using PyAV (FFmpeg). Outputs raw PCM float32 arrays for sounddevice.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

import av
import numpy as np

from gmirror.airplay.audio_receiver import AudioPacket

import struct

log = logging.getLogger(__name__)

DECODED_AUDIO_MAXSIZE = 64

# MPEG-4 AudioSpecificConfig for AAC-ELD (AOT 39), 44100 Hz, 2 channels, 480 samples/frame
_AAC_ELD_EXTRADATA = b"\xf8\xe8\x50\x00"

# Standard Apple ALAC 36-byte magic cookie (352 samples/frame, 16-bit, stereo, 44100 Hz)
_ALAC_EXTRADATA = struct.pack(
    ">III BBBB H III",
    36, 0x616C6163, 0,
    352 >> 24, (352 >> 16) & 0xFF, (352 >> 8) & 0xFF, 352 & 0xFF,
    0,
    (16 << 24) | (40 << 16) | (10 << 8) | 14,
    (2 << 24) | (255 << 8),
    44100,
)


class AudioDecoder(threading.Thread):
    """
    Decodes AAC-ELD / ALAC audio packets using FFmpeg via PyAV.

    Input:  queue.Queue[AudioPacket]
    Output: queue.Queue[np.ndarray]  (float32, shape [samples, 2])
    """

    CODECS = {
        "aac-eld": "aac",
        "alac": "alac",
        "pcm": None,  # Raw PCM — no decode needed
        "opus": "libopus",
    }

    def __init__(self, input_queue: queue.Queue, codec: str = "aac-eld") -> None:
        super().__init__(name="AudioDecoder", daemon=True)
        self._input = input_queue
        self._output: queue.Queue = queue.Queue(maxsize=DECODED_AUDIO_MAXSIZE)
        self._codec = codec
        self._stop_event = threading.Event()
        self._codec_ctx: Optional[av.codec.context.CodecContext] = None
        self._resampler: Optional[av.AudioResampler] = None
        self._sample_rate = 44100
        self._channels = 2

    def run(self) -> None:
        self._init_codec()
        try:
            self._decode_loop()
        except Exception as e:
            if not self._stop_event.is_set():
                log.error("AudioDecoder error: %s", e)

    def _init_codec(self) -> None:
        if self._codec_ctx is not None:
            try:
                self._codec_ctx.close()
            except Exception:
                pass
            self._codec_ctx = None

        ffmpeg_codec = self.CODECS.get(self._codec)
        if ffmpeg_codec is None:
            log.info("Audio codec '%s': pass-through (no decode needed)", self._codec)
            return
        try:
            codec = av.codec.Codec(ffmpeg_codec, "r")
            self._codec_ctx = av.codec.context.CodecContext.create(codec)
            self._codec_ctx.sample_rate = self._sample_rate
            self._codec_ctx.layout = "stereo"
            if self._codec == "aac-eld":
                self._codec_ctx.extradata = _AAC_ELD_EXTRADATA
            elif self._codec == "alac":
                self._codec_ctx.extradata = _ALAC_EXTRADATA
            self._codec_ctx.open()
            self._resampler = av.AudioResampler(
                format="fltp", layout="stereo", rate=self._sample_rate
            )
            log.info("Audio decoder initialized: %s (mode=%s)", ffmpeg_codec, self._codec)
        except Exception as e:
            log.warning("Audio decoder init failed (%s): %s", ffmpeg_codec, e)

    def _decode_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                pkt: AudioPacket = self._input.get(timeout=0.5)
            except queue.Empty:
                continue

            if pkt.codec and pkt.codec != self._codec:
                self._codec = pkt.codec
                self._init_codec()

            if self._codec_ctx is None:
                # PCM pass-through (16-bit big-endian or little-endian stereo)
                try:
                    arr = np.frombuffer(pkt.data, dtype=">i2").astype(np.float32) / 32768.0
                    arr = arr.reshape(-1, self._channels)
                    self._output.put_nowait(arr)
                except Exception:
                    pass
                continue

            try:
                packet = av.Packet(pkt.data)
                for frame in self._codec_ctx.decode(packet):
                    frames = self._resampler.resample(frame) if self._resampler else [frame]
                    for rframe in frames:
                        arr = rframe.to_ndarray().astype(np.float32, copy=False)
                        if arr.ndim == 2:
                            # Planar (channels, samples) -> (samples, channels)
                            arr = np.ascontiguousarray(arr.T)
                        elif arr.ndim == 1:
                            arr = arr.reshape(-1, 1)

                        # Strictly enforce 2-channel stereo shape (samples, 2)
                        if arr.shape[1] < self._channels:
                            arr = np.tile(arr, (1, self._channels))[:, :self._channels]
                        elif arr.shape[1] > self._channels:
                            arr = arr[:, :self._channels]

                        try:
                            self._output.put_nowait(arr)
                        except queue.Full:
                            try:
                                self._output.get_nowait()
                            except queue.Empty:
                                pass
                            self._output.put_nowait(arr)
            except Exception:
                # Avoid per-packet disk logging on invalid/corrupted audio frames
                pass

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def output_queue(self) -> queue.Queue:
        return self._output
