# Changelog

All notable changes to the G-Mirror project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-05

### Added
- **Native AirPlay Receiver**:
  - Zeroconf mDNS Bonjour advertisement (`_airplay._tcp`, `_raop._tcp`).
  - Full RTSP/HTTP control server (`OPTIONS`, `GET /info`, `POST /fp-setup`, `SETUP`, `RECORD`, `SET_PARAMETER`, `TEARDOWN`).
  - AirPlay FairPlay v3 challenge-response pairing handshake.
  - High-performance TCP H.264 video frame stream receiver.
  - RAOP UDP audio receiver with AAC-ELD / ALAC support.
  - UDP NTP clock synchronization responder (port 7012).
- **Video & Audio Pipeline**:
  - H.264 decoding via PyAV / FFmpeg with low-latency configuration.
  - Hardware acceleration probe (DXVA2, D3D11VA, Intel QSV, NVIDIA CUDA).
  - High-performance video rendering surface with aspect-ratio letterboxing.
  - Sounddevice audio output with real-time device selection, volume slider, and mute.
- **Recording & Capture**:
  - MP4 video/audio session recording with safe container finalization.
  - One-click instant screenshot capture (PNG/JPEG) with timestamping.
- **User Interface**:
  - Dark, Light, and Windows System theme support.
  - Live metric bar (FPS, Resolution, Latency, Bitrate, Dropped frames, Decoder, Network quality).
  - Real-time in-video performance overlay.
  - Fullscreen (F11) and borderless windowed mode.
  - Window always-on-top toggle.
  - Windows sleep/wake lock prevention (`SetThreadExecutionState`).
  - System tray icon with quick controls and balloon notifications.
- **Connection Diagnostics**:
  - Automated 10-point network and firewall health test suite.
  - Human-friendly explanations with actionable advice.
  - "Copy Report" and "Export Diagnostic Report" (sanitized, zero credentials).
- **First-Run Experience**:
  - 5-step onboarding wizard for seamless setup.
- **Packaging & Portability**:
  - PyInstaller single-folder / portable configuration.
  - Original iPhone-inspired vector/raster icon suite (`.ico`, multi-size PNGs).
