"""
G-Mirror Application Bootstrap.

Sets up QApplication, applies theme, runs first-run wizard if needed,
and launches the main window.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gmirror.logging_setup import setup_logging
from gmirror.settings.config import get_config
from ui.styles.theme_manager import apply_theme

log = logging.getLogger(__name__)


def create_app() -> QApplication:
    """Create and configure the QApplication."""
    # Required for high-DPI on Windows
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("G-Mirror")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("GMirror")
    app.setQuitOnLastWindowClosed(False)   # Stay alive in tray
    return app


def run() -> int:
    """Main entry point. Returns process exit code."""
    import io
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

    setup_logging()
    log.info("G-Mirror starting…")

    app = create_app()

    cfg = get_config()
    apply_theme(app, cfg.general.theme)

    # First-run wizard
    if not cfg.general.first_run_complete:
        from ui.first_run_wizard import FirstRunWizard
        wizard = FirstRunWizard(None)
        wizard.exec()

    from ui.main_window import MainWindow
    window = MainWindow()

    # Show window (unless start minimized)
    if not cfg.general.start_minimized:
        window.show()

    # Optional update check
    if cfg.general.check_for_updates:
        from gmirror.updater import check_for_update
        def _on_update(version: Optional[str], url: Optional[str]) -> None:
            if version and url:
                from PySide6.QtWidgets import QMessageBox
                from PySide6.QtCore import QTimer
                def _show():
                    mb = QMessageBox(window)
                    mb.setWindowTitle("G-Mirror Update Available")
                    mb.setText(
                        f"G-Mirror {version} is available.\n\n"
                        f"Visit {url} to download."
                    )
                    mb.setIcon(QMessageBox.Icon.Information)
                    mb.exec()
                QTimer.singleShot(3000, _show)  # Show after window is fully visible
        check_for_update(_on_update)

    log.info("G-Mirror ready.")
    return app.exec()
