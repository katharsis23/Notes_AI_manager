from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from models.note_models import NoteContent, NoteMetadata, Tag


class VaultIndexer:
    """
    SQLite index of an Obsidian Vault.

    Responsibilities:
    - initialize SQLite database
    - scan Markdown files
    - detect file changes using SHA-256
    - parse basic YAML frontmatter
    - extract tags
    - extract [[WikiLinks]]
    - maintain notes, tags and relations
    - remove notes deleted from the Vault

    The index is a derived representation of the Markdown Vault.
    Markdown files remain the source of truth.
    """

    DB_DIR_NAME = ".obsidian-ai"
    DB_FILE_NAME = "vault.db"

    WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

    TAG_RE = re.compile(r"(?<![\w-])#([A-Za-z0-9_/-]+)")

    FRONTMATTER_TAG_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_/-]+)\s*$")

    FRONTMATTER_BOUNDARY = "---"

    def __init__(
        self,
        vault_path: Path,
        db_path: Path | None = None,
    ):
        self.vault_path = vault_path.resolve()

        if db_path is None:
            db_path = self.vault_path / self.DB_DIR_NAME / self.DB_FILE_NAME

        self.db_path = db_path.resolve()

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    # ============================================================
    # DATABASE
    # ============================================================

    def _connect(self) -> sqlite3.Connection:
        """
        Create a SQLite connection.

        Foreign keys are explicitly enabled because SQLite does not
        enable them by default.
        """

        connection = sqlite3.connect(self.db_path)

        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def initialize(self) -> None:
        """
        Create database schema if it does not exist.
        """

        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    folder TEXT NOT NULL,
                    type TEXT,
                    modified_at TEXT,
                    hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS note_content (
                    note_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,

                    FOREIGN KEY (note_id)
                        REFERENCES notes(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS note_tags (
                    note_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,

                    PRIMARY KEY (note_id, tag_id),

                    FOREIGN KEY (note_id)
                        REFERENCES notes(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (tag_id)
                        REFERENCES tags(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS note_links (
                    source_note_id TEXT NOT NULL,
                    target_note_id TEXT NOT NULL,

                    PRIMARY KEY (
                        source_note_id,
                        target_note_id
                    ),

                    FOREIGN KEY (source_note_id)
                        REFERENCES notes(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (target_note_id)
                        REFERENCES notes(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_notes_path
                    ON notes(path);

                CREATE INDEX IF NOT EXISTS idx_notes_hash
                    ON notes(hash);

                CREATE INDEX IF NOT EXISTS idx_notes_type
                    ON notes(type);

                CREATE INDEX IF NOT EXISTS idx_notes_modified
                    ON notes(modified_at);

                CREATE INDEX IF NOT EXISTS idx_note_tags_tag
                    ON note_tags(tag_id);

                CREATE INDEX IF NOT EXISTS idx_note_links_target
                    ON note_links(target_note_id);

                CREATE INDEX IF NOT EXISTS idx_note_links_source
                    ON note_links(source_note_id);
                """
            )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def sync(self) -> None:
        """
        Synchronize SQLite index with the current Vault.

        Algorithm:

        1. Scan all Markdown files.
        2. Calculate their hashes.
        3. Skip unchanged files.
        4. Index new/changed files.
        5. Remove files that no longer exist.
        6. Resolve WikiLinks between all indexed notes.
        7. Cleanup orphan tags.
        """

        if not self.vault_path.exists():
            return

        current_files = {
            self._relative_path(path): path for path in self._iter_markdown_files()
        }

        with self._connect() as db:
            indexed_paths = {
                row["path"] for row in db.execute("SELECT path FROM notes").fetchall()
            }

            has_changes = False

            for relative_path, path in current_files.items():
                file_hash = self._calculate_hash(path)

                existing = db.execute(
                    """
                    SELECT id, hash
                    FROM notes
                    WHERE path = ?
                    """,
                    (relative_path,),
                ).fetchone()

                if existing is not None and existing["hash"] == file_hash:
                    continue

                has_changes = True

                self._index_file(
                    db=db,
                    path=path,
                    relative_path=relative_path,
                    file_hash=file_hash,
                    existing_id=(existing["id"] if existing is not None else None),
                )

            deleted_paths = indexed_paths - set(current_files)

            if deleted_paths:
                has_changes = True

            for deleted_path in deleted_paths:
                db.execute(
                    """
                    DELETE FROM notes
                    WHERE path = ?
                    """,
                    (deleted_path,),
                )

            # Hot reloading file relationship in case of changes
            if has_changes:
                self._resolve_links(db)

            self._cleanup_orphan_tags(db)

    def rebuild(self) -> None:
        """
        Completely rebuild the index.

        Useful after schema changes or when the index is suspected
        to be inconsistent.
        """

        with self._connect() as db:
            db.execute("DELETE FROM notes")
            db.execute("DELETE FROM tags")

        self.sync()

    # ============================================================
    # FILE DISCOVERY
    # ============================================================

    def _iter_markdown_files(self):
        """
        Iterate through Markdown files in the Vault.

        Internal application directories are skipped.
        """

        ignored_directories = {
            ".git",
            ".obsidian",
            self.DB_DIR_NAME,
        }

        for path in self.vault_path.rglob("*.md"):
            if any(
                part in ignored_directories
                for part in path.relative_to(self.vault_path).parts
            ):
                continue

            if path.is_file():
                yield path

    def _relative_path(self, path: Path) -> str:
        """
        Return Vault-relative POSIX path.

        Example:

            Programming/Python/AsyncIO.md
        """

        return path.relative_to(self.vault_path).as_posix()

    # ============================================================
    # INDEXING
    # ============================================================

    def _index_file(
        self,
        db: sqlite3.Connection,
        path: Path,
        relative_path: str,
        file_hash: str,
        existing_id: str | None,
    ) -> None:
        """
        Index a single Markdown file.
        """

        content = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        frontmatter, body = self._parse_frontmatter(content)

        note_id = existing_id if existing_id is not None else str(uuid4())

        name = path.stem

        folder = str(Path(relative_path).parent)

        if folder == ".":
            folder = ""

        note_type = frontmatter.get("type")

        modified_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()

        metadata = NoteMetadata(
            id=UUID(note_id),
            name=name,
            path=relative_path,
            folder=folder,
            type=note_type,
            modified_at=datetime.fromisoformat(modified_at),
            hash=file_hash,
        )

        self._upsert_note(
            db=db,
            metadata=metadata,
        )

        self._upsert_content(
            db=db,
            content=NoteContent(
                note_id=metadata.id,
                content=body,
            ),
        )

        tags = self._extract_tags(
            frontmatter=frontmatter,
            content=body,
        )

        self._replace_note_tags(
            db=db,
            note_id=metadata.id,
            tags=tags,
        )

        self._replace_note_links(
            db=db,
            source_note_id=metadata.id,
            wikilinks=self._extract_wikilinks(body),
        )

    def _upsert_note(
        self,
        db: sqlite3.Connection,
        metadata: NoteMetadata,
    ) -> None:
        db.execute(
            """
            INSERT INTO notes (
                id,
                name,
                path,
                folder,
                type,
                modified_at,
                hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(path)
            DO UPDATE SET
                name = excluded.name,
                folder = excluded.folder,
                type = excluded.type,
                modified_at = excluded.modified_at,
                hash = excluded.hash
            """,
            (
                str(metadata.id),
                metadata.name,
                metadata.path,
                metadata.folder,
                metadata.type,
                (metadata.modified_at.isoformat() if metadata.modified_at else None),
                metadata.hash,
            ),
        )

    def _upsert_content(
        self,
        db: sqlite3.Connection,
        content: NoteContent,
    ) -> None:
        db.execute(
            """
            INSERT INTO note_content (
                note_id,
                content
            )
            VALUES (?, ?)

            ON CONFLICT(note_id)
            DO UPDATE SET
                content = excluded.content
            """,
            (
                str(content.note_id),
                content.content,
            ),
        )

    # ============================================================
    # FRONTMATTER
    # ============================================================

    def _parse_frontmatter(
        self,
        content: str,
    ) -> tuple[dict, str]:
        """
        Parse a minimal YAML frontmatter.

        We intentionally do not introduce PyYAML at this stage.

        Currently supported:

            ---
            type: concept
            tags:
              - python
              - asyncio
            ---

        Returns:

            (frontmatter_dict, markdown_body)
        """

        lines = content.splitlines()

        if not lines or lines[0].strip() != self.FRONTMATTER_BOUNDARY:
            return {}, content

        end_index = None

        for index in range(1, len(lines)):
            if lines[index].strip() == self.FRONTMATTER_BOUNDARY:
                end_index = index
                break

        if end_index is None:
            return {}, content

        yaml_lines = lines[1:end_index]

        frontmatter: dict = {}

        current_key: str | None = None

        for line in yaml_lines:
            stripped = line.strip()

            if not stripped:
                continue

            # key: value
            if ":" in stripped and not stripped.startswith("-"):
                key, value = stripped.split(
                    ":",
                    1,
                )

                key = key.strip()
                value = value.strip()

                current_key = key

                if value:
                    frontmatter[key] = value.strip('"').strip("'")
                else:
                    frontmatter[key] = []

                continue

            # list item
            if stripped.startswith("-") and current_key:
                value = stripped[1:].strip()

                if not isinstance(
                    frontmatter.get(current_key),
                    list,
                ):
                    frontmatter[current_key] = []

                frontmatter[current_key].append(value.strip('"').strip("'"))

        body = "\n".join(lines[end_index + 1 :])

        return frontmatter, body

    # ============================================================
    # TAGS
    # ============================================================

    def _extract_tags(
        self,
        frontmatter: dict,
        content: str,
    ) -> set[str]:
        """
        Extract tags from:

        1. YAML frontmatter
        2. Inline Markdown tags

        Tags are normalized to lowercase.
        """

        tags: set[str] = set()

        frontmatter_tags = frontmatter.get(
            "tags",
            [],
        )

        if isinstance(frontmatter_tags, str):
            frontmatter_tags = [frontmatter_tags]

        for tag in frontmatter_tags:
            normalized = self._normalize_tag(tag)

            if normalized:
                tags.add(normalized)

        for match in self.TAG_RE.finditer(content):
            normalized = self._normalize_tag(match.group(1))

            if normalized:
                tags.add(normalized)

        return tags

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return str(tag).strip().lower().lstrip("#").replace("_", "-")

    def _replace_note_tags(
        self,
        db: sqlite3.Connection,
        note_id: UUID,
        tags: set[str],
    ) -> None:
        """
        Replace all tag relations for a note.
        """

        note_id_str = str(note_id)

        db.execute(
            """
            DELETE FROM note_tags
            WHERE note_id = ?
            """,
            (note_id_str,),
        )

        for tag_name in tags:
            tag_id = self._get_or_create_tag(
                db,
                tag_name,
            )

            db.execute(
                """
                INSERT OR IGNORE INTO note_tags (
                    note_id,
                    tag_id
                )
                VALUES (?, ?)
                """,
                (
                    note_id_str,
                    tag_id,
                ),
            )

    def _get_or_create_tag(
        self,
        db: sqlite3.Connection,
        tag_name: str,
    ) -> str:
        existing = db.execute(
            """
            SELECT id
            FROM tags
            WHERE name = ?
            """,
            (tag_name,),
        ).fetchone()

        if existing is not None:
            return existing["id"]

        tag_id = str(uuid4())

        db.execute(
            """
            INSERT INTO tags (
                id,
                name
            )
            VALUES (?, ?)
            """,
            (
                tag_id,
                tag_name,
            ),
        )

        return tag_id

    def _cleanup_orphan_tags(
        self,
        db: sqlite3.Connection,
    ) -> None:
        """
        Remove tags that are no longer used by any note.
        """

        db.execute(
            """
            DELETE FROM tags
            WHERE id NOT IN (
                SELECT DISTINCT tag_id
                FROM note_tags
            )
            """
        )

    # ============================================================
    # WIKILINKS
    # ============================================================

    def _extract_wikilinks(
        self,
        content: str,
    ) -> set[str]:
        """
        Extract Obsidian WikiLinks.

        Examples:

            [[Python]]
            [[Python|Python language]]
            [[Python#AsyncIO]]

        Result:

            {"Python"}
        """

        links = set()

        for match in self.WIKILINK_RE.finditer(content):
            target = match.group(1).strip()

            if target:
                links.add(target)

        return links

    def _replace_note_links(
        self,
        db: sqlite3.Connection,
        source_note_id: UUID,
        wikilinks: set[str],
    ) -> None:
        """
        Replace all outgoing links for a note.

        Links that point to files which do not currently exist
        in the Vault are ignored.

        This means unresolved Obsidian links are not stored
        in note_links yet.
        """

        source_id = str(source_note_id)

        db.execute(
            """
            DELETE FROM note_links
            WHERE source_note_id = ?
            """,
            (source_id,),
        )

        for target_name in wikilinks:
            target_id = self._resolve_note(
                db,
                target_name,
            )

            if target_id is None:
                continue

            if target_id == source_id:
                continue

            db.execute(
                """
                INSERT OR IGNORE INTO note_links (
                    source_note_id,
                    target_note_id
                )
                VALUES (?, ?)
                """,
                (
                    source_id,
                    target_id,
                ),
            )

    def _resolve_note(
        self,
        db: sqlite3.Connection,
        target: str,
    ) -> str | None:
        """
        Resolve an Obsidian WikiLink target to a note ID.

        Supports:

            [[Python]]
            [[folder/Python]]

        We first try an exact Vault-relative path,
        then a filename match.
        """

        target = target.strip().strip("/")

        # Remove optional .md extension.
        if target.lower().endswith(".md"):
            target = target[:-3]

        exact = db.execute(
            """
            SELECT id
            FROM notes
            WHERE path = ?
               OR path = ?
            """,
            (
                target,
                f"{target}.md",
            ),
        ).fetchone()

        if exact is not None:
            return exact["id"]

        # Fallback: match by note name.
        name = Path(target).name

        matches = db.execute(
            """
            SELECT id
            FROM notes
            WHERE name = ?
            """,
            (name,),
        ).fetchall()

        # Ambiguous filename.
        # Do not randomly select one.
        if len(matches) != 1:
            return None

        return matches[0]["id"]

    def _resolve_links(self, db: sqlite3.Connection) -> None:
        """
        Re-evaluate all outgoing WikiLinks for indexed notes.

        This pass runs after all files have been inserted/updated in the DB
        to ensure links to newly created or renamed notes are resolved properly.
        """
        # Reading the context for resolution
        rows = db.execute(
            """
            SELECT note_id, content
            FROM note_content
            """
        ).fetchall()

        for row in rows:
            source_id = UUID(row["note_id"])
            body = row["content"]
            wikilinks = self._extract_wikilinks(body)

            self._replace_note_links(
                db=db,
                source_note_id=source_id,
                wikilinks=wikilinks,
            )

    # ============================================================
    # HASHING
    # ============================================================

    @staticmethod
    def _calculate_hash(
        path: Path,
    ) -> str:
        """
        Calculate SHA-256 hash of a Markdown file.
        """

        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest()

    # ============================================================
    # READ API
    # ============================================================
    def get_notes(self) -> list[NoteMetadata]:
        """
        Return all indexed notes.
        """

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    id,
                    name,
                    path,
                    folder,
                    type,
                    modified_at,
                    hash
                FROM notes
                ORDER BY path
                """
            ).fetchall()

        return [self._row_to_metadata(row) for row in rows]

    def get_note(
        self,
        path: str,
    ) -> NoteMetadata | None:
        """
        Retrieve note metadata by Vault-relative path.
        """

        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    id,
                    name,
                    path,
                    folder,
                    type,
                    modified_at,
                    hash
                FROM notes
                WHERE path = ?
                """,
                (path,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_metadata(row)

    def get_content(
        self,
        note_id: UUID,
    ) -> NoteContent | None:
        """
        Retrieve Markdown content by note ID.
        """

        with self._connect() as db:
            row = db.execute(
                """
                SELECT note_id, content
                FROM note_content
                WHERE note_id = ?
                """,
                (str(note_id),),
            ).fetchone()

        if row is None:
            return None

        return NoteContent(
            note_id=UUID(row["note_id"]),
            content=row["content"],
        )

    def get_tags(self) -> list[Tag]:
        """
        Return all tags in the Vault index.
        """

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT id, name
                FROM tags
                ORDER BY name
                """
            ).fetchall()

        return [
            Tag(
                id=UUID(row["id"]),
                name=row["name"],
            )
            for row in rows
        ]

    def get_note_tags(
        self,
        note_id: UUID,
    ) -> list[Tag]:
        """
        Return tags assigned to a note.
        """

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    tags.id,
                    tags.name
                FROM tags
                JOIN note_tags
                    ON note_tags.tag_id = tags.id
                WHERE note_tags.note_id = ?
                ORDER BY tags.name
                """,
                (str(note_id),),
            ).fetchall()

        return [
            Tag(
                id=UUID(row["id"]),
                name=row["name"],
            )
            for row in rows
        ]

    def get_backlinks(
        self,
        note_id: UUID,
    ) -> list[NoteMetadata]:
        """
        Return notes linking TO the specified note.
        """

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    notes.id,
                    notes.name,
                    notes.path,
                    notes.folder,
                    notes.type,
                    notes.modified_at,
                    notes.hash
                FROM notes
                JOIN note_links
                    ON note_links.source_note_id = notes.id
                WHERE note_links.target_note_id = ?
                ORDER BY notes.name
                """,
                (str(note_id),),
            ).fetchall()

        return [self._row_to_metadata(row) for row in rows]

    def get_outgoing_links(
        self,
        note_id: UUID,
    ) -> list[NoteMetadata]:
        """
        Return notes referenced BY the specified note.
        """

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    notes.id,
                    notes.name,
                    notes.path,
                    notes.folder,
                    notes.type,
                    notes.modified_at,
                    notes.hash
                FROM notes
                JOIN note_links
                    ON note_links.target_note_id = notes.id
                WHERE note_links.source_note_id = ?
                ORDER BY notes.name
                """,
                (str(note_id),),
            ).fetchall()

        return [self._row_to_metadata(row) for row in rows]

    # ============================================================
    # SEARCH
    # ============================================================

    def search_notes(
        self,
        query: str,
        limit: int = 20,
    ) -> list[NoteMetadata]:
        """
        Simple metadata search.

        This is intentionally NOT semantic/vector search yet.

        FTS5 can be introduced separately after the basic index
        is stable.
        """

        pattern = f"%{query}%"

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    id,
                    name,
                    path,
                    folder,
                    type,
                    modified_at,
                    hash
                FROM notes
                WHERE name LIKE ?
                   OR path LIKE ?
                ORDER BY name
                LIMIT ?
                """,
                (
                    pattern,
                    pattern,
                    limit,
                ),
            ).fetchall()

        return [self._row_to_metadata(row) for row in rows]

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _row_to_metadata(
        row: sqlite3.Row,
    ) -> NoteMetadata:
        modified_at = None

        if row["modified_at"]:
            modified_at = datetime.fromisoformat(row["modified_at"])

        return NoteMetadata(
            id=UUID(row["id"]),
            name=row["name"],
            path=row["path"],
            folder=row["folder"],
            type=row["type"],
            modified_at=modified_at,
            hash=row["hash"],
        )
