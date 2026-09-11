import faster_whisper
from config.config import config
import asyncio
from functools import wraps


class WhisperClient:
    def __init__(self, **kwargs):
        # Kwargs can be used to override a timeout, benchmark solution, or other parameters if needed.
        self.model = config.whisper_config.model
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def transcribe(self, audio_file_path: str, **kwargs) -> str:
        """Trascribe audio file to text using the Whisper model from the existing file .mp3"""
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None,
            self.model.transcribe,
            audio_file_path,
            kwargs
        )
        # TODO: Return the text in a pre-declared interface(model)
        return text["text"]

    async def transcribe(self, **kwargs) -> str:
        # Maybe we will use it in case we want to stream audio real-time
        pass

