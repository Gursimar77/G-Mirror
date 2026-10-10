"""
G-Mirror AirPlay RTSP Server.

Implements the AirPlay control channel — a custom RTSP/HTTP hybrid
server on port 7000 that handles the full AirPlay mirroring session
negotiation with iOS.

Flow:
  OPTIONS → GET /info → POST /fp-setup (×2–3) → SETUP → RECORD
  → SET_PARAMETER (volume, etc.) → TEARDOWN

Protocol Reference:
  - openairplay/airplay2-receiver (MIT License)
  - AirPlay2 protocol documentation (community reverse-engineering)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import plistlib
import socket
import threading
import time
from typing import Any, Dict, Optional

from gmirror.airplay.fairplay import FairPlayHandshake
from gmirror.airplay.rtsp import RTSPBuffer, RTSPRequest, RTSPResponse
from gmirror.airplay.session import AirPlaySession, SessionState

log = logging.getLogger(__name__)

# Port assignments
AIRPLAY_CONTROL_PORT = 7000
AIRPLAY_VIDEO_PORT   = 7001
AIRPLAY_AUDIO_PORT   = 7011
AIRPLAY_TIMING_PORT  = 7012

# Server info plist returned to iOS
_SERVER_INFO = {
    "deviceid": "",       # filled at runtime
    "macAddress": "",     # filled at runtime
    "name": "G-Mirror",
    "features": 0x527FFFF7,
    "model": "AppleTV3,2",
    "srcvers": "377.17.10.0",
    "sourceVersion": "377.17.10.0",
    "vv": 2,
    "statusFlags": 68,
    "keepAliveLowPower": 1,
    "keepAliveSendStatsAsBody": 1,
    "initialVolume": 0.0,
    "pi": "2e388006-13ba-4041-9a67-25dd4a43d536",
    "pk": b"\xb0\x77\x27\xd6\xf6\xcd\x65\xbc"
          b"\x38\xe4\x9e\x10\xf3\xd8\x7c\xbc"
          b"\x8b\x3e\x55\xfa\x9d\xed\x6c\xde"
          b"\xd6\x3a\x55\xe7\xfe\x07\xed\xdd",
    "displays": [
        {
            "width": 1920,
            "height": 1080,
            "widthPixels": 1920,
            "heightPixels": 1080,
            "widthPhysical": 0,
            "heightPhysical": 0,
            "rotation": True,
            "refreshRate": 60,
            "maxFPS": 60,
            "overscanned": False,
            "features": 14,
            "uuid": "e0ff8a27-6738-3d56-8a16-cc53aacee925",
        }
    ],
    "audioFormats": [
        {
            "type": 100,
            "audioInputFormats": 0x3FFFFFC,
            "audioOutputFormats": 0x3FFFFFC,
        },
        {
            "type": 101,
            "audioInputFormats": 0x3FFFFFC,
            "audioOutputFormats": 0x3FFFFFC,
        },
    ],
    "audioLatencies": [
        {
            "type": 100,
            "audioType": "default",
            "inputLatencyMicros": 0,
            "outputLatencyMicros": 0,
        },
        {
            "type": 101,
            "audioType": "default",
            "inputLatencyMicros": 0,
            "outputLatencyMicros": 0,
        },
    ],
}


class AirPlayClientHandler:
    """Handles one connected iOS device."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session: AirPlaySession,
        video_port: int,
        audio_port: int,
        video_receiver: Optional[Any] = None,
        audio_receiver: Optional[Any] = None,
        audio_output: Optional[Any] = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._session = session
        self._video_port = video_port
        self._audio_port = audio_port
        self._video_receiver = video_receiver
        self._audio_receiver = audio_receiver
        self._audio_output = audio_output
        self._fp = FairPlayHandshake()
        self._aes_key: Optional[bytes] = None
        self._aes_iv: Optional[bytes] = None
        self._stream_connection_id: Optional[Any] = None
        self._buf = RTSPBuffer()
        self._peer = writer.get_extra_info("peername", ("?", 0))
        self._device_name = "iPhone"

    async def handle(self) -> None:
        log.info("AirPlay connection from %s", self._peer)
        if self._session.state != SessionState.STREAMING:
            self._session.set_connecting(self._device_name)

        # Enable TCP keepalive and disable Nagle's algorithm on RTSP/event sockets
        sock = self._writer.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except Exception:
                pass

        try:
            while True:
                try:
                    # IMPORTANT: The iPhone opens a second passive connection to eventPort (7000)
                    # that sends 0 bytes for the entire mirroring session. A read timeout MUST
                    # continue waiting rather than closing the socket, otherwise the iPhone aborts
                    # the mirroring session after 30 seconds!
                    chunk = await asyncio.wait_for(self._reader.read(65536), timeout=30.0)
                except asyncio.TimeoutError:
                    continue
                if not chunk:
                    break
                requests = self._buf.feed(chunk)
                for req in requests:
                    response = await self._dispatch(req)
                    if response:
                        data = response.build(req.cseq)
                        self._writer.write(data)
                        await self._writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            log.debug("Client handler error: %s", e)
        finally:
            log.info("AirPlay client %s disconnected", self._peer)
            try:
                self._writer.close()
            except Exception:
                pass

    async def _dispatch(self, req: RTSPRequest) -> Optional[RTSPResponse]:
        log.debug("→ %s %s", req.method, req.path)
        method = req.method.upper()
        path = req.path.lower()

        if method == "OPTIONS":
            return self._handle_options(req)
        elif method == "GET" and path == "/info":
            return self._handle_get_info(req)
        elif method == "POST" and path == "/fp-setup":
            return self._handle_fp_setup(req)
        elif method == "POST" and (path == "/pair-setup" or path == "/pair-setup-pin"):
            return self._handle_pair_setup(req)
        elif method == "POST" and path == "/pair-verify":
            return self._handle_pair_verify(req)
        elif method == "SETUP":
            return self._handle_setup(req)
        elif method == "GET_PARAMETER":
            return self._handle_get_parameter(req)
        elif method == "SET_PARAMETER":
            return self._handle_set_parameter(req)
        elif method == "RECORD":
            return self._handle_record(req)
        elif method == "POST" and path == "/feedback":
            log.debug("Received AirPlay /feedback ping")
            return RTSPResponse(200, "OK", {"Server": "AirTunes/377.17.10.0"})
        elif method == "POST" and path == "/audiomode":
            return RTSPResponse(200, "OK", {"Server": "AirTunes/377.17.10.0"})
        elif method == "TEARDOWN":
            return self._handle_teardown(req)
        elif method == "FLUSH":
            return RTSPResponse(200, "OK", {"Server": "AirTunes/377.17.10.0"})
        else:
            log.debug("Unhandled method: %s %s", method, req.path)
            return RTSPResponse(200, "OK", {"Server": "AirTunes/377.17.10.0"})

    def _handle_pair_setup(self, req: RTSPRequest) -> RTSPResponse:
        log.info("Handling pair-setup from %s (len=%d)", self._peer, len(req.body))
        self._session.set_authenticating()
        pk = _SERVER_INFO["pk"][:32]
        content_type = req.headers.get("Content-Type", "")
        if "plist" in content_type:
            resp_body = plistlib.dumps({"pk": pk}, fmt=plistlib.FMT_BINARY)
            return RTSPResponse(
                200, "OK",
                {
                    "Content-Type": "application/x-apple-binary-plist",
                    "Server": "AirTunes/377.17.10.0",
                },
                body=resp_body,
            )
        else:
            return RTSPResponse(
                200, "OK",
                {
                    "Content-Type": "application/octet-stream",
                    "Server": "AirTunes/377.17.10.0",
                },
                body=pk,
            )

    def _handle_pair_verify(self, req: RTSPRequest) -> RTSPResponse:
        log.info("Handling pair-verify from %s (len=%d)", self._peer, len(req.body))
        # Phase 1: 68-byte request -> 96-byte reply (32 bytes pk + 64 bytes signature)
        if len(req.body) == 68:
            flag = req.body[0] if len(req.body) > 0 else 1
            if flag == 1:
                pk = _SERVER_INFO["pk"][:32]
                sig = b"\x00" * 64
                return RTSPResponse(
                    200, "OK",
                    {
                        "Content-Type": "application/octet-stream",
                        "Server": "AirTunes/377.17.10.0",
                    },
                    body=pk + sig,
                )
        return RTSPResponse(
            200, "OK",
            {
                "Content-Type": "application/octet-stream",
                "Server": "AirTunes/377.17.10.0",
            },
        )

    def _handle_options(self, req: RTSPRequest) -> RTSPResponse:
        return RTSPResponse(
            200, "OK",
            {
                "Public": "ANNOUNCE, SETUP, RECORD, PAUSE, FLUSH, TEARDOWN, "
                          "OPTIONS, GET_PARAMETER, SET_PARAMETER, POST, GET",
                "Server": "AirTunes/377.17.10.0",
                "Apple-Jack-Status": "connected; type=analog",
            },
        )

    def _handle_get_info(self, req: RTSPRequest) -> RTSPResponse:
        info = dict(_SERVER_INFO)
        # Fill deviceid from mDNS advertiser device id
        from gmirror.airplay.mdns import _make_device_id
        info["deviceid"] = _make_device_id()

        # Respect user's configured resolution & FPS in /info display descriptor
        try:
            from gmirror.settings.config import get_config
            vcfg = get_config().video
            w, h = 1920, 1080
            if vcfg.resolution == "720p":
                w, h = 1280, 720
            elif vcfg.quality == "Maximum":
                w, h = 2560, 1440
            fps = 30 if vcfg.fps_cap == "30" else 60
            disp = dict(_SERVER_INFO["displays"][0])
            disp.update({
                "width": w,
                "height": h,
                "widthPixels": w,
                "heightPixels": h,
                "refreshRate": fps,
                "maxFPS": fps,
            })
            info["displays"] = [disp]
        except Exception:
            pass

        body = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
        return RTSPResponse(
            200, "OK",
            {
                "Content-Type": "application/x-apple-binary-plist",
                "Server": "AirTunes/377.17.10.0",
            },
            body=body,
        )

    def _handle_fp_setup(self, req: RTSPRequest) -> RTSPResponse:
        self._session.set_authenticating()
        response_body = self._fp.process(req.body)
        if response_body is None:
            return RTSPResponse(500, "Internal Server Error")
        return RTSPResponse(
            200, "OK",
            {
                "Content-Type": "application/octet-stream",
                "Server": "AirTunes/377.17.10.0",
            },
            body=response_body,
        )

    def _handle_setup(self, req: RTSPRequest) -> RTSPResponse:
        """
        iOS sends SETUP with a plist body describing the stream type.
        We respond with port assignments for video and audio.
        """
        try:
            if req.body:
                params = plistlib.loads(req.body)
            else:
                params = {}
        except Exception:
            params = {}

        log.debug("SETUP params: %s", list(params.keys()))

        # Extract device name if provided in headers or plist
        if "X-Apple-Device-Name" in req.headers:
            self._device_name = req.headers["X-Apple-Device-Name"]
            self._session.update_stats(connected_device=self._device_name)
        elif isinstance(params.get("name"), str) and params["name"]:
            self._device_name = params["name"]
            self._session.update_stats(connected_device=self._device_name)

        if "eiv" in params and isinstance(params["eiv"], (bytes, bytearray)) and len(params["eiv"]) >= 16:
            self._aes_iv = bytes(params["eiv"][:16])

        # Handle FairPlay ekey if present (72-byte encrypted session key)
        if "ekey" in params:
            ekey = params["ekey"]
            if isinstance(ekey, (bytes, bytearray)):
                decrypted = self._fp.decrypt_aes_key(bytes(ekey))
                if decrypted:
                    self._aes_key = decrypted
                    log.info("AirPlay SETUP: decrypted master AES key (%s...)", decrypted[:4].hex())
                    if self._video_receiver:
                        sid = self._stream_connection_id if self._stream_connection_id is not None else 0
                        v_key = hashlib.sha512(f"AirPlayStreamKey{sid}".encode("utf-8") + self._aes_key).digest()[:16]
                        v_iv = hashlib.sha512(f"AirPlayStreamIV{sid}".encode("utf-8") + self._aes_key).digest()[:16]
                        if sid == 0 and self._aes_iv:
                            v_iv = self._aes_iv
                        self._video_receiver.init_aes(v_key, v_iv)
                        log.info("Initialized VideoReceiver AES-CTR from ekey (connID=%s)", sid)
                    if self._audio_receiver and self._aes_iv:
                        self._audio_receiver.init_aes(self._aes_key, self._aes_iv)

        response_params = {
            "eventPort": AIRPLAY_CONTROL_PORT,
            "timingPort": AIRPLAY_TIMING_PORT,
        }

        # If this is a stream-specific SETUP request (contains "streams" key)
        streams = params.get("streams", [])
        if streams:
            response_streams = []
            for s in streams:
                stream_type = s.get("type", 0)
                if stream_type == 110:  # Screen mirroring
                    stream_conn_id = s.get("streamConnectionID")
                    if stream_conn_id is not None:
                        self._stream_connection_id = stream_conn_id

                    if self._aes_key and self._video_receiver:
                        sid = self._stream_connection_id if self._stream_connection_id is not None else 0
                        v_key = hashlib.sha512(f"AirPlayStreamKey{sid}".encode("utf-8") + self._aes_key).digest()[:16]
                        v_iv = hashlib.sha512(f"AirPlayStreamIV{sid}".encode("utf-8") + self._aes_key).digest()[:16]
                        self._video_receiver.init_aes(v_key, v_iv)
                        log.info("Initialized VideoReceiver AES-CTR for stream 110 (connID=%s)", sid)

                    response_streams.append({
                        "type": 110,
                        "dataPort": self._video_port,
                        "controlPort": self._video_port + 1,
                    })
                elif stream_type == 96:  # Audio
                    log.info("SETUP audio stream 96: ct=%s, audioFormat=%s, spf=%s, sr=%s",
                             s.get("ct"), s.get("audioFormat"), s.get("spf"), s.get("sr"))
                    if self._audio_receiver:
                        a_key = self._aes_key
                        a_iv = self._aes_iv
                        if "ekey" in s and isinstance(s["ekey"], (bytes, bytearray)):
                            dec = self._fp.decrypt_aes_key(bytes(s["ekey"]))
                            if dec:
                                a_key = dec
                        if "eiv" in s and isinstance(s["eiv"], (bytes, bytearray)) and len(s["eiv"]) >= 16:
                            a_iv = bytes(s["eiv"][:16])
                        if a_key and a_iv:
                            self._audio_receiver.init_aes(a_key, a_iv)
                        ct = s.get("ct")
                        if ct == 2:
                            self._audio_receiver.set_codec("alac")
                        elif ct == 1:
                            self._audio_receiver.set_codec("pcm")
                        elif ct in (4, 8):
                            self._audio_receiver.set_codec("aac-eld")

                    response_streams.append({
                        "type": 96,
                        "dataPort": self._audio_port,
                        "controlPort": self._audio_port + 1,
                    })
            response_params["streams"] = response_streams

        resp_headers = {
            "Content-Type": "application/x-apple-binary-plist",
            "Server": "AirTunes/377.17.10.0",
            "Session": "GMIRROR0001",
        }
        if "Transport" in req.headers:
            resp_headers["Transport"] = req.headers["Transport"]

        body = plistlib.dumps(response_params, fmt=plistlib.FMT_BINARY)
        return RTSPResponse(200, "OK", resp_headers, body=body)

    def _handle_get_parameter(self, req: RTSPRequest) -> RTSPResponse:
        body_text = req.body.decode("utf-8", errors="replace").strip()
        response_lines = []
        if "volume" in body_text or not body_text:
            response_lines.append("volume: 0.0")
        resp_body = ("\r\n".join(response_lines) + "\r\n").encode()
        return RTSPResponse(
            200, "OK",
            {
                "Content-Type": "text/parameters",
                "Server": "AirTunes/377.17.10.0",
                "Session": "GMIRROR0001",
            },
            body=resp_body,
        )

    def _handle_set_parameter(self, req: RTSPRequest) -> RTSPResponse:
        content_type = req.headers.get("Content-Type", "")
        if "text/parameters" in content_type:
            for line in req.body.decode("utf-8", errors="replace").splitlines():
                if line.lower().startswith("volume:"):
                    try:
                        vol_db = float(line.split(":", 1)[1].strip())
                        log.debug("Volume: %.1f dB", vol_db)
                        if self._audio_output:
                            # AirPlay sends volume in dB: -144.0 = mute, -30.0..0.0 = active range
                            if vol_db <= -30.0:
                                self._audio_output.set_volume(0.0)
                            else:
                                linear = max(0.0, min(1.0, (vol_db + 30.0) / 30.0))
                                self._audio_output.set_volume(linear)
                    except ValueError:
                        pass
        return RTSPResponse(200, "OK", {"Server": "AirTunes/377.17.10.0"})

    def _handle_record(self, req: RTSPRequest) -> RTSPResponse:
        self._session.set_streaming()
        return RTSPResponse(
            200, "OK",
            {
                "Audio-Latency": "0",
                "Server": "AirTunes/377.17.10.0",
                "Session": "GMIRROR0001",
            },
        )

    def _handle_teardown(self, req: RTSPRequest) -> RTSPResponse:
        # iOS sends TEARDOWN with {"streams": [{"type": 96}]} when closing only audio.
        # Only mark the session disconnected if video (type 110) or the whole session is torn down.
        disconnect_session = True
        if req.body:
            try:
                params = plistlib.loads(req.body)
                streams = params.get("streams")
                if isinstance(streams, list) and streams:
                    types = {s.get("type") for s in streams if isinstance(s, dict)}
                    if 110 not in types:
                        disconnect_session = False
                        log.info("TEARDOWN for non-video stream(s) %s — keeping mirroring active", types)
            except Exception:
                pass
        if disconnect_session:
            self._session.set_disconnected()
        return RTSPResponse(200, "OK", {"Server": "AirTunes/377.17.10.0"})


