from typing import Any

from pydantic import BaseModel


class WhisperRawResponse(BaseModel):
    text: str
    additional_info: dict[str, Any]


class WhisperAgentCall(BaseModel):
    # Input data format
    # File: from pre-recorded file
    # Live: Live recording
    file: str | None
    live: bool = False
    # Dev Tools
    streaming: bool = False
    time_benchmark: bool = False
    logging: bool = False
    # Other kwargs
    timeout: int
