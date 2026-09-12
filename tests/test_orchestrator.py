"""Tests for :class:`ai.orchestator.Orchestrator`.

Everything is mocked: no Ollama, no real audio, no Whisper, no vault on disk.
We only verify *orchestration* behaviour:

* dispatch by strategy kind;
* correct workers are required / used per strategy;
* whisper-note threads the transcript into the note pipeline;
* dev-tools flags (benchmark / logging / ai_judge) are applied dynamically;
* a disabled tool costs nothing (workers are called exactly once).
"""

from __future__ import annotations

import pytest

from ai.orchestator import Orchestrator
from models.orchestrator import (
    NoteStrategy,
    StrategyKind,
    WhisperNoteStrategy,
    WhisperStrategy,
)


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------


class StubDevTools:
    """Structural stand-in for ``config.dev_tools`` (see DevToolsLike)."""

    def __init__(
        self,
        benchmark: bool = False,
        logging: bool = False,
        judge: bool = False,
    ):
        self.enable_time_benchmark = benchmark
        self.enable_logging = logging
        self.enable_ai_judge = judge


class FakeNotes:
    """Records calls; returns a stable-ish dict like generate_and_save."""

    def __init__(self, result: str = "note-path.md"):
        self.calls: list[str] = []
        self._result = result

    async def generate_and_save(self, raw_text: str):
        self.calls.append(raw_text)
        return self._result


class FakeWhisper:
    """Returns a transcript-like object; records the path it was given."""

    class _Transcript:
        def __init__(self, text: str):
            self.text = text

    def __init__(self, text: str = "hello transcript"):
        self.calls: list[str] = []
        self._text = text

    async def transcribe(self, audio_path: str):
        self.calls.append(audio_path)
        return FakeWhisper._Transcript(self._text)


class ExplodingNotes:
    async def generate_and_save(self, raw_text: str):
        raise AssertionError("note pipeline should NOT be called for this strategy")


class ExplodingWhisper:
    async def transcribe(self, audio_path: str):
        raise AssertionError("whisper should NOT be called for this strategy")


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------


async def test_note_strategy_uses_note_pipeline() -> None:
    notes = FakeNotes()
    orch = Orchestrator(
        NoteStrategy(prompt="async io"),
        StubDevTools(),
        notes=notes,
        whisper=ExplodingWhisper(),  # must not be used
    )
    result = await orch.run()

    assert result == "note-path.md"
    assert notes.calls == ["async io"]


async def test_whisper_strategy_uses_whisper_only() -> None:
    whisper = FakeWhisper("transcribed text")
    orch = Orchestrator(
        WhisperStrategy(audio_path="a.mp3"),
        StubDevTools(),
        notes=ExplodingNotes(),  # must not be used
        whisper=whisper,
    )
    result = await orch.run()

    assert result.text == "transcribed text"
    assert whisper.calls == ["a.mp3"]


async def test_whisper_note_threads_transcript_into_pipeline() -> None:
    notes = FakeNotes()
    whisper = FakeWhisper("the transcript")
    orch = Orchestrator(
        WhisperNoteStrategy(audio_path="a.mp3"),
        StubDevTools(),
        notes=notes,
        whisper=whisper,
    )
    await orch.run()

    assert whisper.calls == ["a.mp3"]
    assert notes.calls == ["the transcript"]


async def test_whisper_note_uses_explicit_prompt_when_given() -> None:
    notes = FakeNotes()
    orch = Orchestrator(
        WhisperNoteStrategy(audio_path="a.mp3", prompt="focus on indexing"),
        StubDevTools(),
        notes=notes,
        whisper=FakeWhisper("raw transcript"),
    )
    await orch.run()

    # Explicit prompt overrides the transcript as the note source.
    assert notes.calls == ["focus on indexing"]


async def test_dispatch_table_covers_all_kinds() -> None:
    orch = Orchestrator(NoteStrategy(prompt="x"), StubDevTools())
    assert set(orch._dispatch.keys()) == set(StrategyKind)


# ----------------------------------------------------------------------
# Missing-worker guards
# ----------------------------------------------------------------------


async def test_note_strategy_without_pipeline_raises() -> None:
    orch = Orchestrator(NoteStrategy(prompt="x"), StubDevTools(), notes=None)
    with pytest.raises(RuntimeError, match="NotePipeline"):
        await orch.run()


async def test_whisper_strategy_without_client_raises() -> None:
    orch = Orchestrator(WhisperStrategy(audio_path="a.mp3"), StubDevTools())
    with pytest.raises(RuntimeError, match="WhisperClient"):
        await orch.run()


async def test_whisper_note_without_whisper_raises() -> None:
    orch = Orchestrator(
        WhisperNoteStrategy(audio_path="a.mp3"),
        StubDevTools(),
        notes=FakeNotes(),
    )
    with pytest.raises(RuntimeError, match="WhisperClient"):
        await orch.run()


# ----------------------------------------------------------------------
# Dev tools
# ----------------------------------------------------------------------


async def test_ai_judge_without_client_raises() -> None:
    orch = Orchestrator(
        NoteStrategy(prompt="x"),
        StubDevTools(judge=True),
        notes=FakeNotes(),
        ollama_client=None,
    )
    with pytest.raises(RuntimeError, match="ollama_client"):
        await orch.run()


async def test_all_dev_tools_disabled_still_returns_result() -> None:
    notes = FakeNotes("ok")
    orch = Orchestrator(
        NoteStrategy(prompt="x"),
        StubDevTools(benchmark=False, logging=False, judge=False),
        notes=notes,
    )
    assert await orch.run() == "ok"
    assert notes.calls == ["x"]


async def test_logging_and_benchmark_enabled_do_not_change_result() -> None:
    notes = FakeNotes("ok")
    orch = Orchestrator(
        NoteStrategy(prompt="x"),
        StubDevTools(benchmark=True, logging=True),
        notes=notes,
    )
    assert await orch.run() == "ok"
    assert notes.calls == ["x"]  # called exactly once despite wrapping


async def test_ai_judge_enabled_invokes_judge_client() -> None:
    """With the judge on, the injected client must be queried after the run."""
    from .conftest import FakeLLMClient

    judge_client = FakeLLMClient(
        responses=[
            '{"valid": true, "score": 9.5, "issues": [], "recommendation": "ok"}'
        ]
    )
    notes = FakeNotes("ok")
    orch = Orchestrator(
        NoteStrategy(prompt="x"),
        StubDevTools(judge=True),
        notes=notes,
        ollama_client=judge_client,
    )
    assert await orch.run() == "ok"
    assert notes.calls == ["x"]
    # The judge ran exactly once through the injected client.
    assert len(judge_client.calls) == 1


async def test_dev_tools_are_not_applied_when_disabled() -> None:
    """Sanity: a plain run without dev tools calls the worker exactly once."""

    class CountingNotes:
        def __init__(self):
            self.count = 0

        async def generate_and_save(self, raw_text: str):
            self.count += 1
            return "done"

    notes = CountingNotes()
    orch = Orchestrator(NoteStrategy(prompt="x"), StubDevTools(), notes=notes)
    await orch.run()
    assert notes.count == 1


# ----------------------------------------------------------------------
# Strategy models
# ----------------------------------------------------------------------


def test_strategy_kinds_are_set_correctly() -> None:
    assert NoteStrategy(prompt="x").kind == StrategyKind.NOTE
    assert WhisperStrategy(audio_path="a").kind == StrategyKind.WHISPER
    assert WhisperNoteStrategy(audio_path="a").kind == StrategyKind.WHISPER_NOTE
