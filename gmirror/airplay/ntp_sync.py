"""
G-Mirror NTP / AirPlay Clock Synchronization Responder.

AirPlay uses UDP timing packets (typically on port 7012) to synchronize
clocks between the iOS sender and the receiver for A/V lip-sync and
latency calculation.
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

# NTP epoch offset: seconds between 1900-01-01 and 1970-01-01
NTP_OFFSET = 2208988800


def get_ntp_timestamp() -> int:
    """Return current time as 64-bit NTP timestamp (32-bit seconds, 32-bit fraction)."""
    now = time.time() + NTP_OFFSET
    sec = int(now)
    frac = int((now - sec) * (1 << 32))
    return (sec << 32) | (frac & 0xFFFFFFFF)


class NTPSyncServer(threading.Thread):
    """
    UDP server listening on AIRPLAY_TIMING_PORT (7012).
    Responds to AirPlay timing synchronization requests.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 7012) -> None:
        super().__init__(name="NTPSyncServer", daemon=True)
        self._host = host
        self._port = port
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._active = False

    def run(self) -> None:
        try:
            self._serve()
        except Exception as e:
            if not self._stop_event.is_set():
                log.error("NTPSyncServer error: %s", e)

    def _serve(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)
        self._sock.bind((self._host, self._port))
        self._active = True
        log.info("NTPSyncServer listening on UDP %s:%d", self._host, self._port)

        while not self._stop_event.is_set():
            try:
                data, addr = self._sock.recvfrom(1024)
                if len(data) < 32:
                    continue

                recv_ts = get_ntp_timestamp()

                # Timing packet format (32 bytes):
                # 0..3: header (0x80 | 0x53 / 0xd3, seq)
                # 4..7: reserved
                # 8..15: originate timestamp (client transmit)
                # 16..23: receive timestamp (server receive)
                # 24..31: transmit timestamp (server transmit)
                resp = bytearray(32)
                resp[0] = 0x80
                resp[1] = data[1] | 0x80  # Reply flag
                resp[2:4] = data[2:4]     # Echo sequence number
                resp[4:8] = b"\x00\x00\x00\x00"
                resp[8:16] = data[24:32] if len(data) >= 32 else data[8:16]  # originate ts
                struct.pack_into(">Q", resp, 16, recv_ts)
                struct.pack_into(">Q", resp, 24, get_ntp_timestamp())

                self._sock.sendto(resp, addr)
            except socket.timeout:
                continue
            except OSError:
                break

        self._active = False

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    @property
    def is_active(self) -> bool:
        return self._active
