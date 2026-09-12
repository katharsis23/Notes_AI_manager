from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class StrategyKind(str, Enum):
    """The three runtime tasks the orchestrator can execute."""

    NOTE = "note"
    WHISPER = "whisper"
    WHISPER_NOTE = "whisper_note"


class NoteStrategy(BaseModel):
    """Generate a note from a text prompt."""

    kind: Literal[StrategyKind.NOTE] = StrategyKind.NOTE
    prompt: str


class WhisperStrategy(BaseModel):
    """Transcribe an audio file only."""

    kind: Literal[StrategyKind.WHISPER] = StrategyKind.WHISPER
    audio_path: str
    # ISO-639-1 code ("uk", "en", ...), "" for auto-detect, None -> use config.
    language: str | None = None


class WhisperNoteStrategy(BaseModel):
    """Transcribe audio, then feed the transcript into the note pipeline."""

    kind: Literal[StrategyKind.WHISPER_NOTE] = StrategyKind.WHISPER_NOTE
    audio_path: str
    prompt: str | None = None
    # ISO-639-1 code ("uk", "en", ...), "" for auto-detect, None -> use config.
    language: str | None = None
    # When set, the raw transcript is also saved next to the note.
    save_transcript: bool = False


# Runtime signal passed to the orchestrator + dispatch key.
ExecutionStrategy = NoteStrategy | WhisperStrategy | WhisperNoteStrategy

STRATEGY_REGISTRY: dict[StrategyKind, str] = {
    StrategyKind.NOTE: "run_notes",
    StrategyKind.WHISPER: "run_whisper",
    StrategyKind.WHISPER_NOTE: "run_whisper_and_notes",
}

