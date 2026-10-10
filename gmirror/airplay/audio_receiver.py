"""
G-Mirror AirPlay Audio Receiver.

Receives AAC-ELD or ALAC audio from iOS.
AirPlay audio can arrive via UDP (RAOP) or TCP depending on the iOS version.

Protocol Reference: openairplay/airplay2-receiver (MIT), UxPlay (GPL v3)
"""

from __future__ import annotations

import logging
import queue
import socket
import struct
import threading
import time
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

log = logging.getLogger(__name__)

AUDIO_QUEUE_MAXSIZE = 128


class AudioPacket:
    """A raw encoded audio payload with timing."""
    __slots__ = ("data", "timestamp", "codec", "seq")

    def __init__(self, data: bytes, timestamp: float, codec: str, seq: int) -> None:
        self.data = data
        self.timestamp = timestamp
        self.codec = codec
        self.seq = seq


class AudioReceiver(threading.Thread):
    """
    UDP-based audio packet receiver for AirPlay RAOP streams.
    Decrypts AES-128-CBC encrypted RTP audio payloads using the FairPlay session key/IV.
    """

    def __init__(
        self,
        host: str,
        port: int,
        audio_queue: Optional[queue.Queue] = None,
        codec: str = "aac-eld",
    ) -> None:
        super().__init__(name="AudioReceiver", daemon=True)
        self._host = host
        self._port = port
        self._audio_queue: queue.Queue = audio_queue or queue.Queue(maxsize=AUDIO_QUEUE_MAXSIZE)
        self._codec = codec
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._sequence = 0
        self._active = False
        self._aes_lock = threading.Lock()
        self._aes_key: Optional[bytes] = None
        self._aes_iv: Optional[bytes] = None

    def init_aes(self, key: bytes, iv: bytes) -> None:
        """Initialize AES-128-CBC key and IV for RTP audio packet decryption."""
        with self._aes_lock:
            self._aes_key = bytes(key[:16])
            self._aes_iv = bytes(iv[:16])
            log.info("AudioReceiver AES-128-CBC initialized (key=%s..., iv=%s...)",
                     self._aes_key[:4].hex(), self._aes_iv[:4].hex())

    def set_codec(self, codec: str) -> None:
        self._codec = codec

    def _decrypt_payload(self, payload: bytes) -> bytes:
        """
        AirPlay RAOP audio packets (stream type 96) encrypt each RTP payload
        independently using AES-128-CBC with the session key and IV reset per packet.
        Only full 16-byte blocks are encrypted; trailing (len % 16) bytes remain in the clear.
        """
        with self._aes_lock:
            key = self._aes_key
            iv = self._aes_iv
        if not key or not iv:
            return payload
        aligned_len = (len(payload) // 16) * 16
        if aligned_len <= 0:
            return payload
        try:
            decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            decrypted = decryptor.update(payload[:aligned_len]) + decryptor.finalize()
            if aligned_len < len(payload):
                return decrypted + payload[aligned_len:]
            return decrypted
        except Exception as e:
            log.debug("Audio AES-CBC decrypt error: %s", e)
            return payload

    def run(self) -> None:
        try:
            self._receive_loop()
        except Exception as e:
            if not self._stop_event.is_set():
                log.error("AudioReceiver error: %s", e)

    def _receive_loop(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 512 * 1024)
        except Exception:
            pass
        self._sock.settimeout(1.0)
        self._sock.bind((self._host, self._port))
        self._active = True
        log.info("AudioReceiver listening on %s:%d (codec=%s)", self._host, self._port, self._codec)

        while not self._stop_event.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
                if len(data) < 12:
                    continue

                # Check RTP payload type (Byte 1 & 0x7F)
                # PT 96 (0x60) or 0xE0 (with marker bit) is audio data; skip RTCP/retransmit control packets
                pt = data[1] & 0x7F
                if pt not in (96, 86):
                    continue

                # For PT 86 (retransmitted audio packet), there is a 4-byte extra header before the original RTP header
                if pt == 86:
                    if len(data) < 16:
                        continue
                    data = data[4:]

                seq = struct.unpack_from(">H", data, 2)[0]
                rtp_ts = struct.unpack_from(">I", data, 4)[0]
                timestamp = rtp_ts / 44100.0  # Standard AirPlay audio sample rate

                # Audio payload starts at byte 12 (standard RTP header)
                raw_payload = data[12:]
                if not raw_payload:
                    continue

                payload = self._decrypt_payload(raw_payload)

                self._sequence += 1
                packet = AudioPacket(payload, timestamp, self._codec, seq)
                try:
                    self._audio_queue.put_nowait(packet)
                except queue.Full:
                    try:
                        self._audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self._audio_queue.put_nowait(packet)

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
    def audio_queue(self) -> queue.Queue:
        return self._audio_queue

    @property
    def is_active(self) -> bool:
        return self._active
