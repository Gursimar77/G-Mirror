"""
G-Mirror logging configuration.
Provides rotating file logs and a queue-based handler for UI log display.
No sensitive information is ever written to logs.
"""

import logging
import logging.handlers
import queue
import sys
from pathlib import Path


LOG_DIR = Path.home() / "AppData" / "Local" / "GMirror" / "Logs"
LOG_FILE = LOG_DIR / "gmirror.log"
_ui_log_queue: queue.Queue = queue.Queue(maxsize=2000)


class UIQueueHandler(logging.Handler):
    """Push log records into an in-memory queue for display in the UI."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            _ui_log_queue.put_nowait((record.levelno, msg))
        except Exception:
            pass


def setup_logging(debug: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers filter

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Rotating file handler — max 5 MB × 5 files
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (visible in debug mode / terminal)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # UI queue handler
    ui_h = UIQueueHandler()
    ui_h.setLevel(logging.INFO)
    ui_h.setFormatter(fmt)
    root.addHandler(ui_h)

    logging.getLogger("zeroconf").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_ui_log_queue() -> queue.Queue:
    return _ui_log_queue


def get_log_dir() -> Path:
    return LOG_DIR
