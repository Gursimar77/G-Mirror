"""
G-Mirror FairPlay SAP Pairing Handshake.

AirPlay screen mirroring requires a FairPlay SAP challenge-response
handshake on the /fp-setup endpoint before RTSP SETUP and video streaming begin.

Protocol Reference:
  - openairplay/airplay2-receiver (MIT License)
  - FDH2/UxPlay (GPL v3)
  - jonaseberle/RPiPlay documentation

The handshake uses standard pre-computed SAP responses embedded in open-source
AirPlay receiver implementations (UxPlay, RPiPlay, airplay2-receiver).
Phase 1: iOS sends 16-byte challenge -> receiver replies with 142-byte SAP reply.
Phase 2: iOS sends 164-byte challenge -> receiver replies with 32-byte SAP reply.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


class FairPlayHandshake:
    """
    Stateful FairPlay SAP handshake handler.

    iOS sends up to 2 /fp-setup POST requests:
      - Phase 1: 16 bytes (FPLY header + mode), expects 142 bytes reply.
      - Phase 2: 164 bytes, expects 32 bytes reply (12 bytes FPLY header + 20 bytes request suffix).

    Usage:
        fp = FairPlayHandshake()
        response_bytes = fp.process(request_body)
    """

    MODES = 4
    MODE_POSITION = 14
    TYPE_POSITION = 5
    SEQ_POSITION = 6
    SETUP_MESSAGE_TYPE = 1
    DECRYPT_MESSAGE_TYPE = 2
    SETUP1_MESSAGE_SEQ = 1
    SETUP2_MESSAGE_SEQ = 3
    SETUP1_RESPONSE_LENGTH = 142
    SETUP2_RESPONSE_LENGTH = 32
    SETUP2_RESPONSE_SUFFIX_LENGTH = 20

    reply_message = [
        b"\x46\x50\x4c\x59\x03\x01\x02\x00\x00\x00\x00\x82\x02\x00\x0f\x9f\x3f\x9e\x0a\x25\x21\xdb\xdf\x31\x2a\xb2\xbf\xb2\x9e\x8d\x23\x2b\x63\x76\xa8\xc8\x18\x70\x1d\x22\xae\x93\xd8\x27\x37\xfe\xaf\x9d\xb4\xfd\xf4\x1c\x2d\xba\x9d\x1f\x49\xca\xaa\xbf\x65\x91\xac\x1f\x7b\xc6\xf7\xe0\x66\x3d\x21\xaf\xe0\x15\x65\x95\x3e\xab\x81\xf4\x18\xce\xed\x09\x5a\xdb\x7c\x3d\x0e\x25\x49\x09\xa7\x98\x31\xd4\x9c\x39\x82\x97\x34\x34\xfa\xcb\x42\xc6\x3a\x1c\xd9\x11\xa6\xfe\x94\x1a\x8a\x6d\x4a\x74\x3b\x46\xc3\xa7\x64\x9e\x44\xc7\x89\x55\xe4\x9d\x81\x55\x00\x95\x49\xc4\xe2\xf7\xa3\xf6\xd5\xba",
        b"\x46\x50\x4c\x59\x03\x01\x02\x00\x00\x00\x00\x82\x02\x01\xcf\x32\xa2\x57\x14\xb2\x52\x4f\x8a\xa0\xad\x7a\xf1\x64\xe3\x7b\xcf\x44\x24\xe2\x00\x04\x7e\xfc\x0a\xd6\x7a\xfc\xd9\x5d\xed\x1c\x27\x30\xbb\x59\x1b\x96\x2e\xd6\x3a\x9c\x4d\xed\x88\xba\x8f\xc7\x8d\xe6\x4d\x91\xcc\xfd\x5c\x7b\x56\xda\x88\xe3\x1f\x5c\xce\xaf\xc7\x43\x19\x95\xa0\x16\x65\xa5\x4e\x19\x39\xd2\x5b\x94\xdb\x64\xb9\xe4\x5d\x8d\x06\x3e\x1e\x6a\xf0\x7e\x96\x56\x16\x2b\x0e\xfa\x40\x42\x75\xea\x5a\x44\xd9\x59\x1c\x72\x56\xb9\xfb\xe6\x51\x38\x98\xb8\x02\x27\x72\x19\x88\x57\x16\x50\x94\x2a\xd9\x46\x68\x8a",
        b"\x46\x50\x4c\x59\x03\x01\x02\x00\x00\x00\x00\x82\x02\x02\xc1\x69\xa3\x52\xee\xed\x35\xb1\x8c\xdd\x9c\x58\xd6\x4f\x16\xc1\x51\x9a\x89\xeb\x53\x17\xbd\x0d\x43\x36\xcd\x68\xf6\x38\xff\x9d\x01\x6a\x5b\x52\xb7\xfa\x92\x16\xb2\xb6\x54\x82\xc7\x84\x44\x11\x81\x21\xa2\xc7\xfe\xd8\x3d\xb7\x11\x9e\x91\x82\xaa\xd7\xd1\x8c\x70\x63\xe2\xa4\x57\x55\x59\x10\xaf\x9e\x0e\xfc\x76\x34\x7d\x16\x40\x43\x80\x7f\x58\x1e\xe4\xfb\xe4\x2c\xa9\xde\xdc\x1b\x5e\xb2\xa3\xaa\x3d\x2e\xcd\x59\xe7\xee\xe7\x0b\x36\x29\xf2\x2a\xfd\x16\x1d\x87\x73\x53\xdd\xb9\x9a\xdc\x8e\x07\x00\x6e\x56\xf8\x50\xce",
        b"\x46\x50\x4c\x59\x03\x01\x02\x00\x00\x00\x00\x82\x02\x03\x90\x01\xe1\x72\x7e\x0f\x57\xf9\xf5\x88\x0d\xb1\x04\xa6\x25\x7a\x23\xf5\xcf\xff\x1a\xbb\xe1\xe9\x30\x45\x25\x1a\xfb\x97\xeb\x9f\xc0\x01\x1e\xbe\x0f\x3a\x81\xdf\x5b\x69\x1d\x76\xac\xb2\xf7\xa5\xc7\x08\xe3\xd3\x28\xf5\x6b\xb3\x9d\xbd\xe5\xf2\x9c\x8a\x17\xf4\x81\x48\x7e\x3a\xe8\x63\xc6\x78\x32\x54\x22\xe6\xf7\x8e\x16\x6d\x18\xaa\x7f\xd6\x36\x25\x8b\xce\x28\x72\x6f\x66\x1f\x73\x88\x93\xce\x44\x31\x1e\x4b\xe6\xc0\x53\x51\x93\xe5\xef\x72\xe8\x68\x62\x33\x72\x9c\x22\x7d\x82\x0c\x99\x94\x45\xd8\x92\x46\xc8\xc3\x59",
    ]

    fp_header = b"\x46\x50\x4c\x59\x03\x01\x04\x00\x00\x00\x00\x14"

    def __init__(self) -> None:
        self._phase: int = 0
        self._aes_key: Optional[bytes] = None
        self._message3: Optional[bytes] = None

    def process(self, data: bytes) -> Optional[bytes]:
        """
        Process an /fp-setup request body and return the response body.
        Returns None on error.
        """
        try:
            return self._dispatch(data)
        except Exception as e:
            log.error("FairPlay handshake error: %s", e)
            return None

    def _dispatch(self, data: bytes) -> Optional[bytes]:
        if not data or len(data) < 4:
            log.warning("FairPlay: data too short (%d bytes)", len(data) if data else 0)
            return None

        # Check if FPLY magic header is present
        if data[:4] == b"FPLY":
            msg_type = data[self.TYPE_POSITION] if len(data) > self.TYPE_POSITION else 1
            seq = data[self.SEQ_POSITION] if len(data) > self.SEQ_POSITION else 1

            if msg_type == self.SETUP_MESSAGE_TYPE:
                if seq == self.SETUP1_MESSAGE_SEQ or len(data) == 16:
                    self._phase = 1
                    mode = data[self.MODE_POSITION] if len(data) > self.MODE_POSITION else 0
                    if mode >= len(self.reply_message):
                        mode = 0
                    log.info("FairPlay setup phase 1 (mode=%d, seq=%d) -> responding 142 bytes", mode, seq)
                    return self.reply_message[mode]
                elif seq == self.SETUP2_MESSAGE_SEQ or len(data) == 164:
                    self._phase = 2
                    self._message3 = data
                    log.info("FairPlay setup phase 2 (seq=%d) -> responding 32 bytes", seq)
                    suffix = (
                        data[-self.SETUP2_RESPONSE_SUFFIX_LENGTH:]
                        if len(data) >= self.SETUP2_RESPONSE_SUFFIX_LENGTH
                        else (data + b"\x00" * 20)[:20]
                    )
                    return self.fp_header + suffix

        # Fallback heuristics by payload length
        if len(data) == 16:
            self._phase = 1
            mode = data[self.MODE_POSITION] if len(data) > self.MODE_POSITION else 0
            if mode >= len(self.reply_message):
                mode = 0
            log.info("FairPlay setup phase 1 heuristic (mode=%d) -> responding 142 bytes", mode)
            return self.reply_message[mode]
        elif len(data) == 164:
            self._phase = 2
            self._message3 = data
            log.info("FairPlay setup phase 2 heuristic -> responding 32 bytes")
            return self.fp_header + data[-self.SETUP2_RESPONSE_SUFFIX_LENGTH:]
        else:
            log.info("FairPlay setup fallback response (len=%d) -> responding phase 1 default", len(data))
            self._phase = 1
            return self.reply_message[0]

    @property
    def aes_key(self) -> Optional[bytes]:
        return self._aes_key

    def decrypt_aes_key(self, ekey: bytes) -> Optional[bytes]:
        """
        Decrypt the 72-byte ekey sent by iOS during SETUP using FairPlay SAPv3.
        Returns the 16-byte master AES key, or None on failure.
        """
        if not self._message3 or len(self._message3) != 164:
            log.warning(
                "FairPlay decrypt_aes_key: missing or invalid message3 (%d bytes)",
                len(self._message3) if self._message3 else 0,
            )
            return None
        if len(ekey) != 72:
            log.warning("FairPlay decrypt_aes_key: invalid ekey length %d (expected 72)", len(ekey))
            return None
        try:
            from gmirror.airplay.fairplay3 import Fairplay3
            aes_key = Fairplay3().decryptAESKey(self._message3, ekey)
            self._aes_key = aes_key
            log.info("FairPlay AES key successfully decrypted: %s...", aes_key[:4].hex())
            return aes_key
        except Exception as e:
            log.error("FairPlay AES key decryption error: %s", e)
            return None

    def reset(self) -> None:
        self._phase = 0
        self._aes_key = None
        self._message3 = None

