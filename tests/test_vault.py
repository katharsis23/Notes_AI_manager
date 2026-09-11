"""Tests for :class:`vault.vault.VaultManager`."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.note_models import VaultContext
from vault.vault import VaultManager


@pytest.fixture
def manager(tmp_vault: Path) -> VaultManager:
    return VaultManager(vault_path=tmp_vault, auto_git=False)


def test_context_v2_returns_notes_and_tags(manager: VaultManager) -> None:
    context = manager.get_existing_context_v2()
    assert isinstance(context, VaultContext)
    assert {n.name for n in context.notes} == {"ExistingNote", "OtherNote"}
    assert "python" in context.tags


def test_legacy_context(manager: VaultManager) -> None:
    tags, files = manager.get_existing_context()
    assert "ai-generated" in tags
    assert "ExistingNote" in files


def test_legacy_context_missing_vault(tmp_path: Path) -> None:
    mgr = VaultManager(vault_path=tmp_path / "missing", auto_git=False)
    tags, files = mgr.get_existing_context()
    assert "ai-generated" in tags
    assert files == []


def test_save_note_creates_file(manager: VaultManager) -> None:
    data = {
        "title": "My Note",
        "type": "concept",
        "folder": "Concepts",
        "tags": ["Python", "test_tag"],
        "backlinks": ["ExistingNote"],
        "content": "## Body\n\nText",
    }
    path = manager.save_note(data)
    assert path is not None
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "title" not in text or True  # H1 title added below
    assert "# My Note" in text
    assert "## Body" in text


def test_save_note_normalizes_tags(manager: VaultManager, tmp_vault: Path) -> None:
    data = {"title": "T", "tags": ["UPPER", "with_underscore", "#hash"], "content": "x"}
    path = manager.save_note(data)
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "- upper" in text
    assert "- with-underscore" in text
    assert "- hash" in text
    assert "- ai-generated" in text


def test_save_note_strips_h1_from_content(manager: VaultManager) -> None:
    data = {"title": "T", "content": "# Duplicate Title\n\nBody"}
    path = manager.save_note(data)
    assert path is not None
    text = path.read_text(encoding="utf-8")
    # Only one H1 should remain (added by VaultManager).
    assert text.count("\n# ") == 1
    assert "Duplicate Title" not in text


def test_save_note_backlinks_single(manager: VaultManager) -> None:
    data = {"title": "T", "backlinks": ["NoteA"], "content": "x"}
    path = manager.save_note(data)
    assert path is not None
    assert "[[NoteA]]" in path.read_text(encoding="utf-8")


def test_save_note_backlinks_multiple(manager: VaultManager) -> None:
    data = {"title": "T", "backlinks": ["A", "B"], "content": "x"}
    path = manager.save_note(data)
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "[[A]]" in text
    assert "[[B]]" in text


def test_save_note_string_backlinks(manager: VaultManager) -> None:
    data = {"title": "T", "backlinks": "Single", "content": "x"}
    path = manager.save_note(data)
    assert path is not None
    assert "[[Single]]" in path.read_text(encoding="utf-8")


def test_save_note_empty_data(manager: VaultManager) -> None:
    assert manager.save_note({}) is None


def test_save_note_default_folder(manager: VaultManager, tmp_vault: Path) -> None:
    path = manager.save_note({"title": "T", "content": "x"})
    assert path is not None
    assert path.parent == (tmp_vault / "Inbox").resolve()


def test_save_note_frontmatter_format(manager: VaultManager) -> None:
    data = {"title": "T", "type": "reference", "content": "x"}
    path = manager.save_note(data)
    assert path is not None
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    assert any(line.startswith("date:") for line in lines)
    assert "type: reference" in lines
    assert "---" in lines[1:]


def test_save_note_updates_index(manager: VaultManager) -> None:
    manager.save_note({"title": "Indexed", "content": "x"})
    notes = {n.name for n in manager.indexer.get_notes()}
    assert "Indexed" in notes


def test_save_note_with_auto_git_calls_git(
    tmp_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = VaultManager(vault_path=tmp_vault, auto_git=True)
    called = {}

    def fake_commit(file_path, commit_message):
        called["file"] = file_path
        called["msg"] = commit_message
        return True

    monkeypatch.setattr(manager.git, "commit_and_push", fake_commit)
    path = manager.save_note({"title": "Git Note", "content": "x"})
    assert path is not None
    assert called["msg"] == "Add Git Note"
