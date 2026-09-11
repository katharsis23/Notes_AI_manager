"""Tests for :class:`git_client.GitClient`.

Git subprocess calls are mocked; no real repository is required.
"""

from __future__ import annotations

import pathlib
import subprocess
from unittest.mock import MagicMock

import pytest

from git_client import GitClient


@pytest.fixture
def client(tmp_path: pathlib.Path) -> GitClient:
    return GitClient(vault_path=tmp_path)


def _ok(stdout: str = "") -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.stderr = ""
    return result


def _fail(stderr: str) -> subprocess.CalledProcessError:
    err = subprocess.CalledProcessError(1, ["git"])
    err.stderr = stderr
    return err


def test_run_git_success(client: GitClient, monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _ok("ok"))
    ok, out = client._run_git(["status"])
    assert ok is True
    assert out == "ok"


def test_run_git_called_process_error(client: GitClient, monkeypatch) -> None:
    def raise_err(*a, **k):
        raise _fail("bad")

    monkeypatch.setattr(subprocess, "run", raise_err)
    ok, err = client._run_git(["status"])
    assert ok is False
    assert err == "bad"


def test_run_git_file_not_found(client: GitClient, monkeypatch) -> None:
    def raise_err(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", raise_err)
    ok, err = client._run_git(["status"])
    assert ok is False
    assert "not installed" in err


def test_is_git_repo_true(client: GitClient, monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _ok("true"))
    assert client.is_git_repo() is True


def test_is_git_repo_false(client: GitClient, monkeypatch) -> None:
    def raise_err(*a, **k):
        raise _fail("not a repo")

    monkeypatch.setattr(subprocess, "run", raise_err)
    assert client.is_git_repo() is False


def test_commit_and_push_not_repo(client: GitClient, monkeypatch) -> None:
    monkeypatch.setattr(client, "is_git_repo", lambda: False)
    assert client.commit_and_push(client.vault_path / "a.md", "msg") is False


def test_commit_and_push_success(client: GitClient, monkeypatch) -> None:
    monkeypatch.setattr(client, "is_git_repo", lambda: True)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _ok("done")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = client.commit_and_push(client.vault_path / "a.md", "msg")
    assert result is True
    assert ["git", "add", "a.md"] in calls
    assert any("commit" in c for c in calls)
    assert ["git", "push"] in calls


def test_commit_and_push_add_fails(client: GitClient, monkeypatch) -> None:
    monkeypatch.setattr(client, "is_git_repo", lambda: True)

    def fake_run(args, **kwargs):
        if "add" in args:
            raise _fail("add failed")
        return _ok()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert client.commit_and_push(client.vault_path / "a.md", "msg") is False


def test_commit_and_push_push_fails(client: GitClient, monkeypatch) -> None:
    monkeypatch.setattr(client, "is_git_repo", lambda: True)

    def fake_run(args, **kwargs):
        if "push" in args:
            raise _fail("no remote")
        return _ok()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert client.commit_and_push(client.vault_path / "a.md", "msg") is False
