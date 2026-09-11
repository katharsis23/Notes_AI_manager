"""Tests for :mod:`config.config`."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from pydantic import ValidationError


@pytest.fixture
def config_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    (Re)import :mod:`config.config` with the config file redirected to a
    temporary directory so that a developer's real ``~/.config`` never leaks
    into the test run.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    import config.config as cfg

    importlib.reload(cfg)
    yield cfg

    # Reload again so later imports see the real module state.
    importlib.reload(cfg)


def test_config_dir_is_under_home(config_module) -> None:
    assert config_module.CONFIG_DIR == Path.home() / ".config" / "obsidian-ai-note"


def test_defaults_when_no_file(config_module) -> None:
    settings = config_module.Config()
    assert settings.notes.model_name == "qwen2.5:14b"
    assert settings.notes.auto_git is True
    assert settings.whisper.model_size == "turbo"
    assert settings.dev_tools.enable_logging is False


def test_env_override(config_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBS_NOTE_NOTES__MODEL_NAME", "custom-model")
    settings = config_module.Config()
    assert settings.notes.model_name == "custom-model"


def test_env_nested_override(config_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBS_NOTE_WHISPER__DEVICE", "cpu")
    settings = config_module.Config()
    assert settings.whisper.device == "cpu"


def test_invalid_whisper_device_rejected(config_module) -> None:
    with pytest.raises(ValidationError):
        config_module.WhisperSettings(device="gpu")  # type: ignore[arg-type]


def test_extra_keys_are_ignored(config_module) -> None:
    settings = config_module.NotesSettings(unknown_key="value")  # type: ignore[call-arg]
    assert not hasattr(settings, "unknown_key")


def test_notes_vault_path_is_path(config_module) -> None:
    settings = config_module.NotesSettings()
    assert isinstance(settings.note_vault, Path)
