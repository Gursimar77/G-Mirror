"""
G-Mirror mDNS/Bonjour Advertisement.

Advertises the AirPlay receiver service on the local network so that
iPhones can discover "G-Mirror" in their Screen Mirroring list.

Service types registered:
  - _airplay._tcp  (port 7000) — AirPlay video mirroring
  - _raop._tcp     (port 7000) — AirPlay audio (RAOP)

Protocol Reference: AirPlay protocol reverse-engineering documentation,
  openairplay/airplay2-receiver (MIT), UxPlay (GPL v3).
"""

from __future__ import annotations

import hashlib
import logging
import socket
import threading
import time
from typing import List, Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

from gmirror.settings.config import get_config

log = logging.getLogger(__name__)

# AirPlay feature flags (standard set for a mirror-capable receiver)
# Bit field from AirPlay2 spec (bit 27 off for direct fp-setup)
AIRPLAY_FEATURES = "0x527FFFF7,0xE"
AIRPLAY_STATUS_FLAGS = "0x44"
AIRPLAY_MODEL = "AppleTV3,2"    # Presentation model identifier


def _get_local_ip(adapter_hint: str = "Auto") -> str:
    """Get the primary local IPv4 address, or fall back to 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _make_device_id() -> str:
    """
    Generate a stable, deterministic MAC-style device ID from hostname.
    This is what appears in the AirPlay TXT records as 'deviceid'.
    """
    hostname = socket.gethostname()
    h = hashlib.md5(hostname.encode()).hexdigest()
    return ":".join(h[i:i+2] for i in range(0, 12, 2)).upper()


class MDNSAdvertiser:
    """
    Advertises G-Mirror as an AirPlay receiver via mDNS/Bonjour.

    Call start() to begin advertising; stop() to withdraw the service.
    The iPhone's Screen Mirroring list will show the receiver_name when
    both devices are on the same Wi-Fi network.
    """

    def __init__(self, receiver_name: str = "G-Mirror", port: int = 7000) -> None:
        self._name = receiver_name
        self._port = port
        self._zeroconf: Optional[Zeroconf] = None
        self._airplay_info: Optional[ServiceInfo] = None
        self._raop_info: Optional[ServiceInfo] = None
        self._running = False
        self._lock = threading.Lock()
        self._ip: str = "127.0.0.1"
        self._device_id = _make_device_id()

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            try:
                cfg = get_config()
                self._ip = _get_local_ip(cfg.network.adapter)
                self._name = cfg.network.receiver_name or self._name
                self._port = cfg.network.port

                self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
                self._register_airplay()
                self._running = True
                log.info(
                    "mDNS: Advertising '%s' on %s:%d (device_id=%s)",
                    self._name, self._ip, self._port, self._device_id,
                )
                return True
            except Exception as e:
                log.error("mDNS advertisement failed: %s", e)
                self._cleanup()
                return False

    def stop(self) -> None:
        with self._lock:
            self._cleanup()
            self._running = False
            log.info("mDNS: Service withdrawn.")

    def _register_airplay(self) -> None:
        ip_bytes = socket.inet_aton(self._ip)
        hostname = f"{self._name.replace(' ', '-')}.local."

        # _airplay._tcp TXT record properties required by iOS
        airplay_props = {
            "deviceid": self._device_id,
            "features": AIRPLAY_FEATURES,
            "flags": AIRPLAY_STATUS_FLAGS,
            "model": AIRPLAY_MODEL,
            "pk": "b07727d6f6cd65bc38e49e10f3d87cbc8b3e55fa9ded6cded63a55e7fe07eddd",
            "pi": self._device_id.replace(":", "").lower()[:32],
            "srcvers": "377.17.10.0",
            "vv": "2",
        }

        self._airplay_info = ServiceInfo(
            "_airplay._tcp.local.",
            f"{self._name}._airplay._tcp.local.",
            addresses=[ip_bytes],
            port=self._port,
            properties=airplay_props,
            server=hostname,
        )
        self._zeroconf.register_service(self._airplay_info)

        # _raop._tcp for audio pairing (format: DeviceID@Name)
        raop_name = f"{self._device_id.replace(':', '')}@{self._name}"
        raop_props = {
            "et": "0,3,5",
            "md": "0,1,2",
            "am": AIRPLAY_MODEL,
            "vs": "377.17.10.0",
            "pw": "false",
            "ft": AIRPLAY_FEATURES,
            "sf": AIRPLAY_STATUS_FLAGS,
            "tp": "UDP",
            "vn": "65537",
            "pk": airplay_props["pk"],
        }
        self._raop_info = ServiceInfo(
            "_raop._tcp.local.",
            f"{raop_name}._raop._tcp.local.",
            addresses=[ip_bytes],
            port=self._port,
            properties=raop_props,
            server=hostname,
        )
        self._zeroconf.register_service(self._raop_info)

    def _cleanup(self) -> None:
        if self._zeroconf:
            try:
                if self._airplay_info:
                    self._zeroconf.unregister_service(self._airplay_info)
                if self._raop_info:
                    self._zeroconf.unregister_service(self._raop_info)
                self._zeroconf.close()
            except Exception as e:
                log.debug("mDNS cleanup error: %s", e)
            finally:
                self._zeroconf = None
                self._airplay_info = None
                self._raop_info = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def local_ip(self) -> str:
        return self._ip

    @property
    def device_id(self) -> str:
        return self._device_id
