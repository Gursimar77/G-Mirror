"""
G-Mirror Vector Icon Generator.
Generates clean, razor-sharp vector QIcons using QPainter.
Guarantees 100% reliable rendering on all Windows versions without
depending on system emoji fonts or missing unicode glyphs.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath


def _create_canvas(size: int = 32) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pixmap, painter


def get_settings_icon(color: str = "#e0e0e0", size: int = 32) -> QIcon:
    """Draw a clean modern gear icon."""
    pix, p = _create_canvas(size)
    c = QColor(color)
    p.setPen(QPen(c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)

    center = size / 2.0
    r_outer = size * 0.38
    r_inner = size * 0.16

    # Draw 6 cogs
    import math
    cog_path = QPainterPath()
    num_teeth = 6
    for i in range(num_teeth):
        angle = i * (2 * math.pi / num_teeth)
        a1 = angle - 0.22
        a2 = angle + 0.22
        x1 = center + r_outer * 0.8 * math.cos(a1)
        y1 = center + r_outer * 0.8 * math.sin(a1)
        x2 = center + r_outer * math.cos(a1 + 0.05)
        y2 = center + r_outer * math.sin(a1 + 0.05)
        x3 = center + r_outer * math.cos(a2 - 0.05)
        y3 = center + r_outer * math.sin(a2 - 0.05)
        x4 = center + r_outer * 0.8 * math.cos(a2)
        y4 = center + r_outer * 0.8 * math.sin(a2)

        if i == 0:
            cog_path.moveTo(x1, y1)
        else:
            cog_path.lineTo(x1, y1)
        cog_path.lineTo(x2, y2)
        cog_path.lineTo(x3, y3)
        cog_path.lineTo(x4, y4)

    cog_path.closeSubpath()
    p.setBrush(QBrush(c))
    p.drawPath(cog_path)

    # Cut out center hole
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.setBrush(QBrush(Qt.GlobalColor.black))
    p.drawEllipse(QPointF(center, center), r_inner, r_inner)

    p.end()
    return QIcon(pix)


def get_diagnostics_icon(color: str = "#e0e0e0", size: int = 32) -> QIcon:
    """Draw a magnifying glass with a pulse / check line."""
    pix, p = _create_canvas(size)
    c = QColor(color)
    p.setPen(QPen(c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    # Glass circle
    p.drawEllipse(QRectF(5, 5, 15, 15))
    # Handle
    p.drawLine(16, 16, 26, 26)
    # Checkmark inside glass
    p.setPen(QPen(QColor("#4ecca3"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(8, 12, 11, 15)
    p.drawLine(11, 15, 16, 9)

    p.end()
    return QIcon(pix)


def get_overlay_icon(color: str = "#e0e0e0", size: int = 32) -> QIcon:
    """Draw a bar-chart / performance stats icon."""
    pix, p = _create_canvas(size)
    c = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(c))

    # 3 vertical chart bars
    p.drawRoundedRect(QRectF(6, 15, 5, 11), 1.5, 1.5)
    p.drawRoundedRect(QRectF(13.5, 9, 5, 17), 1.5, 1.5)
    p.drawRoundedRect(QRectF(21, 6, 5, 20), 1.5, 1.5)

    p.end()
    return QIcon(pix)


def get_pin_icon(pinned: bool = False, size: int = 32) -> QIcon:
    """Draw a pushpin icon."""
    pix, p = _create_canvas(size)
    color = "#38bdf8" if pinned else "#94a3b8"
    c = QColor(color)
    p.setPen(QPen(c, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QBrush(c) if pinned else Qt.BrushStyle.NoBrush)

    # Pin head
    p.drawLine(11, 7, 21, 7)
    # Pin body
    path = QPainterPath()
    path.moveTo(13, 7)
    path.lineTo(13, 15)
    path.lineTo(9, 18)
    path.lineTo(23, 18)
    path.lineTo(19, 15)
    path.lineTo(19, 7)
    path.closeSubpath()
    p.drawPath(path)
    # Pin needle
    p.drawLine(16, 18, 16, 26)

    p.end()
    return QIcon(pix)


def get_fullscreen_icon(color: str = "#e0e0e0", size: int = 32) -> QIcon:
    """Draw 4-corner expand brackets icon."""
    pix, p = _create_canvas(size)
    c = QColor(color)
    p.setPen(QPen(c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    d = 6
    w = 7
    # Top-left
    p.drawLine(d, d + w, d, d)
    p.drawLine(d, d, d + w, d)
    # Top-right
    p.drawLine(size - d - w, d, size - d, d)
    p.drawLine(size - d, d, size - d, d + w)
    # Bottom-left
    p.drawLine(d, size - d - w, d, size - d)
    p.drawLine(d, size - d, d + w, size - d)
    # Bottom-right
    p.drawLine(size - d - w, size - d, size - d, size - d)
    p.drawLine(size - d, size - d - w, size - d, size - d)

    p.end()
    return QIcon(pix)


def get_volume_icon(muted: bool = False, size: int = 32) -> QIcon:
    """Draw a speaker icon with sound waves (or slash if muted)."""
    pix, p = _create_canvas(size)
    color = "#f87171" if muted else "#94a3b8"
    c = QColor(color)
    p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QBrush(c))

    # Speaker horn
    horn = QPainterPath()
    horn.moveTo(7, 12)
    horn.lineTo(11, 12)
    horn.lineTo(17, 7)
    horn.lineTo(17, 25)
    horn.lineTo(11, 20)
    horn.lineTo(7, 20)
    horn.closeSubpath()
    p.drawPath(horn)

    p.setBrush(Qt.BrushStyle.NoBrush)
    if muted:
        # Cross slash
        p.setPen(QPen(QColor("#e94560"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(20, 11, 26, 21)
        p.drawLine(26, 11, 20, 21)
    else:
        # Sound waves
        p.drawArc(QRectF(15, 10, 8, 12), -60 * 16, 120 * 16)
        p.drawArc(QRectF(18, 7, 10, 18), -60 * 16, 120 * 16)

    p.end()
    return QIcon(pix)


def get_camera_icon(color: str = "#e0e0e0", size: int = 32) -> QIcon:
    """Draw a screenshot camera icon."""
    pix, p = _create_canvas(size)
    c = QColor(color)
    p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    # Body
    path = QPainterPath()
    path.moveTo(6, 12)
    path.lineTo(11, 12)
    path.lineTo(13, 9)
    path.lineTo(19, 9)
    path.lineTo(21, 12)
    path.lineTo(26, 12)
    path.lineTo(26, 24)
    path.lineTo(6, 24)
    path.closeSubpath()
    p.drawPath(path)

    # Lens
    p.drawEllipse(QRectF(12, 13.5, 8, 8))

    p.end()
    return QIcon(pix)


def get_record_icon(recording: bool = False, size: int = 32) -> QIcon:
    """Draw a record circle icon."""
    pix, p = _create_canvas(size)
    color = "#e94560" if recording else "#ffffff"
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))

    if recording:
        # Square stop icon
        p.drawRoundedRect(QRectF(9, 9, 14, 14), 2, 2)
    else:
        # Circle record icon
        p.drawEllipse(QRectF(8, 8, 16, 16))

    p.end()
    return QIcon(pix)
