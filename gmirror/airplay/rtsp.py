"""
G-Mirror RTSP Protocol Parser.

AirPlay uses a custom RTSP/HTTP hybrid protocol on port 7000.
Requests look like HTTP but with RTSP method names (OPTIONS, SETUP, RECORD, etc.)
and binary plist payloads.

Protocol Reference: openairplay/airplay2-receiver (MIT License)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class RTSPRequest:
    method: str = ""
    path: str = ""
    version: str = "RTSP/1.0"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    cseq: int = 0

    @classmethod
    def parse(cls, raw: bytes) -> Optional["RTSPRequest"]:
        """Parse raw bytes into an RTSPRequest. Returns None on failure."""
        try:
            # Split header block from body
            if b"\r\n\r\n" in raw:
                header_block, body = raw.split(b"\r\n\r\n", 1)
            else:
                header_block = raw
                body = b""

            lines = header_block.decode("utf-8", errors="replace").split("\r\n")
            if not lines:
                return None

            request_line = lines[0].split(" ", 2)
            if len(request_line) < 2:
                return None

            req = cls()
            req.method = request_line[0].upper()
            req.path = request_line[1] if len(request_line) > 1 else "/"
            req.version = request_line[2] if len(request_line) > 2 else "RTSP/1.0"

            for line in lines[1:]:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    req.headers[k.strip()] = v.strip()

            req.cseq = int(req.headers.get("CSeq", "0"))

            # Respect Content-Length header
            content_length = int(req.headers.get("Content-Length", len(body)))
            req.body = body[:content_length]

            return req
        except Exception as e:
            log.debug("RTSP parse error: %s", e)
            return None


@dataclass
class RTSPResponse:
    status_code: int = 200
    status_text: str = "OK"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def build(self, cseq: int = 0) -> bytes:
        """Serialize to wire format."""
        self.headers["CSeq"] = str(cseq)
        if self.body:
            self.headers["Content-Length"] = str(len(self.body))

        lines = [f"RTSP/1.0 {self.status_code} {self.status_text}"]
        for k, v in self.headers.items():
            lines.append(f"{k}: {v}")
        lines.append("")
        header = "\r\n".join(lines) + "\r\n"
        return header.encode("utf-8") + self.body


class RTSPBuffer:
    """
    Accumulates incoming TCP bytes and extracts complete RTSP requests.
    AirPlay reuses the TCP connection for multiple sequential requests.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[RTSPRequest]:
        """Feed bytes; return list of complete parsed requests."""
        self._buf.extend(data)
        requests: list[RTSPRequest] = []

        while True:
            result = self._try_extract()
            if result is None:
                break
            req, consumed = result
            if req:
                requests.append(req)
            del self._buf[:consumed]

        return requests

    def _try_extract(self) -> Optional[Tuple[Optional[RTSPRequest], int]]:
        separator = b"\r\n\r\n"
        idx = self._buf.find(separator)
        if idx == -1:
            return None  # Need more data

        header_end = idx + len(separator)
        header_block = bytes(self._buf[:idx])

        # Parse content-length from headers
        content_length = 0
        for line in header_block.decode("utf-8", errors="replace").split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        total_needed = header_end + content_length
        if len(self._buf) < total_needed:
            return None  # Body not yet received

        raw = bytes(self._buf[:total_needed])
        req = RTSPRequest.parse(raw)
        return req, total_needed
