import pathlib
import json
import faster_whisper
from typing import Literal

CONFIG_PATH = pathlib.Path.home() / ".config" / "obsidian-ai-note"
CONFIG_FILE = "config.json"

class NotesConfig:
    """
    Class to store all the constants and global vars
    """
    def __init__(
        self,
        model_name: str = "qwen2.5:14b",
        ollama_url: str = "http://localhost:11434/api/generate",
        note_vault: pathlib.Path = pathlib.Path.home() / "Documents" / "obsidian" / "conspects",
        auto_git: bool = True,
        model_planner: str = "llama3.2:3b",
        model_validator: str = "qwen3:4b"
    ):
        self.model_name = model_name
        self.model_planner = model_planner
        self.model_validator = model_validator
        self.ollama_url = ollama_url
        self.note_vault = note_vault
        self.auto_git = auto_git
        self.system_prompt = """
            You are a JSON ONLY processing model and an expert technical writer.
            The user will give you a topic to write a comprehensive, deep, and detailed note about.

            Your task:
            1. Write a well-structured, in-depth Markdown note (at least 3-5 comprehensive sections with subheadings, bullet points, explanations, and key takeaways).
            2. Extract 3-6 relevant tags related to the core topic (use lowercase, hyphens instead of spaces, e.g., "machine-learning").
            3. Return your output STRICTLY as a JSON object matching this schema:

            {
                "title": "A short, descriptive title for the note",
                "type": "reference",
                "tags": ["topic-tag-1", "topic-tag-2"],
                "content": "Full detailed markdown content starting with headings (###), paragraphs, lists, and examples. Length of the text should be 350 words +"
            }

            CRITICAL: Return ONLY valid JSON. No markdown code blocks around JSON, no explanations.
        """

    @classmethod
    def from_dict(cls):
        file = CONFIG_PATH / CONFIG_FILE

        if not file.exists():
            print(f"[bold red]Config file does not exist at {file}. Using default settings.[/bold red]")
            return cls()

        with open(file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # Ensure all required fields are present in the JSON
        if not isinstance(config_data, dict):
            print("[bold red]Config file is malformed. Using default settings.[/bold red]")
            return cls()
        note_options = config_data.get("notes", {})

        model_name = note_options.get("model_name", "qwen2.5:14b")
        model_planner_note = note_options.get("model_planner_note", "llama3.2:3b")
        model_validator_note = note_options.get("model_validator_note", "qwen3:4b")

        ollama_url = note_options.get("ollama_url", "http://localhost:11434/api/generate")
        note_vault_path = pathlib.Path(note_options.get("note_vault", str(pathlib.Path.home() / "Documents" / "obsidian" / "conspects")))
        auto_git = note_options.get("auto_git", True)
        return cls(model_name, ollama_url, note_vault_path, auto_git, model_planner_note, model_validator_note)


note_config = NotesConfig.from_dict()

class WhisperConfig:
    def __init__(
            # Needs to add Precise Literal for type safety
            self,
            model_size: str = "turbo",
            device: str = "cuda",
            compute_type: str = "float16"
    ):
        if not self.check_type(model_size, device, compute_type):
            raise ValueError("Invalid configuration for Whisper model")
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = faster_whisper.WhisperModel(model_size, device=device, compute_type=compute_type)

    @staticmethod
    def check_type(model_size: str, device: str, compute_type: str) -> bool:
        valid_model_sizes: tuple[Literal["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo"]] = [
            "tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo"
        ]
        valid_devices: tuple[Literal["cpu", "cuda"]] = ("cpu", "cuda")
        valid_compute_types: tuple[Literal["int8_float16", "int8_int8", "float16"]] = ("int8_float16", "int8_int8", "float16")

        if model_size not in valid_model_sizes:
            raise ValueError(f"Invalid model size: {model_size}. Valid options are: {valid_model_sizes}")
        if device not in valid_devices:
            raise ValueError(f"Invalid device: {device}. Valid options are: {valid_devices}")
        if compute_type not in valid_compute_types:
            raise ValueError(f"Invalid compute type: {compute_type}. Valid options are: {valid_compute_types}")
        return True

    @classmethod
    def from_dict(cls):
        file = CONFIG_PATH / CONFIG_FILE

        if not file.exists():
            print(f"[bold red]Config file does not exist at {file}. Using default settings.[/bold red]")
            return cls()

        with open(file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # Ensure all required fields are present in the JSON
        if not isinstance(config_data, dict):
            print("[bold red]Config file is malformed. Using default settings.[/bold red]")
            return cls()
        # Whisper options are stored in config file under "whisper" key
        whisper_options = config_data.get("whisper", {})

        model_size = whisper_options.get("model_size", "turbo")
        device = whisper_options.get("device", "cuda")
        compute_type = whisper_options.get("compute_type", "float16")

        return cls(model_size, device, compute_type)


whisper_config = WhisperConfig.from_dict()


class Config:
    def __init__(
            self,
            note_config: NotesConfig,
            whisper_config: WhisperConfig
    ):
        self.note_config = note_config
        self.whisper_config = whisper_config


config = Config(note_config=note_config, whisper_config=whisper_config)