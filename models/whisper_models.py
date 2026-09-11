from pydantic import BaseModel
from typing import Any, Optional, Dict
from pathlib import Path

class WhisperRawResponse(BaseModel):
    text: str
    additional_info: Dict[str, Any]

class WhisperAgentCall(BaseModel):
    # Input data format
    # File: from pre-recorded file
    # Live: Live recording
    file: Optional[str]
    live: bool=False
    # Dev Tools
    streaming: bool = False
    time_benchmark: bool = False
    logging: bool = False
    # Other kwargs
    timeout: int
