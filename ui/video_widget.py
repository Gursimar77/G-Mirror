"""
G-Mirror Video Widget.

A QWidget that renders decoded video frames as fast as possible.
Uses QPainter with a QImage buffer — compatible with all GPU configurations.
Maintains aspect ratio, supports fullscreen, and optionally renders a
performance overlay.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QRect, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy

log = logging.getLogger(__name__)


class VideoWidget(QWidget):
    """
    Video display surface.

    Accepts frames via display_frame(frame_or_image) called from any thread.
    Schedules Qt repaints on the UI thread via QTimer and coalesced updates.
    """

    double_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._show_overlay = False
        self._overlay_stats: dict = {}
        self._last_frame_time = 0.0

        # Fullscreen exit hint overlay state
        self._fs_hint_visible = False
        self._fs_hint_timer = QTimer(self)
        self._fs_hint_timer.setSingleShot(True)
        self._fs_hint_timer.timeout.connect(self._hide_fs_hint)

        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("videoContainer")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def display_frame(self, frame_or_image) -> None:
        """
        Accepts either a ready QImage or an av.VideoFrame.
        Safe to call from the UI thread.
        """
        try:
            if isinstance(frame_or_image, QImage):
                self._image = frame_or_image
            else:
                bgra = frame_or_image.reformat(format="bgra")
                p = bgra.planes[0]
                self._image = QImage(
                    p, bgra.width, bgra.height, p.line_size, QImage.Format.Format_RGB32
                ).copy()
            self._last_frame_time = time.perf_counter()
            self.update()
        except Exception as e:
            log.debug("Frame display error: %s", e)

    def clear_frame(self) -> None:
        self._image = None
        self.update()

    def set_overlay_visible(self, visible: bool) -> None:
        self._show_overlay = visible
        self.update()

    def update_overlay_stats(self, stats: dict) -> None:
        self._overlay_stats = stats

    def show_fullscreen_hint(self, duration_ms: int = 2800) -> None:
        self._fs_hint_visible = True
        self._fs_hint_timer.stop()
        self._fs_hint_timer.start(duration_ms)
        self.update()

    def hide_fullscreen_hint(self) -> None:
        self._fs_hint_visible = False
        self._fs_hint_timer.stop()
        self.update()

    def _hide_fs_hint(self) -> None:
        self._fs_hint_visible = False
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()

        if self._image is None:
            # Elegant minimal standby state
            painter.fillRect(rect, QColor("#090b0e"))
            
            # Subtle Apple AirPlay device icon outline
            cx, cy = rect.width() / 2.0, rect.height() / 2.0 - 18
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawRoundedRect(QRectF(cx - 24, cy - 32, 48, 64), 7, 7)
            # Screen inner area
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
            painter.drawRoundedRect(QRectF(cx - 20, cy - 26, 40, 52), 4, 4)
            # Home indicator line
            painter.setPen(QPen(QColor(255, 255, 255, 40), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 8, cy + 20), QPointF(cx + 8, cy + 20))

            # Primary message
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
            painter.setPen(QColor("#cbd5e1"))
            text_rect = QRect(0, int(cy + 46), rect.width(), 26)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "Ready for Screen Mirroring")

            # Secondary hint
            painter.setFont(QFont("Segoe UI", 11))
            painter.setPen(QColor("#64748b"))
            sub_rect = QRect(0, int(cy + 72), rect.width(), 22)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "Open Control Center on your iPhone and tap Screen Mirroring")

            if self._fs_hint_visible:
                self._draw_fs_hint(painter, rect)
            return

        # Letterbox / pillarbox: maintain aspect ratio
        iw, ih = self._image.width(), self._image.height()
        rw, rh = rect.width(), rect.height()

        scale = min(rw / iw, rh / ih)
        dw = int(iw * scale)
        dh = int(ih * scale)
        dx = (rw - dw) // 2
        dy = (rh - dh) // 2

        painter.fillRect(rect, QColor(0, 0, 0))
        target_rect = QRect(dx, dy, dw, dh)
        # Direct hardware-accelerated raster blit without CPU-intensive .scaled()
        painter.drawImage(target_rect, self._image)

        if self._show_overlay and self._overlay_stats:
            self._draw_overlay(painter, dx, dy)

        if self._fs_hint_visible:
            self._draw_fs_hint(painter, rect)

    def _draw_fs_hint(self, painter: QPainter, rect: QRect) -> None:
        msg = "Press Esc or F11 to exit full screen"
        font = QFont("Segoe UI", 10, QFont.Weight.Medium)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(msg)
        text_h = fm.height()
        pad_x, pad_y = 18, 7
        pw = text_w + pad_x * 2
        ph = text_h + pad_y * 2
        px = (rect.width() - pw) / 2.0
        py = 28.0
        pill_rect = QRectF(px, py, pw, ph)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 38), 1.0))
        painter.setBrush(QColor(15, 20, 26, 225))
        painter.drawRoundedRect(pill_rect, ph / 2.0, ph / 2.0)

        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, msg)

    def _draw_overlay(self, painter: QPainter, x: int, y: int) -> None:
        stats = self._overlay_stats
        lines = [
            f"FPS: {stats.get('fps', 0):.1f}",
            f"Res: {stats.get('resolution', '—')}",
            f"Bitrate: {stats.get('bitrate_kbps', 0):.0f} kbps",
            f"Latency: {stats.get('latency_ms', 0):.0f} ms",
            f"Dropped: {stats.get('dropped_frames', 0)}",
            f"Decoder: {stats.get('decoder', '—')}",
        ]
        font = QFont("Cascadia Code", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(font)
        fm = painter.fontMetrics()
        lh = fm.height() + 4
        pw = max(fm.horizontalAdvance(l) for l in lines) + 20
        ph = lh * len(lines) + 12

        ox, oy = x + 16, y + 16
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.setBrush(QColor(13, 17, 23, 210))
        painter.drawRoundedRect(QRectF(ox, oy, pw, ph), 8, 8)

        painter.setPen(QColor("#38bdf8"))
        for i, line in enumerate(lines):
            painter.drawText(ox + 10, oy + 8 + (i + 1) * lh - 4, line)

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_F11, Qt.Key.Key_Escape):
            event.ignore()
        else:
            super().keyPressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(854, 480)
