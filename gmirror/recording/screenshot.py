"""
G-Mirror Screenshot Capture.

Captures the current mirrored frame and saves it as PNG or JPEG.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from av.video.frame import VideoFrame as AVVideoFrame

log = logging.getLogger(__name__)


def capture_screenshot(
    frame: AVVideoFrame,
    folder: str,
    fmt: str = "png",
) -> Optional[str]:
    """
    Save the current video frame to a file.

    Args:
        frame: Decoded AV video frame
        folder: Target directory
        fmt: "png" or "jpg"

    Returns:
        Saved file path, or None on failure.
    """
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"GMirror_Screenshot_{ts}.{fmt}"
        filepath = str(Path(folder) / filename)

        img = frame.to_image()  # Returns a Pillow Image
        if fmt.lower() == "jpg":
            img.save(filepath, "JPEG", quality=95)
        else:
            img.save(filepath, "PNG")

        log.info("Screenshot saved: %s", filepath)
        return filepath
    except Exception as e:
        log.error("Screenshot failed: %s", e)
        return None
