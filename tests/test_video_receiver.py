"""
Tests for VideoReceiver packet parsing and H.264 Annex-B framing.
"""

import queue
import struct
from gmirror.airplay.video_receiver import VideoReceiver, VIDEO_HEADER_SIZE, VideoFrame


def _make_header(payload_size: int, packet_type: int = 0, flags: int = 0) -> bytes:
    hdr = bytearray(VIDEO_HEADER_SIZE)
    struct.pack_into("<I", hdr, 0, payload_size)  # Little-endian size
    hdr[4] = packet_type
    hdr[5] = flags
    struct.pack_into("<Q", hdr, 8, 123456789)    # Timestamp
    return bytes(hdr)


def _make_sps_pps_payload(sps: bytes, pps: bytes) -> bytes:
    # 6 bytes padding, then sps_size(2), sps, pps_size(2), pps
    payload = bytearray(b"\x01\x00\x00\x00\x00\x00")
    payload.extend(struct.pack(">H", len(sps)))
    payload.extend(sps)
    payload.append(0x01)  # PPS count byte
    payload.extend(struct.pack(">H", len(pps)))
    payload.extend(pps)
    return bytes(payload)


def _make_avcc_payload(nalus: list[bytes]) -> bytes:
    payload = bytearray()
    for nalu in nalus:
        payload.extend(struct.pack(">I", len(nalu)))
        payload.extend(nalu)
    return bytes(payload)


def test_video_receiver_extracts_sps_pps():
    q = queue.Queue()
    rx = VideoReceiver("127.0.0.1", 7001, frame_queue=q)

    sps = b"\x67\x42\x00\x1f\x9d"
    pps = b"\x68\xce\x3c\x80"
    sps_pps_payload = _make_sps_pps_payload(sps, pps)
    hdr = _make_header(len(sps_pps_payload), packet_type=1)

    buf = bytearray(hdr + sps_pps_payload)
    rx._parse_packets(buf)

    # SPS and PPS are stored and cached
    assert rx._sps_pps == b"\x00\x00\x00\x01" + sps + b"\x00\x00\x00\x01" + pps
    # Standalone SPS/PPS is NOT enqueued into decoder queue (avoids FFmpeg invalid data error)
    assert q.empty()

    # When an IDR slice arrives, SPS and PPS are prepended to the frame
    idr_nalu = b"\x25\x88\x84\x00\x11"
    avcc_payload = _make_avcc_payload([idr_nalu])
    hdr0 = _make_header(len(avcc_payload), packet_type=0, flags=0x10)
    rx._parse_packets(bytearray(hdr0 + avcc_payload))
    assert not q.empty()
    frame = q.get()
    assert frame.data == rx._sps_pps + b"\x00\x00\x00\x01" + idr_nalu


def test_video_receiver_converts_avcc_to_annex_b():
    q = queue.Queue()
    rx = VideoReceiver("127.0.0.1", 7001, frame_queue=q)
    rx._sps_pps = b"\x00\x00\x00\x01\x67\x42\x00\x00\x00\x01\x68\xce"

    idr_nalu = b"\x25\x88\x84\x00\x11"  # NAL type 5 (IDR)
    avcc_payload = _make_avcc_payload([idr_nalu])
    hdr = _make_header(len(avcc_payload), packet_type=0, flags=0x10)

    buf = bytearray(hdr + avcc_payload)
    rx._parse_packets(buf)

    assert not q.empty()
    frame = q.get()
    expected = rx._sps_pps + b"\x00\x00\x00\x01" + idr_nalu
    assert frame.data == expected


