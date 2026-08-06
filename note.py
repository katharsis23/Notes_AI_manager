import sys
import pathlib
import datetime
import httpx as http
from rich.console import Console
import asyncio
import json
import argparse

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
            console.print(f"[bold red]Config file does not exist at {file}. Using default settings.[/bold red]")
            return cls()

        with open(file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # Ensure all required fields are present in the JSON
        if not isinstance(config_data, dict):
            console.print("[bold red]Config file is malformed. Using default settings.[/bold red]")
            return cls()

        model_name = config_data.get("model_name", "qwen2.5:14b")
        ollama_url = config_data.get("ollama_url", "http://localhost:11434/api/generate")
        note_vault_path = pathlib.Path(config_data.get("note_vault", str(pathlib.Path.home() / "Documents" / "obsidian" / "conspects")))

        return cls(model_name, ollama_url, note_vault_path)


console = Console()
config = Config.from_dict()

async def process_ollama(raw_text: str) -> dict | None:
    try:
        payload = {
            "model": config.model_name,
            "prompt": f"System: {config.system_prompt}\nUser topic: {raw_text}",
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        }

        async with http.AsyncClient() as client:
            response = await client.post(url=config.ollama_url, timeout=300, json=payload)
            response.raise_for_status()

            response_data = response.json()
            raw_json = response_data.get("response", "")

            if raw_json:
                return json.loads(raw_json)

        raise Exception('Empty response from Ollama')

    except http.HTTPStatusError as error:
        console.print(f"[bold red]HTTP Error:[/bold red]\n time: {datetime.datetime.now()},\n status code: {error.response.status_code},\n reason: {error.response.reason_phrase}")
        return None

    except Exception as error:
        console.print(f"[bold red]Exception occurred:[/bold red]\n time: {datetime.datetime.now()},\n error: {error}")
        return None

def save_note(data: dict) -> pathlib.Path | None:
    if not data:
        console.print("[bold red]No data received to save.[/bold red]")
        return None

    config.note_vault.mkdir(parents=True, exist_ok=True)

    default_title = f"note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    safe_title = "".join(c for c in data.get("title") or default_title if c.isalnum() or c in (" ", "-", "_")).rstrip()
    note_path = config.note_vault / f"{safe_title}.md"

    # 1. Формуємо списки тегів із примусовим додаванням ai-generated
    raw_tags = data.get("tags", [])
    clean_tags = ["ai-generated"]  # Гарантуємо наявність ai-generated

    for tag in raw_tags:
        formatted = str(tag).strip().lower().replace("_", "-").replace("#", "")
        if formatted and formatted not in clean_tags:
            clean_tags.append(formatted)

    # YAML формат для тегів списком (Obsidian ідеально парсить такий формат)
    yaml_tags = "\n".join([f"  - {t}" for t in clean_tags])

    # 2. Формуємо валідний YAML Frontmatter (три дефіси строго на початку файла!)
    markdown_body = f"""---
date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
type: {data.get('type', 'reference')}
tags:
{yaml_tags}
---

# {data.get('title', safe_title)}

{data.get('content', '').strip()}
"""

    with open(note_path, 'w', encoding='utf-8') as file:
        file.write(markdown_body)

    console.print(f"[bold green]Успішно збережено в Obsidian:[/bold green] {note_path}")
    return note_path

async def main():
    parser = argparse.ArgumentParser(description="Generate detailed Obsidian notes via Ollama.")
    parser.add_argument("topic", nargs="+", help="Topic or prompt for the note")

    args = parser.parse_args()
    raw_input_text = " ".join(args.topic)

    with console.status(f"[bold green]Опрацьовую тему: '{raw_input_text}'...[/bold green]"):
        note_data = await process_ollama(raw_input_text)

    if note_data:
        save_note(note_data)

if __name__ == "__main__":
    asyncio.run(main())