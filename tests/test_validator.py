"""Tests for :class:`ai.notes.note_validator.NoteValidator`."""

from __future__ import annotations

import json

from ai.notes.note_validator import NoteValidator
from models.note_models import NotePlan, VaultContext

from .conftest import ErrorLLMClient, FakeLLMClient


def _validation_json(**overrides) -> str:
    data = {
        "valid": True,
        "score": 9.1,
        "issues": [
            {
                "severity": "minor",
                "type": "grammar",
                "description": "typo",
                "section": "Intro",
            }
        ],
        "recommendation": "ok",
    }
    data.update(overrides)
    return json.dumps(data)


async def test_validate_success(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    validator = NoteValidator(llama_client=FakeLLMClient(_validation_json()))
    result = await validator.validate("x", note_plan, "content", vault_context)
    assert result is not None
    assert result.valid is True
    assert result.score == 9.1
    assert result.issues[0].type == "grammar"


async def test_validate_invalid_json_returns_none(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    validator = NoteValidator(llama_client=FakeLLMClient("oops"))
    assert await validator.validate("x", note_plan, "c", vault_context) is None


async def test_validate_llm_error_returns_none(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    validator = NoteValidator(llama_client=ErrorLLMClient())
    assert await validator.validate("x", note_plan, "c", vault_context) is None


async def test_validate_missing_score_defaults_zero(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    payload = json.dumps({"valid": False, "issues": []})
    validator = NoteValidator(llama_client=FakeLLMClient(payload))
    result = await validator.validate("x", note_plan, "c", vault_context)
    assert result is not None
    assert result.score == 0.0


def test_format_plan(note_plan: NotePlan) -> None:
    text = NoteValidator._format_plan(note_plan)
    assert "Test Note" in text
    assert "Core mechanism" in text
    assert "Required: no" in text  # diagram not needed


def test_format_vault_context_empty() -> None:
    from models.note_models import VaultContext

    text = NoteValidator._format_vault_context(VaultContext(notes=[], tags=[]))
    assert "no indexed notes" in text


def test_format_vault_context_with_notes(vault_context: VaultContext) -> None:
    text = NoteValidator._format_vault_context(vault_context)
    assert "ExistingNote" in text
    assert "OtherNote" in text
