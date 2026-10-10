"""
G-Mirror AirPlay Session State Machine.

Tracks the lifecycle of an AirPlay mirroring session:
  IDLE → CONNECTING → AUTHENTICATING → STREAMING → DISCONNECTED → IDLE

Emits status callbacks to the UI layer.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

log = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = auto()
    CONNECTING = auto()
    AUTHENTICATING = auto()
    STREAMING = auto()
    PAUSED = auto()
    DISCONNECTED = auto()
    ERROR = auto()


@dataclass
class SessionStats:
    """Live streaming statistics updated by the pipeline."""
    fps: float = 0.0
    resolution: str = "—"
    bitrate_kbps: float = 0.0
    latency_ms: float = 0.0
    dropped_frames: int = 0
    total_frames: int = 0
    decoder: str = "—"
    hw_accel: bool = False
    audio_active: bool = False
    network_quality: str = "—"   # "Excellent", "Good", "Fair", "Poor"
    connected_device: str = ""
    session_start: float = 0.0

    @property
    def session_duration(self) -> float:
        if self.session_start > 0:
            return time.time() - self.session_start
        return 0.0


StatusCallback = Callable[[SessionState, SessionStats], None]


class AirPlaySession:
    """
    Central session object.  Created once per app lifetime; reused across
    connections.  Thread-safe state transitions.
    """

    def __init__(self) -> None:
        self._state = SessionState.IDLE
        self._stats = SessionStats()
        self._lock = threading.RLock()
        self._callbacks: list[StatusCallback] = []

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def add_status_callback(self, cb: StatusCallback) -> None:
        with self._lock:
            self._callbacks.append(cb)

    def remove_status_callback(self, cb: StatusCallback) -> None:
        with self._lock:
            self._callbacks.discard(cb) if hasattr(self._callbacks, "discard") else None

    def _notify(self) -> None:
        state = self._state
        stats_copy = SessionStats(**self._stats.__dict__)
        for cb in list(self._callbacks):
            try:
                cb(state, stats_copy)
            except Exception as e:
                log.debug("Status callback error: %s", e)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def set_connecting(self, device_name: str = "") -> None:
        with self._lock:
            self._state = SessionState.CONNECTING
            self._stats = SessionStats(connected_device=device_name)
            log.info("Session: CONNECTING (device=%s)", device_name)
            self._notify()

    def set_authenticating(self) -> None:
        with self._lock:
            self._state = SessionState.AUTHENTICATING
            log.info("Session: AUTHENTICATING")
            self._notify()

    def set_streaming(self) -> None:
        with self._lock:
            self._state = SessionState.STREAMING
            self._stats.session_start = time.time()
            log.info("Session: STREAMING")
            self._notify()

    def set_paused(self) -> None:
        with self._lock:
            self._state = SessionState.PAUSED
            log.info("Session: PAUSED")
            self._notify()

    def set_disconnected(self) -> None:
        with self._lock:
            self._state = SessionState.DISCONNECTED
            log.info("Session: DISCONNECTED")
            self._notify()
            # Reset to IDLE after brief delay
            threading.Timer(2.0, self._reset_to_idle).start()

    def set_error(self, reason: str = "") -> None:
        with self._lock:
            self._state = SessionState.ERROR
            log.warning("Session: ERROR — %s", reason)
            self._notify()
            threading.Timer(3.0, self._reset_to_idle).start()

    def _reset_to_idle(self) -> None:
        with self._lock:
            if self._state in (SessionState.DISCONNECTED, SessionState.ERROR):
                self._state = SessionState.IDLE
                self._stats = SessionStats()
                log.info("Session: IDLE")
                self._notify()

    # ------------------------------------------------------------------
    # Stats update (called from pipeline threads)
    # ------------------------------------------------------------------

    def update_stats(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._stats, k):
                    setattr(self._stats, k, v)
            if self._state == SessionState.STREAMING:
                self._notify()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def stats(self) -> SessionStats:
        with self._lock:
            return SessionStats(**self._stats.__dict__)

    @property
    def is_streaming(self) -> bool:
        return self._state == SessionState.STREAMING
