"""
G-Mirror AirPlay Video Receiver.

Receives the H.264 video stream from iOS on a dedicated TCP connection.
Each video packet has a 128-byte header containing timestamps and
presentation metadata, followed by raw H.264 NAL units.

Protocol Reference:
  - openairplay/airplay2-receiver (MIT)
  - AirPlay mirroring protocol reverse-engineering (public domain research)
"""

from __future__ import annotations

import logging
import queue
import socket
import struct
import threading
import time
from typing import Callable, Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

log = logging.getLogger(__name__)

# Video packet header size (bytes) — AirPlay mirroring protocol
VIDEO_HEADER_SIZE = 128

# Maximum compressed packet queue depth — must be large enough so encoded H.264
# P-frames are NEVER dropped before FFmpeg decodes them (dropping a compressed
# P-frame corrupts the H.264 reference frame buffer and causes broken pixels).
FRAME_QUEUE_MAXSIZE = 600


class VideoFrame:
    """A decoded H.264 NAL unit payload with timing information."""

    __slots__ = ("data", "timestamp", "received_at", "sequence", "is_idr")

    def __init__(self, data: bytes, timestamp: float, sequence: int, is_idr: bool = False) -> None:
        self.data = data
        self.timestamp = timestamp
        self.received_at = time.perf_counter()
        self.sequence = sequence
        self.is_idr = is_idr


FrameCallback = Callable[[VideoFrame], None]


