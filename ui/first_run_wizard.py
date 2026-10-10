"""
G-Mirror First-Run Wizard.

A step-by-step guide that runs on first launch to help users connect
their iPhone to G-Mirror.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QFrame, QProgressBar
)

log = logging.getLogger(__name__)

STEPS = [
    {
        "title": "Welcome to G-Mirror",
        "icon": "📱",
        "body": (
            "G-Mirror lets you wirelessly mirror your iPhone screen "
            "to this Windows PC — using your iPhone's built-in AirPlay feature.\n\n"
            "No iPhone companion app required.\n"
            "No account. No subscription. Completely free and open-source."
        ),
    },
    {
        "title": "Allow Firewall Access",
        "icon": "🔒",
        "body": (
            "When Windows asks to allow G-Mirror through the firewall,\n"
            "click Allow Access on both prompts.\n\n"
            "G-Mirror needs two ports open:\n"
            "  • TCP 7000 — AirPlay control channel\n"
            "  • UDP 5353 — Device discovery (mDNS)\n\n"
            "G-Mirror does not connect to the internet."
        ),
    },
    {
        "title": "Connect to the Same Wi-Fi",
        "icon": "📶",
        "body": (
            "Both your iPhone and this PC must be connected to\n"
            "the same Wi-Fi network or local area network (LAN).\n\n"
            "G-Mirror does not work over mobile data or different networks."
        ),
    },
    {
        "title": "Open Screen Mirroring on iPhone",
        "icon": "🪞",
        "body": (
            "On your iPhone:\n\n"
            "1. Swipe down from the top-right corner\n"
            "   to open Control Center.\n\n"
            "2. Tap Screen Mirroring  (the rectangle with a triangle).\n\n"
            "3. Wait a moment for G-Mirror to appear in the list.\n\n"
            "4. Tap G-Mirror to start mirroring."
        ),
    },
    {
        "title": "You're Ready!",
        "icon": "✅",
        "body": (
            "G-Mirror is now running and advertising itself on your network.\n\n"
            "Your iPhone should show 'G-Mirror' in the Screen Mirroring list "
            "within a few seconds.\n\n"
            "If it doesn't appear, use Connection Diagnostics to troubleshoot."
        ),
    },
]


class FirstRunWizard(QDialog):
    finished_signal = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("G-Mirror — Setup")
        self.setFixedSize(560, 420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._current_step = 0
        self._build_ui()
        self._show_step(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(20)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, len(STEPS) - 1)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        layout.addWidget(self._progress)

        # Icon
        self._icon_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFont(QFont("Segoe UI Emoji", 40))
        layout.addWidget(self._icon_label)

        # Title
        self._title_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(self._title_label)

        # Body text
        self._body_label = QLabel("")
        self._body_label.setWordWrap(True)
        self._body_label.setFont(QFont("Segoe UI", 11))
        self._body_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._body_label, stretch=1)

        # Navigation
        nav = QHBoxLayout()
        self._btn_back = QPushButton("Back")
        self._btn_back.setEnabled(False)
        self._btn_back.clicked.connect(self._prev_step)

        self._btn_next = QPushButton("Next →")
        self._btn_next.setObjectName("startButton")
        self._btn_next.clicked.connect(self._next_step)

        nav.addWidget(self._btn_back)
        nav.addStretch()
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

    def _show_step(self, index: int) -> None:
        step = STEPS[index]
        self._icon_label.setText(step["icon"])
        self._title_label.setText(step["title"])
        self._body_label.setText(step["body"])
        self._progress.setValue(index)
        self._btn_back.setEnabled(index > 0)
        is_last = index == len(STEPS) - 1
        self._btn_next.setText("Get Started" if is_last else "Next →")

    def _next_step(self) -> None:
        if self._current_step < len(STEPS) - 1:
            self._current_step += 1
            self._show_step(self._current_step)
        else:
            self._complete()

    def _prev_step(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self._show_step(self._current_step)

    def _complete(self) -> None:
        from gmirror.settings.config import get_config, save_config
        cfg = get_config()
        cfg.general.first_run_complete = True
        save_config()
        self.finished_signal.emit()
        self.accept()
