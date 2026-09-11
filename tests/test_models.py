"""Tests for the domain models in :mod:`models`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from models.dev_models import QualityIssue, QualityJudgement
from models.note_models import (
    DiagramPlan,
    NoteContent,
    NoteLink,
    NoteMetadata,
    NotePlan,
    NoteTag,
    Tag,
    ValidationIssue,
    ValidationResult,
    VaultContext,
    VaultNote,
)


def test_note_section_and_plan_construction(note_plan: NotePlan) -> None:
    assert note_plan.title == "Test Note"
    assert note_plan.folder == "Concepts"
    assert len(note_plan.outline) == 1
    assert note_plan.diagram.needed is False


def test_diagram_plan_defaults() -> None:
    diagram = DiagramPlan(needed=True)
    assert diagram.needed is True
    assert diagram.type is None
    assert diagram.purpose is None


def test_validation_result() -> None:
    result = ValidationResult(
        valid=False,
        score=4.5,
        issues=[
            ValidationIssue(
                severity="major",
                type="factual_error",
                description="Wrong claim",
                section="Intro",
            )
        ],
        recommendation="Fix it",
    )
    assert result.issues[0].section == "Intro"
    assert result.score == 4.5


def test_vault_context(vault_context: VaultContext) -> None:
    assert len(vault_context.notes) == 2
    assert "python" in vault_context.tags


def test_note_metadata_defaults() -> None:
    metadata = NoteMetadata()
    assert isinstance(metadata.id, UUID)
    assert metadata.name == ""
    assert metadata.hash == ""
    assert isinstance(NoteContent(note_id=metadata.id, content="x"), NoteContent)
    assert NoteTag(note_id=metadata.id, tag_id=metadata.id)
    assert NoteLink(source_note_id=metadata.id, target_note_id=metadata.id)
    assert Tag(name="python").name == "python"


def test_note_metadata_ids_are_unique() -> None:
    assert NoteMetadata().id != NoteMetadata().id


def test_quality_judgement_validates_score_bounds() -> None:
    judgement = QualityJudgement(
        valid=True,
        score=9.0,
        issues=[QualityIssue(severity="minor", type="grammar", description="typo")],
        recommendation="ok",
    )
    assert judgement.score == 9.0


def test_quality_judgement_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        QualityJudgement(valid=True, score=11.0, recommendation="", issues=[])


def test_dev_models_reject_unknown_issue_type() -> None:
    with pytest.raises(ValidationError):
        QualityIssue(
            severity="minor",
            type="not_a_real_type",  # type: ignore[arg-type]
            description="x",
        )


def test_vaultnote_optional_type() -> None:
    note = VaultNote(name="A", path="A.md", tags=[])
    assert note.type is None


def test_note_metadata_modified_at_optional() -> None:
    metadata = NoteMetadata(modified_at=datetime(2024, 1, 1))
    assert metadata.modified_at is not None
