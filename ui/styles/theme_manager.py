"""
G-Mirror Theme Manager.
Applies Dark / Light / System theme based on settings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

_STYLES_DIR = Path(__file__).parent

THEMES = {
    "Dark": _STYLES_DIR / "dark.qss",
    "Light": _STYLES_DIR / "light.qss",
}


def apply_theme(app: "QApplication", theme: str) -> None:
    """
    Apply the specified theme ("Dark", "Light", "System") to the QApplication.
    """
    if theme == "System":
        # Detect Windows dark mode via registry
        theme = _detect_system_theme()

    qss_path = THEMES.get(theme, THEMES["Dark"])
    try:
        stylesheet = qss_path.read_text(encoding="utf-8")
        app.setStyleSheet(stylesheet)
        log.info("Applied theme: %s", theme)
    except Exception as e:
        log.warning("Could not apply theme '%s': %s", theme, e)


def _detect_system_theme() -> str:
    """Returns 'Dark' or 'Light' based on Windows AppsUseLightTheme registry value."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "Light" if value == 1 else "Dark"
    except Exception:
        return "Dark"