class VideoReceiver(threading.Thread):
    """
    Listens on a TCP port for the iPhone's H.264 video stream.

    The AirPlay server tells iOS which port to connect to during SETUP.
    This receiver runs in a background thread and pushes VideoFrames
    into a queue for the decoder thread to consume.
    """

    def __init__(
        self,
        host: str,
        port: int,
        frame_queue: Optional[queue.Queue] = None,
    ) -> None:
        super().__init__(name="VideoReceiver", daemon=True)
        self._host = host
        self._port = port
        self._frame_queue: queue.Queue = frame_queue or queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
        self._stop_event = threading.Event()
        self._sequence = 0
        self._server_sock: Optional[socket.socket] = None
        self._client_sock: Optional[socket.socket] = None
        self._dropped_frames = 0
        self._total_frames = 0
        self._bytes_received = 0
        self._window_bytes = 0
        self._window_start = time.perf_counter()
        self._current_bitrate_kbps = 0.0
        self._start_time = 0.0
        self._sps_pps: Optional[bytes] = None
        self._prepend_sps_pps: bool = False
        self._aes_key: Optional[bytes] = None
        self._aes_iv: Optional[bytes] = None
        self._decryptor = None
        self._cipher_lock = threading.Lock()

    def init_aes(self, key: bytes, iv: bytes) -> None:
        """Initialize AES-128-CTR stream cipher for decrypting video payloads."""
        with self._cipher_lock:
            self._aes_key = key
            self._aes_iv = iv
            cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
            self._decryptor = cipher.decryptor()
        log.info(
            "VideoReceiver: AES-CTR initialized (key=%s..., iv=%s...)",
            key[:4].hex() if key else "none",
            iv[:4].hex() if iv else "none",
        )

    def _enqueue_frame(self, frame: VideoFrame) -> None:
        try:
            self._frame_queue.put_nowait(frame)
        except queue.Full:
            # Only if the queue is completely saturated (e.g. >600 frames):
            # If the incoming frame is an IDR keyframe, we can safely clear old P-frames.
            if frame.is_idr:
                while not self._frame_queue.empty():
                    try:
                        self._frame_queue.get_nowait()
                        self._dropped_frames += 1
                    except queue.Empty:
                        break
                self._frame_queue.put_nowait(frame)
            else:
                try:
                    self._frame_queue.put(frame, timeout=0.05)
                except queue.Full:
                    self._dropped_frames += 1

    def _parse_packets(self, buf: bytearray) -> None:
        """
        Extract complete packets from buffer and queue decoded frames.
        AirPlay mirror protocol packet layout:
          Offset 0..3:   uint32 payload_size (Little-Endian <I)
          Offset 4:      uint8 packet_type (0 = video, 1 = SPS/PPS, 2 = keepalive, 5 = report)
          Offset 5:      uint8 payload_flags (0x10 = IDR keyframe)
          Offset 6:      uint8 payload_option (0x56/0x5e = stream pause)
          Offset 8..15:  uint64 ntp_timestamp (Little-Endian <Q)
          Offset 16..127: metadata
        """
        ANNEX_B = b"\x00\x00\x00\x01"

        while len(buf) >= VIDEO_HEADER_SIZE:
            payload_size = struct.unpack_from("<I", buf, 0)[0]

            # Stream desync protection: maximum single frame size ~16MB
            if payload_size > 16 * 1024 * 1024:
                log.warning("VideoReceiver: payload size %d too large; realigning stream", payload_size)
                del buf[:1]
                continue

            total_size = VIDEO_HEADER_SIZE + payload_size
            if len(buf) < total_size:
                break  # Wait for remaining packet data

            packet_type = buf[4]
            payload_flags = buf[5]
            payload_option = buf[6]
            payload = bytes(buf[VIDEO_HEADER_SIZE:total_size])
            del buf[:total_size]

            if not payload or payload_size == 0:
                continue

            now = time.perf_counter()

            if packet_type == 1:
                # SPS and PPS parameter sets (unencrypted)
                # Note: payload_option 0x56 / 0x5e indicates client screen sleep/stop
                if payload_option in (0x56, 0x5E):
                    log.debug("AirPlay client signaled video pause (option=0x%02x)", payload_option)
                if len(payload) >= 12:
                    try:
                        sps_size = struct.unpack_from(">H", payload, 6)[0]
                        sps = payload[8 : 8 + sps_size]
                        pps_offset = sps_size + 9
                        if pps_offset + 2 <= len(payload):
                            pps_size = struct.unpack_from(">H", payload, pps_offset)[0]
                            pps = payload[pps_offset + 2 : pps_offset + 2 + pps_size]
                            if sps and pps:
                                self._sps_pps = ANNEX_B + sps + ANNEX_B + pps
                                self._prepend_sps_pps = True
                                log.info("AirPlay video SPS (%d B) & PPS (%d B) parsed and cached", len(sps), len(pps))
                    except Exception as e:
                        log.warning("Failed to parse SPS/PPS packet: %s", e)
                continue

            elif packet_type == 0:
                # Encrypted video VCL NAL units (AES-128-CTR)
                with self._cipher_lock:
                    decryptor = self._decryptor
                if decryptor is not None:
                    try:
                        payload = decryptor.update(payload)
                    except Exception as e:
                        log.warning("VideoReceiver decryption error: %s", e)
                        continue

                is_idr = (payload_flags == 0x10)
                payload_ba = bytearray(payload)
                payload_len = len(payload_ba)

                # AirPlay packet_type 0 is ALWAYS in AVCC format (each NAL unit prefixed
                # by its 4-byte Big-Endian length). Note: Do NOT check startswith(b"\x00\x00\x01")
                # because any AVCC NAL unit of length 256..511 bytes has a 4-byte BE length
                # starting with \x00\x00\x01\xXX!
                # Perform in-place AVCC -> Annex-B start code replacement (matching UxPlay).
                valid_data = True
                nalu_offset = 0
                nalu_count = 0
                while nalu_offset < payload_len:
                    if nalu_offset + 4 > payload_len:
                        valid_data = False
                        break
                    nc_len = struct.unpack_from(">I", payload_ba, nalu_offset)[0]
                    if nc_len <= 0 or nalu_offset + 4 + nc_len > payload_len:
                        valid_data = False
                        break
                    # Replace 4-byte length prefix with Annex-B start code 00 00 00 01
                    payload_ba[nalu_offset : nalu_offset + 4] = ANNEX_B
                    nalu_offset += 4
                    nal_header = payload_ba[nalu_offset]
                    # First bit of H.264 NAL header must be 0 (forbidden_zero_bit)
                    if nal_header & 0x80:
                        valid_data = False
                        break
                    nal_type = nal_header & 0x1F
                    if nal_type == 5 or nal_type == 7:
                        is_idr = True
                    nalu_offset += nc_len
                    nalu_count += 1

                if not valid_data or nalu_count == 0 or nalu_offset != payload_len:
                    # Fallback only for synthetic unit-test inputs that pass pre-formatted Annex-B
                    if payload.startswith(ANNEX_B):
                        frame_bytes = (
                            (self._sps_pps + payload)
                            if ((is_idr or self._prepend_sps_pps) and self._sps_pps)
                            else payload
                        )
                        self._prepend_sps_pps = False
                    else:
                        log.debug("Discarding invalid/corrupted H.264 packet (len=%d)", payload_len)
                        continue
                else:
                    if (is_idr or self._prepend_sps_pps) and self._sps_pps:
                        frame_bytes = self._sps_pps + bytes(payload_ba)
                        self._prepend_sps_pps = False
                    else:
                        frame_bytes = bytes(payload_ba)

                self._sequence += 1
                self._total_frames += 1
                self._enqueue_frame(VideoFrame(frame_bytes, now, self._sequence, is_idr=is_idr))

    def run(self) -> None:
        self._start_time = time.perf_counter()
        try:
            self._serve()
        except Exception as e:
            if not self._stop_event.is_set():
                log.error("VideoReceiver error: %s", e)

    def _serve(self) -> None:
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.settimeout(1.0)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen(2)
        log.info("VideoReceiver listening on %s:%d", self._host, self._port)

        while not self._stop_event.is_set():
            try:
                conn, addr = self._server_sock.accept()
                log.info("Video connection from %s", addr)
                self._sps_pps = None  # Reset SPS/PPS for new stream
                self._prepend_sps_pps = False
                self._client_sock = conn
                self._handle_client(conn)
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, conn: socket.socket) -> None:
        # Use a short 1.0s socket timeout so we can check _stop_event,
        # but NEVER close the connection on timeout (iOS pauses sending
        # video packets whenever the iPhone screen is static!).
        conn.settimeout(1.0)
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass
        buf = bytearray()
        with self._cipher_lock:
            if self._aes_key and self._aes_iv:
                cipher = Cipher(algorithms.AES(self._aes_key), modes.CTR(self._aes_iv))
                self._decryptor = cipher.decryptor()
                log.info("VideoReceiver: reset AES-CTR decryptor for new client connection")

        self._window_bytes = 0
        self._window_start = time.perf_counter()

        try:
            while not self._stop_event.is_set():
                try:
                    chunk = conn.recv(131072)
                except socket.timeout:
                    # Normal when iPhone screen is static (no new frames sent)
                    continue
                if not chunk:
                    break
                buf.extend(chunk)
                chunk_len = len(chunk)
                self._bytes_received += chunk_len
                self._window_bytes += chunk_len
                now = time.perf_counter()
                elapsed = now - self._window_start
                if elapsed >= 1.0:
                    self._current_bitrate_kbps = (self._window_bytes * 8) / (elapsed * 1000.0)
                    self._window_bytes = 0
                    self._window_start = now
                self._parse_packets(buf)

        except OSError as e:
            if not self._stop_event.is_set():
                log.warning("Video socket error: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self._client_sock = None
            self._current_bitrate_kbps = 0.0
            log.info("Video connection closed")

    def stop(self) -> None:
        self._stop_event.set()
        if self._client_sock:
            try:
                self._client_sock.close()
            except Exception:
                pass
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    @property
    def frame_queue(self) -> queue.Queue:
        return self._frame_queue

    @property
    def dropped_frames(self) -> int:
        return self._dropped_frames

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def bitrate_kbps(self) -> float:
        now = time.perf_counter()
        elapsed = now - self._window_start
        if elapsed >= 2.5:
            return 0.0
        if self._current_bitrate_kbps > 0:
            return self._current_bitrate_kbps
        total_elapsed = now - self._start_time
        if total_elapsed > 0:
            return (self._bytes_received * 8) / (total_elapsed * 1000)
        return 0.0
