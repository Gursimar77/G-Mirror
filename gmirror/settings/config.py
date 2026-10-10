"""
G-Mirror Settings — persistent configuration model.
All settings are stored locally using QSettings (INI format on Windows).
No data is ever sent to remote servers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from PySide6.QtCore import QSettings
except ImportError:
    QSettings = None  # type: ignore

log = logging.getLogger(__name__)

SETTINGS_ORG = "GMirror"
SETTINGS_APP = "GMirror"


@dataclass
class VideoSettings:
    resolution: str = "Auto"          # "Auto", "1080p", "720p", "540p"
    fps: str = "Auto"                  # "Auto", "60", "30"
    quality: str = "Balanced"          # "Low Latency", "Balanced", "Quality", "Maximum"
    bitrate_mbps: float = 0.0          # 0 = auto
    hw_accel: bool = True
    low_latency: bool = True


@dataclass
class AudioSettings:
    enabled: bool = True
    output_device: str = "Default"
    volume: float = 1.0                # 0.0–1.0
    muted: bool = False


@dataclass
class RecordingSettings:
    folder: str = str(Path.home() / "Videos" / "GMirror")
    format: str = "mp4"
    fps: int = 30
    bitrate_kbps: int = 8000
    include_audio: bool = True


@dataclass
class NetworkSettings:
    adapter: str = "Auto"
    port: int = 7000
    discovery_enabled: bool = True
    receiver_name: str = "G-Mirror"


@dataclass
class GeneralSettings:
    theme: str = "System"              # "System", "Dark", "Light"
    start_with_windows: bool = False
    start_minimized: bool = False
    minimize_to_tray: bool = True
    always_on_top: bool = False
    keep_screen_awake: bool = True
    show_performance_overlay: bool = False
    check_for_updates: bool = True
    screenshot_folder: str = str(Path.home() / "Pictures" / "GMirror")
    first_run_complete: bool = False


@dataclass
class AppConfig:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    recording: RecordingSettings = field(default_factory=RecordingSettings)
    network: NetworkSettings = field(default_factory=NetworkSettings)


# Singleton
_config: Optional[AppConfig] = None
_settings_path = Path.home() / "AppData" / "Local" / "GMirror" / "settings.json"


def _load_json() -> dict:
    try:
        if _settings_path.exists():
            return json.loads(_settings_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to read settings file: %s", e)
    return {}


def _save_json(data: dict) -> None:
    try:
        _settings_path.parent.mkdir(parents=True, exist_ok=True)
        _settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log.error("Failed to save settings: %s", e)


def _apply_dict(obj: Any, data: dict) -> None:
    """Recursively apply a dict onto a dataclass instance."""
    for key, value in data.items():
        if hasattr(obj, key):
            attr = getattr(obj, key)
            if hasattr(attr, "__dataclass_fields__") and isinstance(value, dict):
                _apply_dict(attr, value)
            else:
                try:
                    setattr(obj, key, type(attr)(value))
                except Exception:
                    setattr(obj, key, value)


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
        data = _load_json()
        if data:
            _apply_dict(_config, data)
    return _config


def save_config() -> None:
    if _config is not None:
        _save_json(asdict(_config))


def reset_config() -> None:
    global _config
    _config = AppConfig()
    save_config()
    log.info("Settings reset to defaults.")
