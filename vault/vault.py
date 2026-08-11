import os
import re
import pathlib
import datetime
from rich.console import Console
from git_client import GitClient
from models import VaultContext, VaultNote
from vault.vault_indexer import VaultIndexer

console = Console()


class VaultManager:
    """
    Відповідає за роботу з Obsidian Vault.

    Responsibilities:
    - файлові операції з Vault;
    - збереження Markdown-нот;
    - Git integration;
    - отримання контексту Vault;
    - інтеграція з локальним SQLite index.

    SQLite та індексація делегуються VaultIndexer.
    """

    def __init__(
        self,
        vault_path: pathlib.Path,
        auto_git: bool = True,
    ):
        self.vault_path = vault_path.resolve()
        self.auto_git = auto_git

        self.git = GitClient(
            vault_path=self.vault_path
        )

        # SQLite index є похідним від Markdown Vault.
        self.indexer = VaultIndexer(
            vault_path=self.vault_path
        )

    # ============================================================
    # LEGACY CONTEXT
    # ============================================================

    def get_existing_context(
        self,
        max_tags: int = 50,
        max_files: int = 100,
    ) -> tuple[list[str], list[str]]:
        """
        Старий механізм отримання контексту.

        НЕ ВИДАЛЯЄМО.

        Залишається для backward compatibility та можливості
        поступового переходу на SQLite index.
        """

        existing_tags = {"ai-generated"}
        existing_files = []

        if not self.vault_path.exists():
            return list(existing_tags), existing_files

        tag_regex = re.compile(
            r"^\s*-\s*([a-zA-Z0-9_\-]+)"
        )

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if not file.endswith(".md"):
                    continue

                file_stem = pathlib.Path(file).stem
                existing_files.append(file_stem)

                file_path = pathlib.Path(root) / file

                try:
                    with open(
                        file_path,
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as f:
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
                                    existing_tags.add(
                                        match.group(1).lower()
                                    )

                except Exception:
                    print("Error occurred while reading file.")

        return (
            list(existing_tags)[:max_tags],
            existing_files[:max_files],
        )

    # ============================================================
    # NEW CONTEXT API
    # ============================================================

    def get_existing_context_v2(
        self,
        sync: bool = True,
    ) -> VaultContext:
        """
        Get Vault context from the SQLite index.

        Pipeline:

            Markdown Vault
                  ↓
             VaultIndexer
                  ↓
                SQLite
                  ↓
            VaultContext

        The returned VaultContext is intentionally lightweight
        and suitable for passing into the AI generation pipeline.
        """

        if sync:
            self.indexer.sync()

        metadata_list = self.indexer.get_notes()

        vault_notes: list[VaultNote] = []

        for metadata in metadata_list:
            tags = self.indexer.get_note_tags(
                metadata.id
            )

            vault_notes.append(
                VaultNote(
                    name=metadata.name,
                    path=metadata.path,
                    tags=[
                        tag.name
                        for tag in tags
                    ],
                    type=metadata.type,
                )
            )

        vault_tags = sorted(
            {
                tag.name
                for tag in self.indexer.get_tags()
            }
        )

        return VaultContext(
            notes=vault_notes,
            tags=vault_tags,
        )

    # ============================================================
    # NOTE PERSISTENCE
    # ============================================================

    def save_note(
        self,
        data: dict,
    ) -> pathlib.Path | None:
        """
        Save generated note into the Vault.

        After saving the Markdown file, the SQLite index is updated.
        """

        if not data:
            return None

        folder = data.get(
            "folder",
            "Inbox",
        ).strip("/")

        target_dir = (
            self.vault_path / folder
        )

        target_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        default_title = (
            f"note_"
            f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        title = (
            data.get("title")
            or default_title
        ).strip()

        safe_title = "".join(
            c
            for c in title
            if c.isalnum()
            or c in (" ", "-", "_")
        ).rstrip()

        note_path = (
            target_dir
            / f"{safe_title}.md"
        )

        # ========================================================
        # TAGS
        # ========================================================

        clean_tags = {
            "ai-generated"
        }

        for tag in data.get(
            "tags",
            [],
        ):
            clean_tags.add(
                str(tag)
                .strip()
                .lower()
                .replace("_", "-")
                .replace("#", "")
            )

        yaml_tags = "\n".join(
            f"  - {tag}"
            for tag in clean_tags
        )

        # ========================================================
        # BACKLINKS
        # ========================================================

        raw_backlinks = data.get(
            "backlinks",
            [],
        )

        if isinstance(
            raw_backlinks,
            str,
        ):
            raw_backlinks = [
                raw_backlinks
            ]

        formatted_links = []

        for backlink in raw_backlinks:
            link = str(
                backlink
            ).strip()

            if not link:
                continue

            if not link.startswith("[["):
                link = f"[[{link}]]"

            formatted_links.append(link)

        if len(formatted_links) == 1:
            yaml_backlinks = (
                f'"{formatted_links[0]}"'
            )

        elif len(formatted_links) > 1:
            yaml_backlinks = (
                "\n"
                + "\n".join(
                    f'  - "{link}"'
                    for link in formatted_links
                )
            )

        else:
            yaml_backlinks = '""'

        # ========================================================
        # CONTENT
        # ========================================================

        raw_content = (
            data.get(
                "content",
                "",
            )
            .strip()
        )

        # Видаляємо H1, якщо модель його випадково створила.
        if raw_content.startswith("# "):
            raw_content = re.sub(
                r"^#\s+.*?\n+",
                "",
                raw_content,
            ).strip()

        now_str = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )

        doc_type = data.get(
            "type",
            "reference",
        )

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

        # ========================================================
        # WRITE
        # ========================================================

        with open(
            note_path,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(
                markdown_body
            )

        console.print(
            "[bold green]"
            "✔ Успішно збережено в Obsidian:"
            "[/bold green] "
            f"{note_path}"
        )

        # ========================================================
        # INDEX
        # ========================================================

        # Не обов'язково робити повний sync.
        # Але поки що це найнадійніший варіант.
        self.indexer.sync()

        # ========================================================
        # GIT
        # ========================================================

        if self.auto_git:
            self.git.commit_and_push(
                file_path=note_path,
                commit_message=f"Add {title}",
            )

        return note_path

