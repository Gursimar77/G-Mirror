"""
G-Mirror Settings Dialog.

Organized settings across 5 tabs: General, Video, Audio, Recording, Network/Advanced.
Changes are applied and persisted in real time.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QCheckBox, QSlider, QSpinBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QGroupBox, QFileDialog, QFormLayout,
    QDialogButtonBox, QMessageBox
)

from gmirror.settings.config import get_config, save_config, reset_config
from gmirror.render.audio_output import list_output_devices
from gmirror.logging_setup import get_log_dir

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("G-Mirror Settings")
        self.setMinimumSize(580, 480)
        self._cfg = get_config()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_video_tab(), "Video")
        tabs.addTab(self._build_audio_tab(), "Audio")
        tabs.addTab(self._build_recording_tab(), "Recording")
        tabs.addTab(self._build_advanced_tab(), "Advanced")
        layout.addWidget(tabs, stretch=1)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save_and_close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------ General
    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System", "Dark", "Light"])
        self._theme_combo.setCurrentText(self._cfg.general.theme)
        form.addRow("Theme:", self._theme_combo)

        self._start_windows = QCheckBox("Start with Windows")
        self._start_windows.setChecked(self._cfg.general.start_with_windows)
        form.addRow("", self._start_windows)

        self._start_min = QCheckBox("Start minimized")
        self._start_min.setChecked(self._cfg.general.start_minimized)
        form.addRow("", self._start_min)

        self._min_tray = QCheckBox("Minimize to system tray")
        self._min_tray.setChecked(self._cfg.general.minimize_to_tray)
        form.addRow("", self._min_tray)

        self._always_top = QCheckBox("Always on top")
        self._always_top.setChecked(self._cfg.general.always_on_top)
        form.addRow("", self._always_top)

        self._keep_awake = QCheckBox("Keep screen awake while mirroring")
        self._keep_awake.setChecked(self._cfg.general.keep_screen_awake)
        form.addRow("", self._keep_awake)

        self._perf_overlay = QCheckBox("Show performance overlay")
        self._perf_overlay.setChecked(self._cfg.general.show_performance_overlay)
        form.addRow("", self._perf_overlay)

        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(self._cfg.general.check_for_updates)
        form.addRow("", self._check_updates)

        return w

    # ------------------------------------------------------------------ Video
    def _build_video_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self._res_combo = QComboBox()
        self._res_combo.addItems(["Auto", "1080p", "720p", "540p"])
        self._res_combo.setCurrentText(self._cfg.video.resolution)
        form.addRow("Resolution:", self._res_combo)

        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["Auto", "60", "30"])
        self._fps_combo.setCurrentText(self._cfg.video.fps)
        form.addRow("FPS:", self._fps_combo)

        self._quality_combo = QComboBox()
        self._quality_combo.addItems(["Low Latency", "Balanced", "Quality", "Maximum Quality"])
        self._quality_combo.setCurrentText(self._cfg.video.quality)
        form.addRow("Quality Preset:", self._quality_combo)

        self._hw_accel = QCheckBox("Hardware-accelerated decode (DXVA2/D3D11VA)")
        self._hw_accel.setChecked(self._cfg.video.hw_accel)
        form.addRow("", self._hw_accel)

        self._low_latency = QCheckBox("Low latency mode (minimize buffering)")
        self._low_latency.setChecked(self._cfg.video.low_latency)
        form.addRow("", self._low_latency)

        return w

    # ------------------------------------------------------------------ Audio
    def _build_audio_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self._audio_enabled = QCheckBox("Enable audio")
        self._audio_enabled.setChecked(self._cfg.audio.enabled)
        form.addRow("", self._audio_enabled)

        self._audio_device = QComboBox()
        self._audio_device.addItems(list_output_devices())
        self._audio_device.setCurrentText(self._cfg.audio.output_device)
        form.addRow("Output device:", self._audio_device)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(int(self._cfg.audio.volume * 100))
        form.addRow("Volume:", self._vol_slider)

        self._mute = QCheckBox("Mute")
        self._mute.setChecked(self._cfg.audio.muted)
        form.addRow("", self._mute)

        return w

    # ------------------------------------------------------------------ Recording
    def _build_recording_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        folder_row = QHBoxLayout()
        self._rec_folder = QLineEdit(self._cfg.recording.folder)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_rec_folder)
        folder_row.addWidget(self._rec_folder)
        folder_row.addWidget(browse_btn)
        form.addRow("Save to:", folder_row)

        self._rec_format = QComboBox()
        self._rec_format.addItems(["mp4"])
        form.addRow("Format:", self._rec_format)

        self._rec_fps = QSpinBox()
        self._rec_fps.setRange(15, 60)
        self._rec_fps.setValue(self._cfg.recording.fps)
        form.addRow("FPS:", self._rec_fps)

        self._rec_bitrate = QSpinBox()
        self._rec_bitrate.setRange(1000, 50000)
        self._rec_bitrate.setSingleStep(1000)
        self._rec_bitrate.setSuffix(" kbps")
        self._rec_bitrate.setValue(self._cfg.recording.bitrate_kbps)
        form.addRow("Video bitrate:", self._rec_bitrate)

        self._rec_audio = QCheckBox("Record audio")
        self._rec_audio.setChecked(self._cfg.recording.include_audio)
        form.addRow("", self._rec_audio)

        # Screenshot folder
        ss_row = QHBoxLayout()
        self._ss_folder = QLineEdit(self._cfg.general.screenshot_folder)
        ss_browse = QPushButton("Browse…")
        ss_browse.clicked.connect(self._browse_ss_folder)
        ss_row.addWidget(self._ss_folder)
        ss_row.addWidget(ss_browse)
        form.addRow("Screenshot folder:", ss_row)

        return w

    # ------------------------------------------------------------------ Advanced
    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        # Network
        net_group = QGroupBox("Network")
        net_form = QFormLayout(net_group)

        self._receiver_name = QLineEdit(self._cfg.network.receiver_name)
        net_form.addRow("Receiver name:", self._receiver_name)

        self._net_port = QSpinBox()
        self._net_port.setRange(1024, 65535)
        self._net_port.setValue(self._cfg.network.port)
        net_form.addRow("AirPlay port:", self._net_port)
        layout.addWidget(net_group)

        # Logs
        log_group = QGroupBox("Logs & Debug")
        log_layout = QHBoxLayout(log_group)
        open_logs_btn = QPushButton("Open Logs Folder")
        open_logs_btn.clicked.connect(self._open_logs)
        log_layout.addWidget(open_logs_btn)
        layout.addWidget(log_group)

        # Reset
        reset_group = QGroupBox("Reset")
        reset_layout = QVBoxLayout(reset_group)
        reset_btn = QPushButton("Reset All Settings to Defaults")
        reset_btn.setObjectName("stopButton")
        reset_btn.clicked.connect(self._reset_settings)
        reset_layout.addWidget(reset_btn)
        layout.addWidget(reset_group)

        layout.addStretch()
        return w

    # ------------------------------------------------------------------ Actions
    def _browse_rec_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Recording Folder")
        if path:
            self._rec_folder.setText(path)

    def _browse_ss_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Screenshot Folder")
        if path:
            self._ss_folder.setText(path)

    def _open_logs(self) -> None:
        log_dir = str(get_log_dir())
        os.makedirs(log_dir, exist_ok=True)
        subprocess.Popen(["explorer", log_dir])

    def _reset_settings(self) -> None:
        if QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            reset_config()
            self.reject()

    def _save_and_close(self) -> None:
        cfg = self._cfg
        cfg.general.theme = self._theme_combo.currentText()
        cfg.general.start_with_windows = self._start_windows.isChecked()
        cfg.general.start_minimized = self._start_min.isChecked()
        cfg.general.minimize_to_tray = self._min_tray.isChecked()
        cfg.general.always_on_top = self._always_top.isChecked()
        cfg.general.keep_screen_awake = self._keep_awake.isChecked()
        cfg.general.show_performance_overlay = self._perf_overlay.isChecked()
        cfg.general.check_for_updates = self._check_updates.isChecked()
        cfg.general.screenshot_folder = self._ss_folder.text()

        cfg.video.resolution = self._res_combo.currentText()
        cfg.video.fps = self._fps_combo.currentText()
        cfg.video.quality = self._quality_combo.currentText()
        cfg.video.hw_accel = self._hw_accel.isChecked()
        cfg.video.low_latency = self._low_latency.isChecked()

        cfg.audio.enabled = self._audio_enabled.isChecked()
        cfg.audio.output_device = self._audio_device.currentText()
        cfg.audio.volume = self._vol_slider.value() / 100.0
        cfg.audio.muted = self._mute.isChecked()

        cfg.recording.folder = self._rec_folder.text()
        cfg.recording.fps = self._rec_fps.value()
        cfg.recording.bitrate_kbps = self._rec_bitrate.value()
        cfg.recording.include_audio = self._rec_audio.isChecked()

        cfg.network.receiver_name = self._receiver_name.text() or "G-Mirror"
        cfg.network.port = self._net_port.value()

        save_config()
        self.settings_changed.emit()
        self.accept()
