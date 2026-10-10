"""
G-Mirror Update Checker.
Checks GitHub releases for new versions. Fully optional and user-controlled.
No telemetry. No forced updates.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request
from typing import Callable, Optional

from gmirror import __version__

log = logging.getLogger(__name__)

GITHUB_RELEASES_API = "https://api.github.com/repos/gmirror-app/gmirror/releases/latest"
CHECK_TIMEOUT = 10  # seconds


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip("v").split(".")[:3])
    except Exception:
        return (0, 0, 0)


def check_for_update(callback: Callable[[Optional[str], Optional[str]], None]) -> None:
    """
    Asynchronously check GitHub for a newer release.

    callback(new_version, release_url) is called with:
      - (None, None) if already up to date or check failed
      - ("1.2.0", "https://...") if a newer release exists
    """

    def _worker() -> None:
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": f"GMirror/{__version__}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            latest_tag = data.get("tag_name", "")
            release_url = data.get("html_url", "")

            if not latest_tag:
                callback(None, None)
                return

            current = _parse_version(__version__)
            latest = _parse_version(latest_tag)

            if latest > current:
                log.info("Update available: %s → %s", __version__, latest_tag)
                callback(latest_tag.lstrip("v"), release_url)
            else:
                callback(None, None)

        except Exception as e:
            log.debug("Update check failed: %s", e)
            callback(None, None)

    t = threading.Thread(target=_worker, daemon=True, name="UpdateChecker")
    t.start()
