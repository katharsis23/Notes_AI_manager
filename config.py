import pathlib
import json

CONFIG_PATH = pathlib.Path.home() / ".config" / "obsidian-ai-note"
CONFIG_FILE = "config.json"

class Config:
    """
    Class to store all the constants and global vars
    """
    def __init__(
        self,
        model_name: str = "qwen2.5:14b",
        ollama_url: str = "http://localhost:11434/api/generate",
        note_vault: pathlib.Path = pathlib.Path.home() / "Documents" / "obsidian" / "conspects"
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.note_vault = note_vault
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

        model_name = config_data.get("model_name", "qwen2.5:14b")
        ollama_url = config_data.get("ollama_url", "http://localhost:11434/api/generate")
        note_vault_path = pathlib.Path(config_data.get("note_vault", str(pathlib.Path.home() / "Documents" / "obsidian" / "conspects")))

        return cls(model_name, ollama_url, note_vault_path)


config = Config.from_dict()
