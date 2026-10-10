"""
G-Mirror Main Window.

The primary application window with:
  - Video display area (fills most of the window)
  - Status header with connection state and device name
  - Metric bar: FPS, resolution, latency, bitrate, dropped frames, audio, recording
  - Control buttons: Start/Stop, Record, Screenshot, Fullscreen
  - Toolbar: Settings, Diagnostics, Overlay toggle
  - Window controls: minimize, maximize, close, fullscreen, always-on-top
  - Multi-monitor fullscreen support
  - System tray integration
  - Screen wake-lock via Windows API
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import (
    QAction, QCloseEvent, QFont, QIcon, QKeySequence,
    QColor, QPainter, QPixmap, QScreen, QShortcut
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton,
    QSizePolicy, QStatusBar, QToolBar, QVBoxLayout, QWidget,
    QFrame, QMenu
)

from gmirror import __version__
from gmirror.airplay.mdns import MDNSAdvertiser
from gmirror.airplay.server import AirPlayServer
from gmirror.airplay.session import AirPlaySession, SessionState, SessionStats
from gmirror.airplay.video_receiver import VideoReceiver
from gmirror.airplay.audio_receiver import AudioReceiver
from gmirror.airplay.ntp_sync import NTPSyncServer
from gmirror.codec.video_decoder import VideoDecoder
from gmirror.codec.audio_decoder import AudioDecoder
from gmirror.render.audio_output import AudioOutput
from gmirror.recording.recorder import Recorder
from gmirror.recording.screenshot import capture_screenshot
from gmirror.settings.config import get_config, save_config
from ui.video_widget import VideoWidget
from ui.tray_icon import TrayIcon
from ui.settings_dialog import SettingsDialog
from ui.diagnostics_window import DiagnosticsWindow
from ui.icons import (
    get_settings_icon,
    get_diagnostics_icon,
    get_overlay_icon,
    get_pin_icon,
    get_fullscreen_icon,
    get_volume_icon,
    get_camera_icon,
    get_record_icon,
)
from PySide6.QtCore import QSize

log = logging.getLogger(__name__)

# Windows ES_CONTINUOUS | ES_SYSTEM_REQUIRED — prevents sleep while mirroring
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def _set_screen_awake(awake: bool) -> None:
    try:
        flags = _ES_CONTINUOUS
        if awake:
            flags |= _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception as e:
        log.debug("SetThreadExecutionState failed: %s", e)


class _FrameBridge(QObject):
    """Thread-safe coalescing bridge from decoder thread to UI thread.
    Ensures at most 1 signal is in-flight in the Qt event queue at any time,
    preventing UI event queue backlog and guaranteeing zero-lag display.
    """
    frame_ready = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._latest = None
        self._pending = False

    def submit(self, img, av_frame) -> None:
        with self._lock:
            self._latest = (img, av_frame)
            if not self._pending:
                self._pending = True
                self.frame_ready.emit()

    def take(self):
        with self._lock:
            item = self._latest
            self._latest = None
            self._pending = False
            return item


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"G-Mirror v{__version__}")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        # Explicit standard window flags ensuring title bar controls are active
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # Core components
        self._session = AirPlaySession()
        self._mdns = MDNSAdvertiser()
        self._server: Optional[AirPlayServer] = None
        self._video_receiver: Optional[VideoReceiver] = None
        self._audio_receiver: Optional[AudioReceiver] = None
        self._video_decoder: Optional[VideoDecoder] = None
        self._audio_decoder: Optional[AudioDecoder] = None
        self._audio_output = AudioOutput()
        self._ntp_sync: Optional[NTPSyncServer] = None
        self._recorder = Recorder()
        self._last_av_frame = None
        self._is_running = False
        self._is_fullscreen = False

        # Bridge for cross-thread frame delivery
        self._frame_bridge = _FrameBridge()
        self._frame_bridge.frame_ready.connect(self._on_frame_ready)

        self._build_ui()
        self._build_tray()
        self._connect_session()

        # Window-level shortcuts for rock-solid Fullscreen toggle and Escape handling
        self._f11_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        self._f11_shortcut.activated.connect(self._toggle_fullscreen)

        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.activated.connect(self._on_escape_pressed)

        # Timers
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(500)
        self._stats_timer.timeout.connect(self._update_stats_display)
        self._stats_timer.start()

        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(1000)
        self._rec_timer.timeout.connect(self._update_rec_timer)

        # Apply settings
        cfg = get_config()
        self._apply_window_settings(cfg)

        log.info("G-Mirror main window initialized.")

    # ================================================================ UI BUILD
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        self._root_layout = QVBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Top toolbar
        self._toolbar = self._build_toolbar()
        self._root_layout.addWidget(self._toolbar)

        # Content area: video + side panel
        self._content_layout = QHBoxLayout()
        self._content_layout.setContentsMargins(12, 10, 12, 10)
        self._content_layout.setSpacing(10)

        # Video widget (takes all available space)
        self._video_widget = VideoWidget()
        self._video_widget.double_clicked.connect(self._toggle_fullscreen)
        self._content_layout.addWidget(self._video_widget, stretch=1)

        # Right panel (status + controls)
        self._side_panel = self._build_side_panel()
        self._content_layout.addWidget(self._side_panel)

        self._root_layout.addLayout(self._content_layout, stretch=1)

        # Bottom metric bar
        self._metric_bar = self._build_metric_bar()
        self._root_layout.addWidget(self._metric_bar)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready — waiting for AirPlay connection")

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(46)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Logo / title
        title = QLabel("G-Mirror")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        version_lbl = QLabel(f"v{__version__}")
        version_lbl.setStyleSheet("color: #64748b; font-size: 11px; margin-top: 2px;")
        layout.addWidget(version_lbl)
        layout.addStretch()

        # Settings
        self._settings_btn = QPushButton()
        self._settings_btn.setIcon(get_settings_icon())
        self._settings_btn.setIconSize(QSize(20, 20))
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setFixedSize(36, 36)
        self._settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self._settings_btn)

        # Diagnostics
        self._diag_btn = QPushButton()
        self._diag_btn.setIcon(get_diagnostics_icon())
        self._diag_btn.setIconSize(QSize(20, 20))
        self._diag_btn.setToolTip("Connection Diagnostics")
        self._diag_btn.setFixedSize(36, 36)
        self._diag_btn.clicked.connect(self._open_diagnostics)
        layout.addWidget(self._diag_btn)

        # Performance Overlay
        self._overlay_btn = QPushButton()
        self._overlay_btn.setIcon(get_overlay_icon())
        self._overlay_btn.setIconSize(QSize(20, 20))
        self._overlay_btn.setToolTip("Toggle Performance Overlay (HUD)")
        self._overlay_btn.setFixedSize(36, 36)
        self._overlay_btn.clicked.connect(self._toggle_overlay)
        layout.addWidget(self._overlay_btn)

        # Always on top toggle
        self._aot_btn = QPushButton()
        self._aot_btn.setIcon(get_pin_icon(False))
        self._aot_btn.setIconSize(QSize(20, 20))
        self._aot_btn.setToolTip("Toggle Always on Top")
        self._aot_btn.setCheckable(True)
        self._aot_btn.setFixedSize(36, 36)
        self._aot_btn.toggled.connect(self._toggle_always_on_top)
        layout.addWidget(self._aot_btn)

        # Fullscreen
        self._fs_btn = QPushButton()
        self._fs_btn.setIcon(get_fullscreen_icon())
        self._fs_btn.setIconSize(QSize(20, 20))
        self._fs_btn.setToolTip("Toggle Fullscreen (F11)")
        self._fs_btn.setFixedSize(36, 36)
        self._fs_btn.clicked.connect(self._toggle_fullscreen)
        layout.addWidget(self._fs_btn)

        return bar

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("statusPanel")
        panel.setFixedWidth(224)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(14)

        # Connection status icon & status pill
        status_box = QVBoxLayout()
        status_box.setSpacing(6)
        status_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status_icon = QLabel("●")
        self._status_icon.setFont(QFont("Segoe UI", 16))
        self._status_icon.setStyleSheet("color: #64748b;")
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_box.addWidget(self._status_icon)

        self._status_label = QLabel("Waiting for device…")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        status_box.addWidget(self._status_label)

        self._device_label = QLabel("")
        self._device_label.setObjectName("deviceLabel")
        self._device_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._device_label.setWordWrap(True)
        status_box.addWidget(self._device_label)

        layout.addLayout(status_box)
        layout.addStretch()

        # Start/Stop
        self._start_btn = QPushButton("Start Mirroring")
        self._start_btn.setObjectName("startButton")
        self._start_btn.clicked.connect(self._on_start_stop)
        layout.addWidget(self._start_btn)

        # Record
        self._rec_btn = QPushButton(" Record")
        self._rec_btn.setObjectName("recordButton")
        self._rec_btn.setIcon(get_record_icon(False))
        self._rec_btn.setIconSize(QSize(16, 16))
        self._rec_btn.clicked.connect(self._on_record_toggle)
        self._rec_btn.setEnabled(False)
        layout.addWidget(self._rec_btn)

        self._rec_timer_label = QLabel("")
        self._rec_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rec_timer_label.setStyleSheet("color: #e94560; font-weight: bold;")
        layout.addWidget(self._rec_timer_label)

        # Screenshot
        self._ss_btn = QPushButton(" Screenshot")
        self._ss_btn.setIcon(get_camera_icon())
        self._ss_btn.setIconSize(QSize(18, 18))
        self._ss_btn.clicked.connect(self._on_screenshot)
        self._ss_btn.setEnabled(False)
        layout.addWidget(self._ss_btn)

        # Audio controls
        audio_row = QHBoxLayout()
        self._mute_btn = QPushButton()
        self._mute_btn.setIcon(get_volume_icon(False))
        self._mute_btn.setIconSize(QSize(20, 20))
        self._mute_btn.setToolTip("Toggle Mute")
        self._mute_btn.setFixedWidth(40)
        self._mute_btn.setCheckable(True)
        self._mute_btn.toggled.connect(self._on_mute_toggle)
        self._audio_status = QLabel("Audio: On")
        self._audio_status.setStyleSheet("color: #8888aa; font-size: 11px;")
        audio_row.addWidget(self._mute_btn)
        audio_row.addWidget(self._audio_status)
        layout.addLayout(audio_row)

        return panel

    def _build_metric_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(42)
        bar.setObjectName("metricBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(28)

        metrics = [
            ("fps_lbl", "FPS", "0"),
            ("res_lbl", "Resolution", "—"),
            ("latency_lbl", "Latency", "—"),
            ("bitrate_lbl", "Bitrate", "—"),
            ("dropped_lbl", "Dropped", "0"),
            ("decoder_lbl", "Decoder", "—"),
            ("net_lbl", "Network", "—"),
        ]
        for attr, label_text, default in metrics:
            col = QVBoxLayout()
            col.setSpacing(1)
            val = QLabel(default)
            val.setObjectName("metricValue")
            val.setFont(QFont("Cascadia Code", 11, QFont.Weight.DemiBold))
            val.setStyleSheet("color: #38bdf8;")
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #64748b; text-transform: uppercase; font-size: 9px; letter-spacing: 0.5px;")
            col.addWidget(val, alignment=Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            setattr(self, f"_{attr}", val)
            layout.addLayout(col)

        layout.addStretch()
        return bar

    def _build_tray(self) -> None:
        self._tray = TrayIcon(self)
        self._tray.open_requested.connect(self.show_and_raise)
        self._tray.start_requested.connect(self._start_mirroring)
        self._tray.stop_requested.connect(self._stop_mirroring)
        self._tray.diagnostics_requested.connect(self._open_diagnostics)
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.exit_requested.connect(self._exit_app)
        self._tray.show()

    # ================================================================ SESSION
    def _connect_session(self) -> None:
        self._session.add_status_callback(self._on_session_status)

    def _on_session_status(self, state: SessionState, stats: SessionStats) -> None:
        # Called from any thread — use QTimer.singleShot to marshal to UI thread
        QTimer.singleShot(0, lambda: self._apply_session_state(state, stats))

    def _apply_session_state(self, state: SessionState, stats: SessionStats) -> None:
        state_display = {
            SessionState.IDLE: ("●", "#64748b", "Waiting for device…"),
            SessionState.CONNECTING: ("●", "#38bdf8", "Connecting…"),
            SessionState.AUTHENTICATING: ("●", "#38bdf8", "Authenticating…"),
            SessionState.STREAMING: ("●", "#10b981", "Connected & Mirroring"),
            SessionState.PAUSED: ("●", "#fbbf24", "Paused"),
            SessionState.DISCONNECTED: ("●", "#64748b", "Disconnected"),
            SessionState.ERROR: ("●", "#ef4444", "Error"),
        }
        icon, color, text = state_display.get(state, ("●", "#64748b", "—"))
        self._status_icon.setText(icon)
        self._status_icon.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._status_label.setText(text)
        self._device_label.setText(stats.connected_device)

        is_streaming = state == SessionState.STREAMING
        self._rec_btn.setEnabled(is_streaming)
        self._ss_btn.setEnabled(is_streaming)
        self._tray.set_streaming(is_streaming)

        if is_streaming:
            self._start_btn.setText("Stop Mirroring")
            self._start_btn.setObjectName("stopButton")
            cfg = get_config()
            if cfg.general.keep_screen_awake:
                _set_screen_awake(True)
        else:
            self._start_btn.setText("Start Mirroring")
            self._start_btn.setObjectName("startButton")
            _set_screen_awake(False)
            if self._recorder.is_recording:
                self._finalize_recording()

        self._status_bar.showMessage(f"{text} {stats.connected_device}".strip())
        self.style().unpolish(self._start_btn)
        self.style().polish(self._start_btn)

    # ================================================================ CONTROLS
    def _on_start_stop(self) -> None:
        if not self._is_running:
            self._start_mirroring()
        else:
            self._stop_mirroring()

    def _start_mirroring(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        log.info("Starting mirroring service…")

        cfg = get_config()

        # Start video and audio receivers first so they can be passed to AirPlayServer
        self._video_receiver = VideoReceiver("0.0.0.0", 7001)
        self._video_receiver.start()

        self._audio_receiver = AudioReceiver("0.0.0.0", 7011)
        self._audio_receiver.start()

        # Start RTSP server with video & audio receiver references for FairPlay key setup
        self._server = AirPlayServer(
            self._session,
            video_receiver=self._video_receiver,
            audio_receiver=self._audio_receiver,
            audio_output=self._audio_output,
        )
        self._server.start()

        # Start video decoder
        self._video_decoder = VideoDecoder(
            self._video_receiver.frame_queue,
            hw_accel=cfg.video.hw_accel,
        )
        self._video_decoder.set_frame_callback(self._frame_bridge.submit)
        self._video_decoder.start()

        # Start audio decoder and output
        self._audio_decoder = AudioDecoder(self._audio_receiver.audio_queue)
        self._audio_decoder.start()
        if cfg.audio.enabled:
            self._audio_output.set_volume(cfg.audio.volume)
            self._audio_output.set_muted(cfg.audio.muted)
            self._audio_output.start()
            self._start_audio_feed_thread()

        # Start NTP timing sync
        self._ntp_sync = NTPSyncServer("0.0.0.0", 7012)
        self._ntp_sync.start()

        # Advertise via mDNS
        self._mdns.start()

        self._status_bar.showMessage("G-Mirror is advertising on your network — open Screen Mirroring on iPhone")
        self._tray.show_message("G-Mirror", "Ready — open Screen Mirroring on iPhone")

    def _stop_mirroring(self) -> None:
        if not self._is_running:
            return
        self._is_running = False
        log.info("Stopping mirroring service…")

        self._mdns.stop()
        if self._ntp_sync:
            self._ntp_sync.stop()
        if self._server:
            self._server.stop()
        if self._video_decoder:
            self._video_decoder.stop()
        if self._video_receiver:
            self._video_receiver.stop()
        if self._audio_decoder:
            self._audio_decoder.stop()
        if self._audio_receiver:
            self._audio_receiver.stop()
        self._audio_output.stop()

        self._session.set_disconnected()
        self._video_widget.clear_frame()
        self._status_bar.showMessage("Mirroring stopped.")

    def _start_audio_feed_thread(self) -> None:
        """Feed decoded audio to sounddevice output."""
        def _feed():
            while self._is_running and self._audio_decoder:
                try:
                    pcm = self._audio_decoder.output_queue.get(timeout=0.2)
                    self._audio_output.feed(pcm)
                except queue.Empty:
                    continue
                except Exception as e:
                    log.debug("Audio feed error: %s", e)
        t = threading.Thread(target=_feed, daemon=True, name="AudioFeed")
        t.start()

    def _on_frame_ready(self) -> None:
        """Called on UI thread when a decoded frame is available."""
        item = self._frame_bridge.take()
        if item is None:
            return
        img, av_frame = item
        self._last_av_frame = av_frame
        self._video_widget.display_frame(img)

        # Feed to recorder if active
        if self._recorder.is_recording:
            self._recorder.write_video_frame(av_frame)

    # ================================================================ STATS
    def _update_stats_display(self) -> None:
        if not self._is_running or not self._video_decoder:
            return
        fps = self._video_decoder.fps
        res = self._video_decoder.resolution
        latency = self._video_decoder.latency_ms
        dropped = self._video_receiver.dropped_frames if self._video_receiver else 0
        bitrate = self._video_receiver.bitrate_kbps if self._video_receiver else 0.0
        decoder = self._video_decoder.decoder_name

        self._fps_lbl.setText(f"{fps:.1f}")
        self._res_lbl.setText(res)
        self._latency_lbl.setText(f"{latency:.1f} ms" if latency > 0 else "—")
        self._bitrate_lbl.setText(f"{bitrate:.0f} kbps")
        self._dropped_lbl.setText(str(dropped))
        self._decoder_lbl.setText(decoder)

        # Update session stats
        self._session.update_stats(
            fps=fps, resolution=res, dropped_frames=dropped,
            bitrate_kbps=bitrate, decoder=decoder,
        )

        # Update overlay
        cfg = get_config()
        if cfg.general.show_performance_overlay:
            self._video_widget.update_overlay_stats({
                "fps": fps, "resolution": res, "bitrate_kbps": bitrate,
                "latency_ms": latency, "dropped_frames": dropped, "decoder": decoder,
            })

    # ================================================================ RECORDING
    def _on_record_toggle(self) -> None:
        if self._recorder.is_recording:
            self._finalize_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        cfg = get_config()
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = str(Path(cfg.recording.folder) / f"GMirror_{ts}.mp4")

        if self._recorder.start(
            path,
            fps=cfg.recording.fps,
            bitrate_kbps=cfg.recording.bitrate_kbps,
            include_audio=cfg.recording.include_audio,
        ):
            self._rec_btn.setText(" Stop Recording")
            self._rec_btn.setIcon(get_record_icon(True))
            self._rec_timer.start()
            self._status_bar.showMessage(f"Recording: {path}")
            log.info("Recording started: %s", path)
        else:
            QMessageBox.warning(self, "Recording Failed", "Could not start recording. Check the output folder.")

    def _finalize_recording(self) -> None:
        self._rec_timer.stop()
        self._rec_timer_label.setText("")
        path = self._recorder.stop()
        self._rec_btn.setText(" Record")
        self._rec_btn.setIcon(get_record_icon(False))
        if path:
            self._status_bar.showMessage(f"Recording saved: {path}")
            self._tray.show_message("G-Mirror", f"Recording saved:\n{path}")

    def _update_rec_timer(self) -> None:
        elapsed = int(self._recorder.elapsed_seconds)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._rec_timer_label.setText(f"● {h:02d}:{m:02d}:{s:02d}")

    # ================================================================ SCREENSHOT
    def _on_screenshot(self) -> None:
        if self._last_av_frame is None:
            return
        cfg = get_config()
        path = capture_screenshot(self._last_av_frame, cfg.general.screenshot_folder)
        if path:
            self._status_bar.showMessage(f"Screenshot saved: {path}")
            self._tray.show_message("G-Mirror", f"Screenshot saved:\n{Path(path).name}")

    # ================================================================ FULLSCREEN
    def _toggle_fullscreen(self) -> None:
        if self._is_fullscreen:
            # Exit fullscreen: restore all controls and padding
            self._video_widget.hide_fullscreen_hint()
            self._toolbar.show()
            self._side_panel.show()
            self._metric_bar.show()
            self._status_bar.show()
            self._content_layout.setContentsMargins(12, 10, 12, 10)
            self._content_layout.setSpacing(10)

            self.showNormal()
            self._is_fullscreen = False
        else:
            # Enter pure fullscreen: hide EVERYTHING except the video surface
            self._toolbar.hide()
            self._side_panel.hide()
            self._metric_bar.hide()
            self._status_bar.hide()
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            self._content_layout.setSpacing(0)

            self.showFullScreen()
            self._is_fullscreen = True

            # Display elegant exit hint directly on the video canvas
            self._video_widget.show_fullscreen_hint(2800)

    def _on_escape_pressed(self) -> None:
        if self._is_fullscreen:
            self._toggle_fullscreen()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self._is_fullscreen:
                self._toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    # ================================================================ MISC UI
    def _toggle_overlay(self) -> None:
        cfg = get_config()
        cfg.general.show_performance_overlay = not cfg.general.show_performance_overlay
        save_config()
        self._video_widget.set_overlay_visible(cfg.general.show_performance_overlay)

    def _toggle_always_on_top(self, checked: bool) -> None:
        try:
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOACTIVATE = 0x0010
            hwnd = int(self.winId())
            target = HWND_TOPMOST if checked else HWND_NOTOPMOST
            ctypes.windll.user32.SetWindowPos(
                hwnd, target, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            )
        except Exception as e:
            log.debug("SetWindowPos topmost error: %s", e)
        get_config().general.always_on_top = checked
        save_config()
        self._aot_btn.setIcon(get_pin_icon(pinned=checked))

    def _on_mute_toggle(self, checked: bool) -> None:
        self._audio_output.set_muted(checked)
        self._mute_btn.setIcon(get_volume_icon(checked))
        self._audio_status.setText("Audio: Muted" if checked else "Audio: On")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._apply_new_settings)
        dlg.exec()

    def _apply_new_settings(self) -> None:
        cfg = get_config()
        self._apply_window_settings(cfg)
        from ui.styles.theme_manager import apply_theme
        apply_theme(QApplication.instance(), cfg.general.theme)

    def _apply_window_settings(self, cfg) -> None:
        self._aot_btn.blockSignals(True)
        self._aot_btn.setChecked(cfg.general.always_on_top)
        self._aot_btn.setIcon(get_pin_icon(pinned=cfg.general.always_on_top))
        self._aot_btn.blockSignals(False)
        if cfg.general.always_on_top:
            self._toggle_always_on_top(True)

    def _open_diagnostics(self) -> None:
        dlg = DiagnosticsWindow(self)
        dlg.exec()

    # ================================================================ LIFECYCLE
    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _exit_app(self) -> None:
        self._stop_mirroring()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        cfg = get_config()
        if cfg.general.minimize_to_tray and self._tray:
            event.ignore()
            self.hide()
            self._tray.show_message(
                "G-Mirror",
                "G-Mirror is running in the background.\nRight-click tray icon to exit."
            )
        else:
            self._stop_mirroring()
            event.accept()
            QApplication.instance().quit()
