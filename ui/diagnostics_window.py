"""
G-Mirror Diagnostics Window.

Displays connection diagnostic results with clear pass/warn/fail icons
and user-friendly explanations. No technical jargon without explanation.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QTextEdit, QProgressBar,
    QApplication, QFileDialog
)

from gmirror.diagnostics.network_checker import NetworkChecker, DiagnosticReport, CheckResult
from gmirror.diagnostics.report import export_report

log = logging.getLogger(__name__)


class _SignalBridge(QObject):
    progress = Signal(str, int)
    finished = Signal(object)  # DiagnosticReport


class DiagnosticsWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("G-Mirror — Connection Diagnostics")
        self.setMinimumSize(680, 560)
        self._report: Optional[DiagnosticReport] = None
        self._bridge = _SignalBridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.finished.connect(self._on_finished)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Connection Diagnostics")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        self._run_btn = QPushButton("▶  Run Diagnostics")
        self._run_btn.setObjectName("startButton")
        self._run_btn.clicked.connect(self.run_diagnostics)
        header.addWidget(self._run_btn)
        layout.addLayout(header)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

        # Scroll area for results
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setSpacing(6)
        self._results_layout.addStretch()
        scroll.setWidget(self._results_widget)
        layout.addWidget(scroll, stretch=1)

        # Summary
        self._summary_label = QLabel("")
        self._summary_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(self._summary_label)

        # Bottom buttons
        btns = QHBoxLayout()
        self._copy_btn = QPushButton("📋  Copy Report")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_report)

        self._export_btn = QPushButton("💾  Export Report")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_report)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)

        btns.addWidget(self._copy_btn)
        btns.addWidget(self._export_btn)
        btns.addStretch()
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        # Placeholder text
        self._placeholder = QLabel(
            "Click 'Run Diagnostics' to test your network configuration\n"
            "and check AirPlay compatibility."
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #8888aa; font-size: 14px;")
        self._results_layout.insertWidget(0, self._placeholder)

    def run_diagnostics(self) -> None:
        self._run_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_label.setVisible(True)
        self._progress_bar.setValue(0)
        self._copy_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._summary_label.setText("")

        # Clear old results
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def _worker():
            def _progress(name: str, pct: int):
                self._bridge.progress.emit(name, pct)

            checker = NetworkChecker(progress_callback=_progress)
            report = checker.run()
            self._bridge.finished.emit(report)

        threading.Thread(target=_worker, daemon=True, name="DiagWorker").start()

    def _on_progress(self, name: str, pct: int) -> None:
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"Checking: {name}…")

    def _on_finished(self, report: DiagnosticReport) -> None:
        self._report = report
        self._progress_bar.setValue(100)
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._run_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)
        self._export_btn.setEnabled(True)

        for check in report.checks:
            row = self._make_check_row(check)
            self._results_layout.addWidget(row)
        self._results_layout.addStretch()

        summary = report.summary()
        self._summary_label.setText(summary)

    def _make_check_row(self, check) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        icon_color = {
            CheckResult.OK: ("✓", "#4ecca3"),
            CheckResult.WARNING: ("⚠", "#f39c12"),
            CheckResult.FAIL: ("✕", "#e94560"),
            CheckResult.SKIP: ("—", "#888888"),
        }[check.status]

        header = QHBoxLayout()
        icon_lbl = QLabel(icon_color[0])
        icon_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {icon_color[1]};")
        icon_lbl.setFixedWidth(24)

        name_lbl = QLabel(check.name)
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.addWidget(icon_lbl)
        header.addWidget(name_lbl)
        header.addStretch()
        layout.addLayout(header)

        if check.message:
            msg_lbl = QLabel(check.message)
            msg_lbl.setWordWrap(True)
            msg_lbl.setFont(QFont("Segoe UI", 11))
            msg_lbl.setContentsMargins(28, 0, 0, 0)
            layout.addWidget(msg_lbl)

        if check.suggestion and check.status != CheckResult.OK:
            sug_lbl = QLabel(f"💡 {check.suggestion}")
            sug_lbl.setWordWrap(True)
            sug_lbl.setFont(QFont("Segoe UI", 10))
            sug_lbl.setStyleSheet("color: #f39c12;")
            sug_lbl.setContentsMargins(28, 0, 0, 0)
            layout.addWidget(sug_lbl)

        return frame

    def _copy_report(self) -> None:
        if self._report:
            QApplication.clipboard().setText(self._report.to_text())
            self._copy_btn.setText("✓ Copied!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self._copy_btn.setText("📋  Copy Report"))

    def _export_report(self) -> None:
        if not self._report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Diagnostic Report", "GMirror_Diagnostic.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            export_report(self._report, path)
