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

        clean_tags = {"ai-generated"}
        for t in data.get("tags", []):
            clean_tags.add(str(t).strip().lower().replace("_", "-").replace("#", ""))

        yaml_tags = "\n".join([f"  - {t}" for t in clean_tags])
        backlinks = data.get("backlinks", [])
        yaml_backlinks = "\n".join([f'  - "{b}"' if b.startswith("[[") else f'  - "[[{b}]]"' for b in backlinks]) if backlinks else "  []"

        # Очищення вмісту: якщо модель на початку згенерувала заголовок # Title, прибираємо його,
        # щоб не дублювати з нашим # {title}
        raw_content = data.get("content", "").strip()
        if raw_content.startswith("# "):
            raw_content = re.sub(r"^#\s+.*?\n+", "", raw_content).strip()

        # Використовуємо textwrap.dedent, щоб прибрати будь-які ліві відступи
        markdown_body = textwrap.dedent(f"""\
        ---
        date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
        type: {data.get('type', 'reference')}
        folder: {folder}
        tags:
        {yaml_tags}
        related_notes:
        {yaml_backlinks}
        ---

        # {title}

        {raw_content}
        """)

        with open(note_path, "w", encoding="utf-8") as file:
            file.write(markdown_body)

        console.print(f"[bold green]✔ Успішно збережено в Obsidian:[/bold green] {note_path}")
        return note_path