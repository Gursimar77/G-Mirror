"""
Tests for G-Mirror RTSP parser.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from gmirror.airplay.rtsp import RTSPRequest, RTSPBuffer, RTSPResponse


def test_parse_options():
    raw = (
        b"OPTIONS * RTSP/1.0\r\n"
        b"CSeq: 1\r\n"
        b"User-Agent: AirPlay/1.0\r\n"
        b"\r\n"
    )
    req = RTSPRequest.parse(raw)
    assert req is not None
    assert req.method == "OPTIONS"
    assert req.cseq == 1
    assert req.body == b""


def test_parse_with_body():
    body = b"\x00\x01\x02\x03"
    raw = (
        f"POST /fp-setup RTSP/1.0\r\n"
        f"CSeq: 3\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"\r\n"
    ).encode() + body
    req = RTSPRequest.parse(raw)
    assert req is not None
    assert req.method == "POST"
    assert req.path == "/fp-setup"
    assert req.body == body


def test_response_build():
    resp = RTSPResponse(200, "OK", {"Server": "AirTunes/1.0"})
    data = resp.build(cseq=5)
    assert b"RTSP/1.0 200 OK" in data
    assert b"CSeq: 5" in data
    assert b"Server: AirTunes/1.0" in data


def test_buffer_accumulates():
    buf = RTSPBuffer()
    raw = b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n"
    # Feed in two chunks
    r1 = buf.feed(raw[:10])
    assert r1 == []  # incomplete
    r2 = buf.feed(raw[10:])
    assert len(r2) == 1
    assert r2[0].method == "OPTIONS"


def test_buffer_multiple_requests():
    buf = RTSPBuffer()
    raw = (
        b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n"
        b"OPTIONS * RTSP/1.0\r\nCSeq: 2\r\n\r\n"
    )
    requests = buf.feed(raw)
    assert len(requests) == 2
    assert requests[0].cseq == 1
    assert requests[1].cseq == 2
