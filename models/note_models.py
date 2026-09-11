from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


# ============================================================
# AI NOTE GENERATION
# ============================================================

@dataclass
class NoteSection:
    title: str
    purpose: str
    elements: list[str]


@dataclass
class DiagramPlan:
    needed: bool
    type: str | None = None
    purpose: str | None = None


@dataclass
class NotePlan:
    title: str
    type: str
    folder: str
    tags: list[str]
    backlinks: list[str]
    outline: list[NoteSection]
    diagram: DiagramPlan


# ============================================================
# NOTE VALIDATION
# ============================================================

@dataclass
class ValidationIssue:
    severity: str
    type: str
    description: str
    section: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    score: float
    issues: list[ValidationIssue]
    recommendation: str


# ============================================================
# VAULT CONTEXT
# ============================================================

@dataclass
class VaultNote:
    """
    Lightweight representation of an Obsidian note.

    Used when passing Vault context to the AI pipeline.
    """

    name: str
    path: str
    tags: list[str]
    type: str | None = None


@dataclass
class VaultContext:
    """
    Context extracted from the Obsidian Vault.

    This is intentionally independent from SQLite.
    """

    notes: list[VaultNote]
    tags: list[str]


# ============================================================
# SQLITE / VAULT INDEX
# ============================================================

@dataclass
class NoteMetadata:
    """
    Metadata stored for a note in the local SQLite index.

    Corresponds roughly to the `notes` table.
    """

    id: UUID = field(default_factory=uuid4)

    name: str = ""
    path: str = ""
    folder: str = ""

    type: str | None = None

    modified_at: datetime | None = None

    # SHA-256 hash of the source Markdown file.
    # Used to detect changes without comparing full contents.
    hash: str = ""


@dataclass
class NoteContent:
    """
    Markdown content belonging to a note.

    Corresponds to the content part of the indexed note.
    """

    note_id: UUID
    content: str


@dataclass
class Tag:
    """
    Unique tag in the Vault.

    Corresponds to the `tags` table.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""


@dataclass
class NoteTag:
    """
    Many-to-many relation between notes and tags.

    Corresponds to the `note_tags` table.
    """

    note_id: UUID
    tag_id: UUID


@dataclass
class NoteLink:
    """
    Directed link between two notes.

    source_note_id -> target_note_id

    This represents an Obsidian [[WikiLink]].

    Backlinks are therefore not stored separately:
    a backlink to note B is simply a NoteLink
    where target_note_id == B.id.
    """

    source_note_id: UUID
    target_note_id: UUID