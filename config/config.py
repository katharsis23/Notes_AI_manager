from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

CONFIG_DIR = Path.home() / ".config" / "obsidian-ai-note"
CONFIG_FILE = CONFIG_DIR / "config.json"


WhisperModelSize = Literal[
    "tiny",
    "base",
    "small",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "turbo",
]

WhisperDevice = Literal["cpu", "cuda"]

WhisperComputeType = Literal[
    "int8_float16",
    "int8_int8",
    "int8",
    "float16",
]


class NotesSettings(BaseModel):
    """Settings related to AI note generation."""

    model_config = ConfigDict(extra="ignore")

    model_name: str = "qwen2.5:14b"
    model_planner: str = "llama3.2:3b"
    model_validator: str = "qwen3:4b"

    ollama_url: str = "http://0.0.0.0:11434/api/generate"

    note_vault: Path = Field(
        default_factory=lambda: Path.home() / "Documents" / "obsidian" / "conspects"
    )

    auto_git: bool = True

    system_prompt: str = """\
You are a JSON ONLY processing model and an expert technical writer.

The user will give you a topic to write a comprehensive, deep, and detailed note about.

Your task:

1. Write a well-structured, in-depth Markdown note
   (at least 3-5 comprehensive sections with subheadings,
   bullet points, explanations, and key takeaways).

2. Extract 3-6 relevant tags related to the core topic.
   Use lowercase and hyphens instead of spaces,
   e.g. "machine-learning".

3. Return your output STRICTLY as a JSON object matching this schema:

{
    "title": "A short, descriptive title for the note",
    "type": "reference",
    "tags": ["topic-tag-1", "topic-tag-2"],
    "content": "Full detailed markdown content starting with headings (###), paragraphs, lists, and examples. Length of the text should be 350 words +"
}

CRITICAL: Return ONLY valid JSON.
No markdown code blocks around JSON.
No explanations.
"""


class WhisperSettings(BaseModel):
    """Settings related to Faster-Whisper."""

    model_config = ConfigDict(extra="ignore")

    model_size: WhisperModelSize = "turbo"
    device: WhisperDevice = "cpu"

    # CPU uses "int8"; GPU/CUDA uses "float16". The default is chosen for CPU.
    compute_type: WhisperComputeType = "int8_float16"

    # ISO-639-1 language code ("uk", "en", ...) or None for auto-detection.
    # Always prefer an explicit language: auto-detect is unreliable, especially
    # on accented or noisy speech. Ukrainian is the common case here.
    language: str | None = "en"

    # Anti-hallucination / robustness flags (all default to the "speech" profile):
    # - vad_filter: drop silent/music/noise regions where Whisper invents text;
    # - condition_on_previous_text: avoid getting "stuck" echoing prior output;
    # - no_speech_threshold: skip segments with low speech probability.
    vad_filter: bool = True
    condition_on_previous_text: bool = False
    no_speech_threshold: float = 0.6


class DevToolsSettings(BaseModel):
    """Development and debugging settings."""

    model_config = ConfigDict(extra="ignore")

    enable_time_benchmark: bool = False
    enable_logging: bool = False
    enable_ai_judge: bool = False


class Config(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        json_file=CONFIG_FILE,
        json_file_encoding="utf-8",
        env_prefix="OBS_NOTE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    notes: NotesSettings = Field(default_factory=NotesSettings)
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    dev_tools: DevToolsSettings = Field(default_factory=DevToolsSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls),
        )


config = Config()