def test_video_receiver_little_endian_payload_size():
    q = queue.Queue()
    rx = VideoReceiver("127.0.0.1", 7001, frame_queue=q)

    # 1500 bytes payload
    payload = b"\x41" * 1500  # non-IDR slice
    avcc = struct.pack(">I", 1496) + payload[:1496]
    hdr = _make_header(len(avcc), packet_type=0, flags=0x00)

    # In little-endian, 1500 is \xdc\x05\x00\x00
    assert hdr[0:4] == struct.pack("<I", 1500)

    buf = bytearray(hdr + avcc)
    rx._parse_packets(buf)

    assert len(buf) == 0  # Entire packet was consumed
    assert not q.empty()
    frame = q.get()
    assert frame.data == b"\x00\x00\x00\x01" + payload[:1496]


def test_video_receiver_aes_ctr_decryption():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    q = queue.Queue()
    rx = VideoReceiver("127.0.0.1", 7001, frame_queue=q)

    key = b"\x01" * 16
    iv = b"\x02" * 16
    rx.init_aes(key, iv)

    # Plaintext AVCC slice
    slice_nalu = b"\x41\x00\x12\x34\x56"
    avcc_payload = _make_avcc_payload([slice_nalu])

    # Encrypt with AES-CTR
    encryptor = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    encrypted_payload = encryptor.update(avcc_payload)

    hdr = _make_header(len(encrypted_payload), packet_type=0, flags=0x00)
    buf = bytearray(hdr + encrypted_payload)
    rx._parse_packets(buf)

    assert not q.empty()
    frame = q.get()
    # Should decrypt cleanly to Annex-B format
    assert frame.data == b"\x00\x00\x00\x01" + slice_nalu


def test_video_receiver_avcc_256_to_511_byte_nal_unit():
    """
    Regression test: an AVCC NAL unit of length 256..511 bytes has a 4-byte
    big-endian length prefix of \\x00\\x00\\x01\\xXX, which starts with \\x00\\x00\\x01.
    Ensure it is properly converted to 4-byte Annex-B \\x00\\x00\\x00\\x01 + NAL
    instead of being mistaken for a 3-byte Annex-B start code.
    """
    q = queue.Queue()
    rx = VideoReceiver("127.0.0.1", 7001, frame_queue=q)

    # 300-byte P-frame slice (0x0000012c -> starts with \x00\x00\x01\x2c)
    slice_nalu = b"\x41" + (b"\xab" * 299)
    assert len(slice_nalu) == 300
    avcc_payload = _make_avcc_payload([slice_nalu])
    assert avcc_payload.startswith(b"\x00\x00\x01\x2c")

    hdr = _make_header(len(avcc_payload), packet_type=0, flags=0x00)
    buf = bytearray(hdr + avcc_payload)
    rx._parse_packets(buf)

    assert not q.empty()
    frame = q.get()
    assert frame.data == b"\x00\x00\x00\x01" + slice_nalu


def test_audio_receiver_aes_cbc_decryption():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from gmirror.airplay.audio_receiver import AudioReceiver

    rx = AudioReceiver("127.0.0.1", 7011)
    key = b"\x11" * 16
    iv = b"\x22" * 16
    rx.init_aes(key, iv)

    # 35-byte payload: 32 bytes AES-128-CBC encrypted + 3 bytes unencrypted trailing remainder
    plaintext_head = b"0123456789abcdef" * 2
    plaintext_tail = b"XYZ"
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(plaintext_head) + encryptor.finalize() + plaintext_tail

    decrypted = rx._decrypt_payload(ciphertext)
    assert decrypted == plaintext_head + plaintext_tail


def test_audio_output_callback_handles_extra_channels():
    import numpy as np
    from gmirror.render.audio_output import AudioOutput

    ao = AudioOutput()
    ao._running = True
    # Feed a 26-channel array like the one that previously triggered the CFFI ValueError
    ao.feed(np.ones((512, 26), dtype=np.float32) * 0.5)

    outdata = np.zeros((512, 2), dtype=np.float32)
    ao._audio_callback(outdata, 512, None, None)
    assert outdata.shape == (512, 2)
    assert np.allclose(outdata, 0.5)

