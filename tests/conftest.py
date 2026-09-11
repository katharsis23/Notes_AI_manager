"""
Shared pytest fixtures.

The goal of this module is to keep tests *deterministic*:

- no real network calls (Ollama is always mocked);
- no real ``~/.config`` access (config is redirected to a tmp dir);
- no reliance on wall-clock time or filesystem ordering where avoidable.

Anything that is inherently nondeterministic and cannot be removed is marked
with the ``flaky`` marker and retried by pytest-rerunfailures (see
``pyproject.toml``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project root importable regardless of where pytest is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.note_models import (  # noqa: E402
    DiagramPlan,
    NotePlan,
    NoteSection,
    VaultContext,
    VaultNote,
)


@pytest.fixture
def note_section() -> NoteSection:
    return NoteSection(
        title="Core mechanism",
        purpose="Explain how the mechanism works",
        elements=["definition", "example"],
    )


@pytest.fixture
def note_plan(note_section: NoteSection) -> NotePlan:
    return NotePlan(
        title="Test Note",
        type="concept",
        folder="Concepts",
        tags=["python", "testing"],
        backlinks=["ExistingNote"],
        outline=[note_section],
        diagram=DiagramPlan(needed=False),
    )


@pytest.fixture
def vault_context() -> VaultContext:
    return VaultContext(
        notes=[
            VaultNote(
                name="ExistingNote",
                path="Concepts/ExistingNote.md",
                tags=["python"],
                type="concept",
            ),
            VaultNote(
                name="OtherNote",
                path="Tech/OtherNote.md",
                tags=["networking"],
                type="reference",
            ),
        ],
        tags=["python", "networking"],
    )


class FakeLLMClient:
    """
    Deterministic stand-in for :class:`ai.notes.llm.OllamaClient`.

    The real client performs HTTP requests. Tests must never do that, so every
    component that accepts a "llama_client" gets this instead.
    """

    def __init__(self, response: str = "", responses: list[str] | None = None):
        self._responses = list(responses) if responses else []
        self._default = response
        self.calls: list[dict] = []

    async def query(
        self,
        prompt: str,
        is_json: bool = True,
        temperature: float = 0.3,
    ) -> str:
        self.calls.append(
            {"prompt": prompt, "is_json": is_json, "temperature": temperature}
        )
        if self._responses:
            return self._responses.pop(0)
        return self._default


class ErrorLLMClient(FakeLLMClient):
    """LLM client that always raises, used to test error handling."""

    async def query(self, *args, **kwargs) -> str:  # type: ignore[override]
        raise RuntimeError("boom")


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def error_llm() -> ErrorLLMClient:
    return ErrorLLMClient()


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Create a small Markdown vault on disk and return its path."""
    (tmp_path / "Concepts").mkdir()
    (tmp_path / "Concepts" / "ExistingNote.md").write_text(
        "---\ntype: concept\ntags:\n  - python\n---\n\n"
        "# Existing Note\n\nLinks to [[OtherNote]]. #asyncio\n",
        encoding="utf-8",
    )
    (tmp_path / "Tech").mkdir()
    (tmp_path / "Tech" / "OtherNote.md").write_text(
        "---\ntype: reference\n---\n\n# Other Note\n\nContent here.\n",
        encoding="utf-8",
    )
    return tmp_path
