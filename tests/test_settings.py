"""
Tests for G-Mirror settings persistence.
"""

import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import gmirror.settings.config as config_module


def test_default_config():
    cfg = config_module.AppConfig()
    assert cfg.general.theme == "System"
    assert cfg.video.fps == "Auto"
    assert cfg.audio.volume == 1.0
    assert cfg.network.port == 7000


def test_save_and_reload(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_module, "_settings_path", settings_file)
    monkeypatch.setattr(config_module, "_config", None)

    cfg = config_module.get_config()
    cfg.general.theme = "Dark"
    cfg.video.fps = "60"
    cfg.audio.volume = 0.5
    config_module.save_config()

    # Reload
    monkeypatch.setattr(config_module, "_config", None)
    cfg2 = config_module.get_config()
    assert cfg2.general.theme == "Dark"
    assert cfg2.video.fps == "60"
    assert cfg2.audio.volume == 0.5


def test_reset_config(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_module, "_settings_path", settings_file)
    monkeypatch.setattr(config_module, "_config", None)

    cfg = config_module.get_config()
    cfg.general.theme = "Light"
    config_module.save_config()

    config_module.reset_config()
    assert config_module.get_config().general.theme == "System"
