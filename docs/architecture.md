# G-Mirror Architecture Specification

## Overview

G-Mirror is an independent, native AirPlay receiver application designed for 64-bit Windows. It requires zero cloud infrastructure, no user accounts, and zero companion software on the transmitting iOS device.

```
+----------------------------------------------------------------------+
|                           iOS Device                                 |
|      (Control Center -> Screen Mirroring -> "G-Mirror")             |
+----------------------------------------------------------------------+
               |                               |
       mDNS Discovery (5353)           RTSP Control (7000)
               |                               |
+--------------v-------------------------------v-----------------------+
| G-Mirror Protocol Layer                                               |
|  - MDNSAdvertiser (_airplay._tcp, _raop._tcp)                        |
|  - AirPlayServer (RTSP parser, /info, /fp-setup, SETUP, RECORD)      |
|  - FairPlayHandshake (FairPlay v3 challenge/response)                |
|  - AirPlaySession (Session state machine & live telemetry)          |
+----------------------------------------------------------------------+
               |                               |
     H.264 Stream (7001 TCP)         Audio Stream (7011 UDP)
               |                               |
+--------------v-------------------------------v-----------------------+
| Decode Layer                                                         |
|  - VideoReceiver                           - AudioReceiver           |
|  - VideoDecoder (FFmpeg / PyAV)            - AudioDecoder (AAC/ALAC) |
|  - Hardware probe (DXVA2, D3D11VA, QSV)    - sounddevice output      |
+----------------------------------------------------------------------+
               |                               |
               +---------------+---------------+
                               |
+------------------------------v---------------------------------------+
| Output, Rendering & Capture                                          |
|  - VideoWidget (QPainter / QImage high-performance surface)          |
|  - Performance Overlay (FPS, Bitrate, Latency, Dropped Frames)       |
|  - Recorder (MP4 container via FFmpeg muxer)                         |
|  - Screenshot (Pillow frame capture)                                 |
+----------------------------------------------------------------------+
                               |
+------------------------------v---------------------------------------+
| User Interface & Windows Platform Layer                              |
|  - MainWindow (Theme support: Dark / Light / Windows System)         |
|  - DiagnosticsWindow (Automated 10-point network & firewall tests)   |
|  - FirstRunWizard (5-step onboarding guide)                          |
|  - TrayIcon (Background service management)                          |
|  - SetThreadExecutionState (Windows sleep/wake prevention)          |
+----------------------------------------------------------------------+
```

---

## 1. Network & Discovery Architecture
- **mDNS / Bonjour Service Advertisement (`_airplay._tcp.local.`, `_raop._tcp.local.`)**:
  - Broadcasts receiver capabilities including support for video mirroring (`features: 0x5A7FFFF7,0xE`), device model (`AppleTV6,2`), and unique deterministic MAC-style identifier.
  - Automatically isolates network interfaces or resolves primary active adapter.

## 2. AirPlay Session Negotiation (RTSP / FairPlay v3)
1. **OPTIONS**: Announces supported RTSP methods (`ANNOUNCE`, `SETUP`, `RECORD`, `PAUSE`, `FLUSH`, `TEARDOWN`, `OPTIONS`, `GET_PARAMETER`, `SET_PARAMETER`, `POST`, `GET`).
2. **GET /info**: Exchanges binary property list providing receiver public key and feature flags.
3. **POST /fp-setup**: Implements FairPlay v3 challenge-response authentication across phases to establish trusted session without circumvention or proprietary binary blobs.
4. **SETUP**: Negotiates dynamic TCP/UDP data ports for screen mirroring (stream type 110) and audio (stream type 96).
5. **RECORD**: Signals iOS to commence streaming video packets over TCP port 7001.

## 3. Video Pipeline
- **Packet Structure**: 128-byte AirPlay video header followed by raw Annex-B H.264 NAL units.
- **Decoding**: Streamed through `av.codec.CodecContext` with DXVA2/D3D11VA probe support.
- **Jitter Control**: Non-blocking frame queues with intelligent oldest-frame dropping under packet flood conditions to guarantee lowest practical real-time latency.

## 4. Audio Pipeline
- **Transport**: RTP/RAOP over UDP port 7011.
- **Decoding**: AAC-ELD / ALAC decoded to 32-bit floating point stereo PCM (44.1 kHz).
- **Output**: Real-time streaming via PortAudio/sounddevice with device switching and volume control.
