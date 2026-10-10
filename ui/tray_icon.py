"""
G-Mirror System Tray Icon.
Provides tray menu: Open, Start/Stop, Diagnostics, Settings, Exit.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


def _make_tray_icon(color: str = "#4ecca3") -> QIcon:
    """Generate a simple G-Mirror tray icon programmatically."""
    pix = QPixmap(32, 32)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Phone silhouette
    p.setBrush(QColor(color))
    p.setPen(QColor(color))
    p.drawRoundedRect(8, 2, 16, 28, 3, 3)
    p.setBrush(QColor(18, 18, 31))
    p.drawRoundedRect(10, 5, 12, 22, 2, 2)
    # Screen reflection dot
    p.setBrush(QColor(color))
    p.drawEllipse(15, 25, 3, 3)
    p.end()
    return QIcon(pix)


class TrayIcon(QObject):
    open_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    diagnostics_requested = Signal()
    settings_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("G-Mirror — AirPlay Receiver")

        self._menu = QMenu()
        self._action_open = self._menu.addAction("Open G-Mirror")
        self._menu.addSeparator()
        self._action_start = self._menu.addAction("Start Mirroring")
        self._action_stop = self._menu.addAction("Stop Mirroring")
        self._action_stop.setEnabled(False)
        self._menu.addSeparator()
        self._action_diag = self._menu.addAction("Connection Diagnostics")
        self._action_settings = self._menu.addAction("Settings")
        self._menu.addSeparator()
        self._action_exit = self._menu.addAction("Exit")

        self._tray.setContextMenu(self._menu)

        # Connections
        self._action_open.triggered.connect(self.open_requested)
        self._action_start.triggered.connect(self.start_requested)
        self._action_stop.triggered.connect(self.stop_requested)
        self._action_diag.triggered.connect(self.diagnostics_requested)
        self._action_settings.triggered.connect(self.settings_requested)
        self._action_exit.triggered.connect(self.exit_requested)
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def hide_tray(self) -> None:
        self._tray.hide()

    def set_streaming(self, active: bool) -> None:
        self._action_start.setEnabled(not active)
        self._action_stop.setEnabled(active)
        tip = "G-Mirror — Mirroring active" if active else "G-Mirror — AirPlay Receiver"
        self._tray.setToolTip(tip)
        self._tray.setIcon(_make_tray_icon("#e94560" if active else "#4ecca3"))

    def show_message(self, title: str, msg: str) -> None:
        self._tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_requested.emit()
