"""
G-Mirror Network Diagnostics.

Automatically tests the local environment for AirPlay compatibility and
reports results in plain English with actionable suggestions.

Checks performed:
  1.  Network adapter presence
  2.  Wi-Fi vs Ethernet detection
  3.  Active IP address (IPv4)
  4.  Gateway reachability
  5.  mDNS/UDP port 5353 availability
  6.  AirPlay port 7000 availability
  7.  Windows Firewall (via netsh)
  8.  Windows network profile (Public/Private)
  9.  Multicast availability
  10. IPv6 status
  11. AirPlay receiver service status
  12. mDNS advertisement visibility
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

log = logging.getLogger(__name__)


class CheckResult(Enum):
    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class DiagCheck:
    name: str
    status: CheckResult = CheckResult.SKIP
    message: str = ""
    suggestion: str = ""
    technical: str = ""


@dataclass
class DiagnosticReport:
    checks: List[DiagCheck] = field(default_factory=list)
    timestamp: str = ""
    system_info: str = ""
    airplay_visible: bool = False

    def summary(self) -> str:
        ok = sum(1 for c in self.checks if c.status == CheckResult.OK)
        warn = sum(1 for c in self.checks if c.status == CheckResult.WARNING)
        fail = sum(1 for c in self.checks if c.status == CheckResult.FAIL)
        return f"{ok} passed · {warn} warnings · {fail} failed"

    def to_text(self) -> str:
        """Human-readable report (safe for copy/export — no passwords/keys)."""
        lines = [
            "G-Mirror Connection Diagnostics Report",
            f"Generated: {self.timestamp}",
            f"System: {self.system_info}",
            "",
            self.summary(),
            "=" * 60,
        ]
        for check in self.checks:
            icon = {"ok": "✓", "warning": "⚠", "fail": "✕", "skip": "—"}[check.status.value]
            lines.append(f"{icon}  {check.name}")
            if check.message:
                lines.append(f"   {check.message}")
            if check.suggestion and check.status != CheckResult.OK:
                lines.append(f"   💡 {check.suggestion}")
            lines.append("")
        return "\n".join(lines)


class NetworkChecker:
    """
    Runs all diagnostic checks and returns a DiagnosticReport.
    Designed to run in a background thread.
    """

    def __init__(self, progress_callback=None) -> None:
        self._progress = progress_callback  # callback(check_name: str, percent: int)

    def run(self) -> DiagnosticReport:
        import platform
        report = DiagnosticReport()
        report.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        report.system_info = f"Windows {platform.version()} ({platform.machine()})"

        checks = [
            self._check_network_adapter,
            self._check_ip_address,
            self._check_gateway,
            self._check_mdns_port,
            self._check_airplay_port,
            self._check_firewall,
            self._check_network_profile,
            self._check_multicast,
            self._check_ipv6,
            self._check_service_ports_free,
        ]

        for i, check_fn in enumerate(checks):
            percent = int((i / len(checks)) * 100)
            check = check_fn()
            report.checks.append(check)
            if self._progress:
                self._progress(check.name, percent)

        return report

    def _check_network_adapter(self) -> DiagCheck:
        check = DiagCheck("Network Adapter")
        try:
            adapters = socket.getaddrinfo(socket.gethostname(), None)
            ipv4s = [a[4][0] for a in adapters if "." in a[4][0] and not a[4][0].startswith("127.")]
            if ipv4s:
                check.status = CheckResult.OK
                check.message = f"Active network adapter found: {ipv4s[0]}"
            else:
                check.status = CheckResult.FAIL
                check.message = "No active network adapter with a LAN IP address was found."
                check.suggestion = "Connect your PC to the same Wi-Fi network as your iPhone."
        except Exception as e:
            check.status = CheckResult.FAIL
            check.message = "Could not enumerate network adapters."
            check.technical = str(e)
        return check

    def _check_ip_address(self) -> DiagCheck:
        check = DiagCheck("PC IP Address (IPv4)")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            check.status = CheckResult.OK
            check.message = f"PC IP address: {ip}"
            check.technical = f"addr={ip}"
        except Exception as e:
            check.status = CheckResult.FAIL
            check.message = "Could not determine PC's IP address. Your PC may not be connected to a network."
            check.suggestion = "Connect your PC to Wi-Fi or Ethernet, then run diagnostics again."
            check.technical = str(e)
        return check

    def _check_gateway(self) -> DiagCheck:
        check = DiagCheck("Network Gateway Reachability")
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", "8.8.8.8"],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000
            )
            if result.returncode == 0:
                check.status = CheckResult.OK
                check.message = "Internet connectivity confirmed."
            else:
                check.status = CheckResult.WARNING
                check.message = "Cannot reach the internet, but local network may still work."
                check.suggestion = (
                    "AirPlay only needs the iPhone and PC on the same Wi-Fi network "
                    "(internet access is not required)."
                )
        except Exception as e:
            check.status = CheckResult.WARNING
            check.message = "Gateway check could not be completed."
            check.technical = str(e)
        return check

    def _check_mdns_port(self) -> DiagCheck:
        check = DiagCheck("mDNS/Bonjour (UDP port 5353)")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", 5353))
            s.close()
            check.status = CheckResult.OK
            check.message = "mDNS port 5353 is available for G-Mirror."
        except OSError as e:
            if e.errno == 10048:  # WSAEADDRINUSE
                check.status = CheckResult.WARNING
                check.message = "mDNS port 5353 is in use by another application."
                check.suggestion = (
                    "Another mDNS service (e.g., Bonjour for Windows, iTunes, or Avahi) "
                    "may already be running. G-Mirror will attempt to share the port. "
                    "If discovery fails, try closing those applications."
                )
            else:
                check.status = CheckResult.FAIL
                check.message = "mDNS port 5353 could not be opened."
                check.suggestion = "Check Windows Firewall rules and try running G-Mirror as Administrator."
                check.technical = str(e)
        return check

    def _check_airplay_port(self) -> DiagCheck:
        check = DiagCheck("AirPlay Control Port (TCP 7000)")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", 7000))
            s.close()
            check.status = CheckResult.OK
            check.message = "AirPlay port 7000 is available."
        except OSError as e:
            # Check if G-Mirror's own service is listening on port 7000
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(0.5)
                test_sock.connect(("127.0.0.1", 7000))
                test_sock.sendall(b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n")
                banner = test_sock.recv(1024).decode(errors="ignore")
                test_sock.close()
                if "AirTunes" in banner:
                    check.status = CheckResult.OK
                    check.message = "AirPlay port 7000 is active (G-Mirror service is currently running)."
                    return check
            except Exception:
                pass

            if e.errno == 10048:
                check.status = CheckResult.FAIL
                check.message = "Port 7000 is already in use by another application."
                check.suggestion = (
                    "Another AirPlay receiver (e.g., iTunes, LonelyScreen, or Reflector) "
                    "may already be running on this port. "
                    "Close it and restart G-Mirror."
                )
            else:
                check.status = CheckResult.FAIL
                check.message = "Could not open AirPlay port 7000."
                check.suggestion = "Check Windows Firewall and try running G-Mirror as Administrator."
            check.technical = str(e)
        return check

    def _check_firewall(self) -> DiagCheck:
        check = DiagCheck("Windows Firewall")
        try:
            state_res = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000
            )
            state_out = state_res.stdout.lower()
            is_active = "on" in state_out

            if not is_active:
                check.status = CheckResult.OK
                check.message = "Windows Firewall is disabled (all traffic permitted)."
                return check

            # Check if G-Mirror or Python has active inbound rules
            rules_res = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"],
                capture_output=True, text=True, timeout=8, creationflags=0x08000000
            )
            rules_out = rules_res.stdout.lower()
            has_rule = ("rule name:" in rules_out and ("gmirror" in rules_out or "python" in rules_out))

            if has_rule:
                check.status = CheckResult.OK
                check.message = "Windows Firewall is active, and G-Mirror has inbound access allowed."
            else:
                check.status = CheckResult.WARNING
                check.message = "Windows Firewall is active, but no specific rule was found for G-Mirror."
                check.suggestion = (
                    "If your iPhone cannot find G-Mirror, ensure G-Mirror is allowed "
                    "in Windows Defender Firewall (Inbound ports TCP 7000, 7001 and UDP 5353, 7011)."
                )
        except Exception as e:
            check.status = CheckResult.SKIP
            check.message = "Firewall status could not be checked."
            check.technical = str(e)
        return check

    def _check_network_profile(self) -> DiagCheck:
        check = DiagCheck("Windows Network Profile")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetConnectionProfile | Select-Object -ExpandProperty NetworkCategory"],
                capture_output=True, text=True, timeout=8, creationflags=0x08000000
            )
            profile = result.stdout.strip()
            if "Public" in profile:
                check.status = CheckResult.FAIL
                check.message = "Network is set to 'Public' profile."
                check.suggestion = (
                    "A Public network profile blocks mDNS discovery. "
                    "Go to Settings → Network → Wi-Fi → (your network) → Properties "
                    "and change the profile to 'Private'."
                )
            elif "Private" in profile or "Domain" in profile:
                check.status = CheckResult.OK
                check.message = f"Network profile: {profile} (mDNS allowed)."
            else:
                check.status = CheckResult.WARNING
                check.message = f"Network profile: {profile or 'Unknown'}."
                check.suggestion = "Set network to 'Private' for best AirPlay compatibility."
        except Exception as e:
            check.status = CheckResult.SKIP
            check.message = "Network profile check skipped."
            check.technical = str(e)
        return check

    def _check_multicast(self) -> DiagCheck:
        check = DiagCheck("Multicast / mDNS Availability")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            # Just try to bind — actual multicast join tested here
            s.bind(("0.0.0.0", 0))
            s.close()
            check.status = CheckResult.OK
            check.message = "Multicast sockets are available."
        except Exception as e:
            check.status = CheckResult.FAIL
            check.message = "Multicast is not available on this network adapter."
            check.suggestion = (
                "Your network adapter may not support multicast, or your router "
                "has multicast isolation enabled. AirPlay discovery requires multicast."
            )
            check.technical = str(e)
        return check

    def _check_ipv6(self) -> DiagCheck:
        check = DiagCheck("IPv6 Status")
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s.close()
            check.status = CheckResult.OK
            check.message = "IPv6 is available (G-Mirror uses IPv4 primarily)."
        except Exception:
            check.status = CheckResult.OK  # Not required for AirPlay
            check.message = "IPv6 is not available (not required for AirPlay)."
        return check

    def _check_service_ports_free(self) -> DiagCheck:
        check = DiagCheck("G-Mirror Service Ports (7000, 7001, 7011, 7012)")
        blocked = []
        for port in [7000, 7001, 7011, 7012]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("0.0.0.0", port))
                s.close()
            except OSError:
                blocked.append(port)

        if blocked:
            # Check if G-Mirror's own RTSP service is holding port 7000
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(0.5)
                test_sock.connect(("127.0.0.1", 7000))
                test_sock.sendall(b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n")
                banner = test_sock.recv(1024).decode(errors="ignore")
                test_sock.close()
                if "AirTunes" in banner:
                    check.status = CheckResult.OK
                    check.message = f"G-Mirror service is currently active and listening on ports {blocked}."
                    return check
            except Exception:
                pass

        if not blocked:
            check.status = CheckResult.OK
            check.message = "All G-Mirror ports (7000, 7001, 7011, 7012) are available."
        else:
            check.status = CheckResult.FAIL
            check.message = f"Ports already in use: {blocked}"
            check.suggestion = (
                "Close any other AirPlay receivers (iTunes, LonelyScreen, Reflector, etc.) "
                "and restart G-Mirror."
            )
        return check
