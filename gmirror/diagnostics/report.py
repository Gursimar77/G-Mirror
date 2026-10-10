"""
G-Mirror Diagnostic Report Generator.
Exports reports to text or clipboard. Never includes passwords or private keys.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from gmirror.diagnostics.network_checker import DiagnosticReport
from gmirror.logging_setup import get_log_dir

log = logging.getLogger(__name__)


def export_report(report: DiagnosticReport, path: Optional[str] = None) -> str:
    """
    Save diagnostic report to file. Returns file path.
    If path is None, saves to log directory with timestamp filename.
    """
    if path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = str(get_log_dir() / f"diagnostic_report_{ts}.txt")
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(report.to_text(), encoding="utf-8")
        log.info("Diagnostic report saved: %s", path)
        return path
    except Exception as e:
        log.error("Failed to export report: %s", e)
        return ""
