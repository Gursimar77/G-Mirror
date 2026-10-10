"""
Tests for G-Mirror MP4 Recorder.
"""

import os
import sys
import tempfile
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import av
import pytest
from gmirror.recording.recorder import Recorder


def test_recorder_start_stop(tmp_path):
    output_file = str(tmp_path / "test_recording.mp4")
    rec = Recorder()

    assert not rec.is_recording
    started = rec.start(output_file, fps=30, bitrate_kbps=2000, include_audio=False)
    assert started
    assert rec.is_recording
    assert rec.output_path == output_file

    # Create dummy video frame
    frame = av.VideoFrame(640, 480, "rgb24")
    for plane in frame.planes:
        plane.update(bytes(plane.buffer_size))

    rec.write_video_frame(frame)
    assert rec.frame_count == 1

    saved_path = rec.stop()
    assert saved_path == output_file
    assert not rec.is_recording
    assert os.path.exists(output_file)
    assert os.path.getsize(output_file) > 0


def test_recorder_double_start(tmp_path):
    output_file1 = str(tmp_path / "test1.mp4")
    output_file2 = str(tmp_path / "test2.mp4")
    rec = Recorder()

    assert rec.start(output_file1)
    # Second start while already recording should return False
    assert not rec.start(output_file2)
    rec.stop()
