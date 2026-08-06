import os
import re
import pathlib
import datetime
from rich.console import Console
import textwrap


console = Console()

class VaultManager:
    """Відповідає за інспекцію та запис нотаток у Obsidian Vault."""
    
    def __init__(self, vault_path: pathlib.Path):
        self.vault_path = vault_path

    def get_existing_context(self, max_tags: int = 50, max_files: int = 100) -> tuple[list[str], list[str]]:
        """Сканує Vault на наявність існуючих MD-файлів та тегів у їхньому YAML frontmatter."""
        existing_tags = {"ai-generated"}
        existing_files = []

        if not self.vault_path.exists():
            return list(existing_tags), existing_files

        tag_regex = re.compile(r"^\s*-\s*([a-zA-Z0-9_\-]+)")

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if not file.endswith(".md"):
                    continue

                file_stem = pathlib.Path(file).stem
                existing_files.append(file_stem)

                file_path = pathlib.Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        in_yaml = False
                        for line in f:
                            if line.strip() == "---":
                                if not in_yaml:
                                    in_yaml = True
                                    continue
                                else:
                                    break
                            if in_yaml:
                                match = tag_regex.match(line)
                                if match:
                                    existing_tags.add(match.group(1).lower())
                except Exception:
                    print("Error occured \n.")

        return list(existing_tags)[:max_tags], existing_files[:max_files]

    def save_note(self, data: dict) -> pathlib.Path | None:
        if not data:
            return None

        folder = data.get("folder", "Inbox").strip("/")
        target_dir = self.vault_path / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        default_title = f"note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        title = (data.get("title") or default_title).strip()
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).rstrip()
        note_path = target_dir / f"{safe_title}.md"

        # Обробка тегів
        clean_tags = {"ai-generated"}
        for t in data.get("tags", []):
            clean_tags.add(str(t).strip().lower().replace("_", "-").replace("#", ""))
        
        yaml_tags = "\n".join([f"  - {t}" for t in clean_tags])

        # Обробка backlinks під потрібний формат (один рядок або список)
        raw_backlinks = data.get("backlinks", [])
        if isinstance(raw_backlinks, str):
            raw_backlinks = [raw_backlinks]

        formatted_links = []
        for b in raw_backlinks:
            b_str = str(b).strip()
            if not b_str.startswith("[["):
                b_str = f"[[{b_str}]]"
            formatted_links.append(b_str)

        if len(formatted_links) == 1:
            yaml_backlinks = f'"{formatted_links[0]}"'
        elif len(formatted_links) > 1:
            yaml_backlinks = "\n" + "\n".join([f'  - "{link}"' for link in formatted_links])
        else:
            yaml_backlinks = '""'

        # Очищення вмісту від повторного H1
        raw_content = data.get("content", "").strip()
        if raw_content.startswith("# "):
            raw_content = re.sub(r"^#\s+.*?\n+", "", raw_content).strip()

        # Збираємо чистий Markdown без f-string indentation
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        doc_type = data.get('type', 'reference')

        markdown_body = (
            "---\n"
            f"date: {now_str}\n"
            f"type: {doc_type}\n"
            "tags:\n"
            f"{yaml_tags}\n"
            f"backlinks: {yaml_backlinks}\n"
            "---\n\n"
            f"# {title}\n\n"
            f"{raw_content}\n"
        )

        with open(note_path, "w", encoding="utf-8") as file:
            file.write(markdown_body)

        console.print(f"[bold green]✔ Успішно збережено в Obsidian:[/bold green] {note_path}")
        return note_path