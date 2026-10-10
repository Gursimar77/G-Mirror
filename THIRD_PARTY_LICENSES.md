# Third-Party Licenses and Notices

G-Mirror incorporates and depends on several open-source libraries and specifications.
This document details their upstream licenses and copyright notices.

---

## 1. PySide6 (Qt for Python)
- **License**: GNU Lesser General Public License v3 (LGPLv3)
- **Copyright**: © The Qt Company Ltd. and other contributors
- **Website**: https://wiki.qt.io/Qt_for_Python
- **Notice**: G-Mirror dynamically imports and links against PySide6 without modifying Qt source code. Users have the right to inspect, replace, and relink against compatible Qt binaries in accordance with the LGPLv3 terms.

---

## 2. Zeroconf (python-zeroconf)
- **License**: GNU Lesser General Public License v2.1 (LGPLv2.1)
- **Copyright**: © Paul Scott-Murphy, William McBrine, and contributors
- **Website**: https://github.com/python-zeroconf/python-zeroconf
- **Usage**: Used for Multicast DNS (mDNS) / Bonjour advertisement of AirPlay services on the local subnet.

---

## 3. PyAV (av) & FFmpeg
- **License**: BSD 3-Clause (PyAV), LGPL v2.1+ / GPL (FFmpeg)
- **Copyright**: © Mike Boers and PyAV contributors; © FFmpeg developers
- **Website**: https://github.com/PyAV-Org/PyAV / https://ffmpeg.org
- **Usage**: Used for H.264 video decoding, AAC audio decoding, and MP4 container muxing.
- **Notice**: Pre-compiled PyAV wheels are compiled with LGPL configuration of FFmpeg.

---

## 4. sounddevice & PortAudio
- **License**: MIT License (sounddevice), MIT-like (PortAudio)
- **Copyright**: © 2015–2024 Matthias Geier; © 1999–2024 Ross Bencina and Phil Burk
- **Website**: https://python-sounddevice.readthedocs.io / http://www.portaudio.com
- **Usage**: Low-latency audio playback to Windows audio output endpoints.

---

## 5. cryptography
- **License**: Apache Software License 2.0 or BSD License
- **Copyright**: © The Python Cryptographic Authority and individual contributors
- **Website**: https://cryptography.io
- **Usage**: Cryptographic primitives for AirPlay session authentication.

---

## 6. Pillow (PIL Fork)
- **License**: Historical Permission Notice and Disclaimer (HPND)
- **Copyright**: © 2010–2024 Jeffrey A. Clark (Alex) and contributors
- **Website**: https://python-pillow.org
- **Usage**: Screenshot frame capture and icon asset processing.

---

## 7. NumPy
- **License**: BSD 3-Clause
- **Copyright**: © 2005–2024 NumPy Developers
- **Website**: https://numpy.org
- **Usage**: Fast buffer interleave and audio matrix manipulation.

---

## Protocol References & Research Notices
- **AirPlay Protocol Implementation**: G-Mirror is an independent, clean-room implementation of the receiver side of Apple's AirPlay screen mirroring protocol, based on publicly available reverse-engineering literature, the `openairplay/airplay2-receiver` project (MIT license), and `UxPlay` (GPLv3).
- No proprietary Apple source code, confidential headers, or trade secrets are included or utilized.
- All trademarks (AirPlay, iPhone, iOS, Windows) belong to their respective owners and are used purely descriptively to indicate device interoperability.
