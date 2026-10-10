"""
G-Mirror MP4 Recorder.

Records the mirrored AirPlay session to an MP4 file using PyAV's
muxer. Handles clean file finalization even on unexpected stop.

Features:
  - MP4 container (H.264 video + AAC audio)
  - Configurable FPS and bitrate
  - Safe finalization (flushes all packets before close)
  - Recording timer
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import av
import numpy as np
from av.video.frame import VideoFrame as AVVideoFrame

log = logging.getLogger(__name__)


class Recorder:
    """
    Records decoded video (and optionally audio) to an MP4 file.

    Usage:
        rec = Recorder()
        rec.start("/path/to/output.mp4")
        rec.write_video_frame(av_frame)
        rec.write_audio_chunk(pcm_array)
        rec.stop()
    """

    def __init__(self) -> None:
        self._container: Optional[av.container.OutputContainer] = None
        self._video_stream = None
        self._audio_stream = None
        self._lock = threading.Lock()
        self._recording = False
        self._start_time: float = 0.0
        self._output_path: str = ""
        self._fps: int = 30
        self._bitrate_kbps: int = 8000
        self._include_audio: bool = True
        self._frame_count: int = 0
        self._pts_video: int = 0
        self._pts_audio: int = 0

    def start(
        self,
        output_path: str,
        fps: int = 30,
        bitrate_kbps: int = 8000,
        include_audio: bool = True,
    ) -> bool:
        with self._lock:
            if self._recording:
                log.warning("Recording already in progress.")
                return False
            try:
                # Ensure directory exists
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                self._output_path = output_path
                self._fps = fps
                self._bitrate_kbps = bitrate_kbps
                self._include_audio = include_audio
                self._frame_count = 0
                self._pts_video = 0
                self._pts_audio = 0

                self._container = av.open(output_path, mode="w")

                # Video stream
                self._video_stream = self._container.add_stream("libx264", rate=fps)
                self._video_stream.bit_rate = bitrate_kbps * 1000
                self._video_stream.pix_fmt = "yuv420p"
                # Low-latency x264 settings
                self._video_stream.options = {
                    "preset": "veryfast",
                    "crf": "23",
                    "movflags": "+faststart",
                }

                # Audio stream
                if include_audio:
                    self._audio_stream = self._container.add_stream("aac", rate=44100)
                    self._audio_stream.layout = "stereo"
                    self._audio_stream.bit_rate = 192000

                self._recording = True
                self._start_time = time.time()
                log.info("Recording started: %s", output_path)
                return True

            except Exception as e:
                log.error("Failed to start recording: %s", e)
                self._cleanup()
                return False

    def write_video_frame(self, frame: AVVideoFrame) -> None:
        with self._lock:
            if not self._recording or self._video_stream is None:
                return
            try:
                # Convert to yuv420p if needed
                if frame.format.name != "yuv420p":
                    frame = frame.reformat(format="yuv420p")
                frame.pts = self._pts_video
                self._pts_video += 1
                self._frame_count += 1

                for packet in self._video_stream.encode(frame):
                    self._container.mux(packet)
            except Exception as e:
                log.debug("Video write error: %s", e)

    def write_audio_chunk(self, pcm: np.ndarray) -> None:
        """Write float32 PCM (samples, channels) to audio stream."""
        with self._lock:
            if not self._recording or self._audio_stream is None or not self._include_audio:
                return
            try:
                frame = av.AudioFrame.from_ndarray(
                    pcm.T.astype(np.float32), format="fltp", layout="stereo"
                )
                frame.sample_rate = 44100
                frame.pts = self._pts_audio
                self._pts_audio += len(pcm)

                for packet in self._audio_stream.encode(frame):
                    self._container.mux(packet)
            except Exception as e:
                log.debug("Audio write error: %s", e)

    def stop(self) -> Optional[str]:
        """Finalize and close the recording. Returns the output path."""
        with self._lock:
            if not self._recording:
                return None
            path = self._output_path
            try:
                self._flush_streams()
            except Exception as e:
                log.warning("Flush error during stop: %s", e)
            finally:
                self._cleanup()
                self._recording = False
            log.info("Recording saved: %s (%d frames)", path, self._frame_count)
            return path

    def _flush_streams(self) -> None:
        if self._container is None:
            return
        if self._video_stream:
            for packet in self._video_stream.encode(None):
                self._container.mux(packet)
        if self._audio_stream:
            for packet in self._audio_stream.encode(None):
                self._container.mux(packet)
        self._container.close()

    def _cleanup(self) -> None:
        self._container = None
        self._video_stream = None
        self._audio_stream = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> float:
        if self._recording:
            return time.time() - self._start_time
        return 0.0

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def output_path(self) -> str:
        return self._output_path