class AirPlayServer:
    """
    Main AirPlay RTSP server.

    Runs an asyncio TCP server on port 7000.
    Accepts one connection at a time (iOS sends one mirroring session).
    """

    def __init__(
        self,
        session: AirPlaySession,
        video_receiver: Optional[Any] = None,
        audio_receiver: Optional[Any] = None,
        audio_output: Optional[Any] = None,
    ) -> None:
        self._session = session
        self._video_receiver = video_receiver
        self._audio_receiver = audio_receiver
        self._audio_output = audio_output
        self._server: Optional[asyncio.AbstractServer] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._host = "0.0.0.0"
        self._video_port = AIRPLAY_VIDEO_PORT
        self._audio_port = AIRPLAY_AUDIO_PORT
        self._active_connections = 0

    def start(self, host: str = "0.0.0.0", port: int = AIRPLAY_CONTROL_PORT) -> bool:
        if self._running:
            return True
        self._host = host
        self._thread = threading.Thread(
            target=self._run_loop, args=(port,), daemon=True, name="AirPlayServer"
        )
        self._thread.start()
        # Give the loop a moment to start
        time.sleep(0.3)
        log.info("AirPlay server starting on %s:%d", host, port)
        return True

    def _run_loop(self, port: int) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve(port))
        except Exception as e:
            log.error("AirPlay server loop error: %s", e)
        finally:
            self._loop.close()

    async def _serve(self, port: int) -> None:
        self._server = await asyncio.start_server(
            self._client_connected, self._host, port
        )
        self._running = True
        log.info("AirPlay RTSP server listening on port %d", port)
        async with self._server:
            await self._server.serve_forever()

    async def _client_connected(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._active_connections += 1
        handler = AirPlayClientHandler(
            reader, writer, self._session,
            self._video_port, self._audio_port,
            video_receiver=self._video_receiver,
            audio_receiver=self._audio_receiver,
            audio_output=self._audio_output,
        )
        try:
            await handler.handle()
        finally:
            self._active_connections -= 1
            if self._active_connections <= 0:
                self._session.set_disconnected()

    def stop(self) -> None:
        self._running = False
        if self._server and self._loop:
            self._loop.call_soon_threadsafe(self._server.close)
        log.info("AirPlay server stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
