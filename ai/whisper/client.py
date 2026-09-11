import asyncio

from config.config import config
from models.whisper_models import WhisperRawResponse


class WhisperClient:
    """A low level abstract class that calls Whisper"""

    def __init__(self, **kwargs):
        # Kwargs can be used to override a timeout, benchmark solution, or other parameters if needed.
        self.model = config.whisper_config.model
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def transcribe(self, audio_file_path: str, **kwargs) -> str:
        """Trascribe audio file to text using the Whisper model from the existing file .mp3"""
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, self.model.transcribe, audio_file_path, kwargs
        )
        # TODO: Return the text in a pre-declared interface(model)
        return WhisperRawResponse(text=text["text"], additional_info=...)

    async def transcribe_stream(self, **kwargs) -> str:
        """Streaming transcription (not implemented yet)."""
        # Maybe we will use it in case we want to stream audio real-time
        raise NotImplementedError("Streaming transcription is not implemented yet.")
