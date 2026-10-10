# G-Mirror 📱 🪞

> **Free, High-Performance, Open-Source iPhone → Windows Screen Mirroring**  
> *Native AirPlay Receiver for Windows 10 & 11 x64. No iOS companion app. No accounts. No subscriptions. No cloud.*

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11%20x64-blue.svg)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12-blue)](https://python.org)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## 🌟 Highlights

- **Native AirPlay Integration**: Uses iOS Control Center's native **Screen Mirroring** button. No app needed on your iPhone!
- **Real-Time Video & Audio**: Smooth 60 FPS video playback with synchronized stereo audio.
- **Hardware-Accelerated Decoding**: Probes and leverages DXVA2, D3D11VA, NVIDIA CUDA, or Intel QSV for minimal CPU load.
- **Ultra-Low Latency Pipeline**: Zero-bloat frame queuing maintains the lowest practical display latency.
- **100% Private & Offline**: Zero telemetry, zero analytics, zero internet requirements. Everything stays on your local Wi-Fi.
- **One-Click MP4 Recording & Screenshots**: Record your mirrored session directly to MP4 with clean container finalization or capture high-res PNG screenshots instantly.
- **Built-in Connection Diagnostics**: Automated 10-point network and firewall test suite diagnoses Wi-Fi client isolation, blocked ports, or network profile issues in plain English.
- **Modern Adaptive UI**: Beautiful Dark and Light modes, Windows System Theme detection, performance metrics overlay, fullscreen (F11), and system tray background operation.

---

## 📸 Screenshots & Architecture

```
iPhone Control Center  ──>  AirPlay (mDNS / RTSP / FP3)  ──>  G-Mirror (Windows x64)
                                                                 ├── H.264 Video Decoder (DXVA2/D3D11VA)
                                                                 ├── AAC Audio Output (sounddevice)
                                                                 ├── MP4 Session Recorder
                                                                 └── Live Performance Overlay
```

---

## 🚀 Quick Start

### 1. Installation

#### Portable Version (Recommended)
1. Download `GMirror-Windows-x64-Portable.zip` from [Releases](https://github.com/gmirror-app/gmirror/releases).
2. Extract to any folder and double-click `GMirror.exe`.

#### Running from Source
```bash
git clone https://github.com/gmirror-app/gmirror.git
cd gmirror
python -m pip install -r requirements.txt
python main.py
```

### 2. How to Mirror Your iPhone
1. Ensure your PC and iPhone are connected to the **same Wi-Fi network**.
2. Launch **G-Mirror** on Windows. Click **Start Mirroring**.
3. On your iPhone:
   - Swipe down from the top-right corner to open **Control Center**.
   - Tap **Screen Mirroring** (the two overlapping rectangles icon).
   - Select **G-Mirror** from the list.
4. Your iPhone screen will instantly appear on your PC!

---

## 🛠️ Features & Controls

| Feature | Description |
|---|---|
| **Live Metric Bar** | Displays real-time FPS, Resolution, Bitrate, Dropped Frames, Active Decoder, and Network Quality. |
| **Performance Overlay** | Optional in-game style Heads-Up Display (HUD) showing frame rendering latency and decoder stats. |
| **Fullscreen Modes** | Press **F11** or double-click the video surface to enter borderless fullscreen; **ESC** to exit. |
| **Always on Top** | Pin G-Mirror above games, IDEs, or presentations with the 📌 toolbar button. |
| **Sleep Lock Prevention** | Automatically prevents Windows from entering sleep or turning off screens during active mirroring. |
| **Audio Controls** | Independent mute toggle, volume slider, and Windows audio output endpoint switcher. |
| **System Tray Mode** | Minimize G-Mirror to the system notification area to mirror seamlessly in the background. |

---

## 🔍 Connection Diagnostics

If your iPhone cannot see G-Mirror, click the 🔍 icon in the toolbar or open **Connection Diagnostics**:

- **Automated Tests**:
  - Wi-Fi / Ethernet adapter activity & IPv4 subnet check.
  - mDNS / Bonjour port (UDP 5353) conflict detection.
  - AirPlay control port (TCP 7000) & stream ports (7001, 7011, 7012).
  - Windows Network Profile (flags Public network warnings).
  - Windows Firewall inspection with tailored whitelist instructions.
  - Multicast packet routing compatibility.
- **One-Click Export**:
  - `Copy Report` or `Export Diagnostic Report` generate safe, sanitized text logs with **zero private keys or passwords**.

---

## 🏗️ Technical Architecture & Protocol Compliance

G-Mirror implements the receiver side of Apple's AirPlay protocol suite:

1. **Service Discovery**: Advertises `_airplay._tcp.local.` and `_raop._tcp.local.` via `zeroconf` with standard model tags (`AppleTV6,2`).
2. **RTSP Control Channel**: Implements an asynchronous RTSP server handling `OPTIONS`, `GET /info`, `POST /fp-setup`, `SETUP`, `RECORD`, `SET_PARAMETER`, and `TEARDOWN`.
3. **FairPlay v3 Pairing**: Employs the standard public challenge-response handshake sequence documented in open-source research without circumventing content encryption.
4. **H.264 Video Transport**: Streams Annex-B NAL packets over TCP with 128-byte presentation timestamps and real-time clock synchronization over UDP port 7012.
5. **A/V Sync**: Implements NTP timestamp calculations to ensure lip-sync fidelity.

---

## 🧪 Testing

Run the automated test suite covering protocol parsing, FairPlay handshake sequences, settings persistence, diagnostics, and container finalization:

```bash
python -m pytest tests/ -v
```

---

## 📦 Building from Source (PyInstaller)

To build the standalone Windows x64 executable:

```bash
# 1. Install development dependencies
pip install -r requirements-dev.txt

# 2. Generate application branding and icon assets
python packaging/generate_icons.py

# 3. Compile standalone distribution
pyinstaller packaging/gmirror.spec
```

The compiled binaries will be output to `dist/GMirror/`.

---

## ❓ Frequently Asked Questions (FAQ)

#### Q: Does this require iTunes or Bonjour for Windows installed?
**A:** No! G-Mirror includes its own zero-configuration pure-Python mDNS responder. Neither iTunes nor third-party Bonjour services are required.

#### Q: Why is my iPhone not finding G-Mirror?
**A:** Ensure both devices are on the exact same Wi-Fi network and that your router does not have "AP Isolation" or "Client Isolation" turned on. Also check Windows Settings → Network to verify your network profile is set to **Private** rather than **Public**.

#### Q: Can G-Mirror mirror DRM-protected content (Netflix, Disney+, etc.)?
**A:** No. Apple restricts FairPlay DRM-protected video playback strictly to certified Apple TV hardware and authorized TV manufacturers. Screen mirroring displays the user interface, games, photos, cameras, and non-DRM video smoothly.

---

## 📄 License & Attribution

- G-Mirror is open-source software licensed under the **[MIT License](LICENSE)**.
- Third-party libraries and licenses are detailed in **[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)**.
- G-Mirror is an independent open-source project and is not affiliated with, sponsored by, or endorsed by Apple Inc.
