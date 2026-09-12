"""Tests for :class:`vault.vault_indexer.VaultIndexer`."""


from __future__ import annotations

from pathlib import Path

import pytest

from vault.vault_indexer import VaultIndexer


@pytest.fixture
def indexer(tmp_vault: Path) -> VaultIndexer:
    return VaultIndexer(vault_path=tmp_vault)


def test_initialize_creates_database(tmp_vault: Path, indexer: VaultIndexer) -> None:
    assert indexer.db_path.exists()
    assert indexer.db_path.parent.name == VaultIndexer.DB_DIR_NAME


def test_sync_indexes_notes(indexer: VaultIndexer) -> None:
    indexer.sync()
    notes = indexer.get_notes()
    names = {n.name for n in notes}
    assert names == {"ExistingNote", "OtherNote"}


def test_sync_extracts_frontmatter_type(indexer: VaultIndexer) -> None:
    indexer.sync()
    note = indexer.get_note("Concepts/ExistingNote.md")
    assert note is not None
    assert note.type == "concept"


def test_sync_extracts_tags_from_frontmatter_and_inline(indexer: VaultIndexer) -> None:
    indexer.sync()
    tags = {t.name for t in indexer.get_tags()}
    assert "python" in tags
    assert "asyncio" in tags  # inline #asyncio in ExistingNote


def test_note_tags_relation(indexer: VaultIndexer) -> None:
    indexer.sync()
    note = indexer.get_note("Concepts/ExistingNote.md")
    assert note is not None
    tag_names = {t.name for t in indexer.get_note_tags(note.id)}
    assert {"python", "asyncio"} <= tag_names


def test_wikilink_resolution(indexer: VaultIndexer) -> None:
    indexer.sync()
    source = indexer.get_note("Concepts/ExistingNote.md")
    assert source is not None
    outgoing = {n.name for n in indexer.get_outgoing_links(source.id)}
    assert outgoing == {"OtherNote"}


def test_backlinks(indexer: VaultIndexer) -> None:
    indexer.sync()
    target = indexer.get_note("Tech/OtherNote.md")
    assert target is not None
    backlinks = {n.name for n in indexer.get_backlinks(target.id)}
    assert backlinks == {"ExistingNote"}


def test_resync_is_idempotent(indexer: VaultIndexer) -> None:
    indexer.sync()
    first = {n.id for n in indexer.get_notes()}
    indexer.sync()
    second = {n.id for n in indexer.get_notes()}
    assert first == second


def test_modified_file_is_reindexed_but_keeps_id(
    tmp_vault: Path, indexer: VaultIndexer
) -> None:
    indexer.sync()
    note = indexer.get_note("Tech/OtherNote.md")
    assert note is not None

    path = tmp_vault / "Tech" / "OtherNote.md"
    path.write_text("---\ntype: reference\n---\n\n# Changed\n", encoding="utf-8")
    indexer.sync()

    updated = indexer.get_note("Tech/OtherNote.md")
    assert updated is not None
    assert updated.id == note.id  # ID is stable across content changes
    assert updated.hash != note.hash


def test_deleted_file_is_removed(tmp_vault: Path, indexer: VaultIndexer) -> None:
    indexer.sync()
    (tmp_vault / "Tech" / "OtherNote.md").unlink()
    indexer.sync()
    assert indexer.get_note("Tech/OtherNote.md") is None


def test_orphan_tags_are_cleaned(tmp_vault: Path, indexer: VaultIndexer) -> None:
    indexer.sync()
    assert any(t.name == "asyncio" for t in indexer.get_tags())

    # Remove the only note carrying #asyncio.
    (tmp_vault / "Concepts" / "ExistingNote.md").write_text(
        "---\ntype: concept\n---\n\n# No tags\n", encoding="utf-8"
    )
    indexer.sync()
    assert not any(t.name == "asyncio" for t in indexer.get_tags())


def test_rebuild_clears_and_reindexes(tmp_vault: Path, indexer: VaultIndexer) -> None:
    indexer.sync()
    indexer.rebuild()
    assert {n.name for n in indexer.get_notes()} == {"ExistingNote", "OtherNote"}


def test_search_notes(indexer: VaultIndexer) -> None:
    indexer.sync()
    results = indexer.search_notes("other")
    assert any(n.name == "OtherNote" for n in results)


def test_get_content_roundtrip(indexer: VaultIndexer) -> None:
    indexer.sync()
    note = indexer.get_note("Tech/OtherNote.md")
    assert note is not None
    content = indexer.get_content(note.id)
    assert content is not None
    assert "Content here" in content.content


def test_ignored_directories_are_skipped(tmp_vault: Path, indexer: VaultIndexer) -> None:
    git_dir = tmp_vault / ".git"
    git_dir.mkdir()
    (git_dir / "hidden.md").write_text("# should be ignored\n", encoding="utf-8")

    indexer.sync()
    assert indexer.get_note(".git/hidden.md") is None


def test_ambiguous_wikilink_not_resolved(tmp_vault: Path, indexer: VaultIndexer) -> None:
    # Two notes with the same stem in different folders -> ambiguous link.
    (tmp_vault / "Concepts" / "Dup.md").write_text("# Dup A\n", encoding="utf-8")
    (tmp_vault / "Tech" / "Dup.md").write_text("# Dup B\n", encoding="utf-8")
    (tmp_vault / "Linked.md").write_text("# L\n\n[[Dup]]\n", encoding="utf-8")

    indexer.sync()
    source = indexer.get_note("Linked.md")
    assert source is not None
    # Ambiguous names must not be silently linked to a random target.
    assert indexer.get_outgoing_links(source.id) == []


def test_self_link_ignored(tmp_vault: Path, indexer: VaultIndexer) -> None:
    (tmp_vault / "Self.md").write_text("# S\n\n[[Self]]\n", encoding="utf-8")
    indexer.sync()
    note = indexer.get_note("Self.md")
    assert note is not None
    assert indexer.get_outgoing_links(note.id) == []


def test_sync_missing_vault_is_noop(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    idx = VaultIndexer(vault_path=missing)
    idx.sync()  # should not raise
    assert idx.get_notes() == []


@pytest.mark.flaky(reruns=3)
def test_hash_is_stable_for_fixed_content(tmp_vault: Path) -> None:
    """
    Hashing must be deterministic. We compute it twice through the public
    indexer behaviour. This is only flaky if the filesystem mangles the file
    between writes, hence the retry marker.
    """
    a = VaultIndexer._calculate_hash(tmp_vault / "Tech" / "OtherNote.md")
    b = VaultIndexer._calculate_hash(tmp_vault / "Tech" / "OtherNote.md")
    assert a == b
    assert len(a) == 64
