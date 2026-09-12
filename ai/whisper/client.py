import asyncio
from typing import Any

from config.config import config
from models.whisper_models import WhisperRawResponse


class WhisperClient:
    """A low level abstraction around Faster-Whisper.

    The heavy ``WhisperModel`` (and the ``faster_whisper`` import itself) is
    created lazily on first use, so importing this module never requires the
    native audio stack (ffmpeg/av/zlib) to be present.
    """

    def __init__(self, **kwargs: Any):
        # Kwargs can override settings (device, compute_type, language, ...).
        self.model_size = config.whisper.model_size
        self.device = config.whisper.device
        self.compute_type = config.whisper.compute_type
        self.language = config.whisper.language
        self.vad_filter = config.whisper.vad_filter
        self.condition_on_previous_text = config.whisper.condition_on_previous_text
        self.no_speech_threshold = config.whisper.no_speech_threshold

        for key, value in kwargs.items():
            setattr(self, key, value)

        self._model = None

    def _get_model(self):
        """Lazily construct and cache the underlying WhisperModel."""
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    async def transcribe(
        self,
        audio_file_path: str,
        language: str | None = None,
        **kwargs: Any,
    ) -> WhisperRawResponse:
        """Transcribe an audio file to text (runs the blocking model in a thread).

        ``language`` overrides the configured language for this call. Pass an
        empty string "" to force auto-detection.
        """
        model = self._get_model()

        # Per-call language wins; otherwise fall back to the configured one.
        lang = language if language is not None else self.language
        if lang == "":
            lang = None

        transcribe_kwargs: dict[str, Any] = {
            "language": lang,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
            "no_speech_threshold": self.no_speech_threshold,
        }
        # Allow callers to override any transcribe option.
        transcribe_kwargs.update(kwargs)
        # If the caller forced language=None via kwargs, keep it as auto-detect.
        if "language" in kwargs and kwargs["language"] == "":
            transcribe_kwargs["language"] = None

        loop = asyncio.get_event_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: model.transcribe(audio_file_path, **transcribe_kwargs),
        )

        text = "".join(segment.text for segment in segments)

        additional_info = {
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration": getattr(info, "duration", None),
            "requested_language": lang,
        }

        return WhisperRawResponse(text=text.strip(), additional_info=additional_info)

    async def transcribe_stream(self, **kwargs: Any) -> None:
        """Streaming transcription (not implemented yet)."""
        # Maybe we will use it in case we want to stream audio real-time
        raise NotImplementedError("Streaming transcription is not implemented yet.")

