from typing import Union

from pydantic import BaseModel

# Declaring strategies pattern
MODULE_REGISTRY: dict[str, BaseModel] = {
    "note": ...,
    "whisper": ...,
}


class Note(BaseModel): ...


class Whisper(BaseModel): ...


class WhisperNote(BaseModel): ...


# Pass this to orchestrator as runtime signal
ExecutionStrategy = Union[Note, Whisper, WhisperNote]
