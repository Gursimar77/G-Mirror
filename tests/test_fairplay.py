"""
Tests for G-Mirror FairPlay handshake.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from gmirror.airplay.fairplay import FairPlayHandshake


def test_phase1_returns_142_bytes():
    fp = FairPlayHandshake()
    challenge = bytes(16)  # 16-byte challenge = phase 1
    response = fp.process(challenge)
    assert response is not None
    assert len(response) == 142


def test_phase1_starts_with_FPLY():
    fp = FairPlayHandshake()
    response = fp.process(bytes(16))
    assert response[:4] == b"FPLY"


def test_phase1_version_is_3():
    fp = FairPlayHandshake()
    response = fp.process(bytes(16))
    assert response[4] == 3


def test_phase2_returns_32_bytes():
    fp = FairPlayHandshake()
    fp.process(bytes(16))  # Phase 1
    challenge2 = bytes(164)  # 164 bytes = phase 2
    response = fp.process(challenge2)
    assert response is not None
    assert len(response) == 32
    assert response[:4] == b"FPLY"


def test_reset_clears_state():
    fp = FairPlayHandshake()
    fp.process(bytes(16))
    assert fp._phase == 1
    fp.reset()
    assert fp._phase == 0


def test_short_data_returns_none():
    fp = FairPlayHandshake()
    response = fp.process(b"")
    assert response is None


def test_message3_stored_in_phase2():
    fp = FairPlayHandshake()
    fp.process(bytes(16))  # Phase 1
    challenge2 = b"\x46\x50\x4c\x59\x03\x01\x03\x00" + b"\x00" * 156  # 164 bytes
    fp.process(challenge2)
    assert fp._message3 == challenge2
    assert fp._phase == 2


def test_decrypt_aes_key_requires_message3():
    fp = FairPlayHandshake()
    # No message3 received yet
    assert fp.decrypt_aes_key(bytes(72)) is None


def test_decrypt_aes_key_invalid_ekey_length():
    fp = FairPlayHandshake()
    challenge2 = b"\x46\x50\x4c\x59\x03\x01\x03\x00" + b"\x00" * 156
    fp.process(challenge2)
    # Invalid length (e.g. 16 or 32 instead of 72)
    assert fp.decrypt_aes_key(bytes(16)) is None
    assert fp.decrypt_aes_key(bytes(70)) is None


