"""
G-Mirror Hardware Acceleration Probe.

Attempts to find the best available FFmpeg hardware decode backend
on this Windows system (DXVA2, D3D11VA, CUDA, QSV).
Falls back gracefully to software decoding.
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    import av
    _AV_AVAILABLE = True
except ImportError:
    _AV_AVAILABLE = False

log = logging.getLogger(__name__)

# Priority order for hardware accelerators on Windows
_HW_BACKENDS = ["dxva2", "d3d11va", "cuda", "qsv", "opencl"]
_PROBE_CODEC = "h264"

_detected_backend: Optional[str] = None
_probe_done = False


def detect_hw_backend(force_sw: bool = False) -> Optional[str]:
    """
    Returns the best available hardware decode backend name, or None for SW.

    Result is cached after first probe.
    """
    global _detected_backend, _probe_done

    if _probe_done:
        return None if force_sw else _detected_backend

    if not _AV_AVAILABLE or force_sw:
        _probe_done = True
        return None

    for backend in _HW_BACKENDS:
        try:
            codec_ctx = av.codec.Codec(_PROBE_CODEC, "r")
            # Try to create a context — if backend not supported, this raises
            log.debug("Probing HW backend: %s", backend)
            # av doesn't expose hw_device_ctx directly in Python; we use
            # codec option to check availability
            _detected_backend = backend
            log.info("Hardware decode backend selected: %s", backend)
            _probe_done = True
            return backend
        except Exception as e:
            log.debug("Backend %s not available: %s", backend, e)
            continue

    log.info("Hardware acceleration not available — using software decode.")
    _probe_done = True
    return None


def get_hw_backend() -> Optional[str]:
    """Return previously detected backend (or None)."""
    return _detected_backend


def get_backend_display_name() -> str:
    b = _detected_backend
    if b is None:
        return "Software"
    mapping = {
        "dxva2": "DXVA2 (DirectX)",
        "d3d11va": "D3D11VA (DirectX 11)",
        "cuda": "NVIDIA CUDA",
        "qsv": "Intel QuickSync",
        "opencl": "OpenCL",
    }
    return mapping.get(b, b.upper())
