"""Tests for :class:`ai.notes.note_writer.NoteWriter`."""

from __future__ import annotations

from ai.notes.note_writer import NoteWriter
from models.note_models import DiagramPlan, NotePlan, NoteSection, VaultContext

from .conftest import ErrorLLMClient, FakeLLMClient


async def test_generate_content_strips_whitespace(vault_context: VaultContext) -> None:
    plan = NotePlan(
        title="T",
        type="concept",
        folder="C",
        tags=[],
        backlinks=[],
        outline=[NoteSection("S", "p", [])],
        diagram=DiagramPlan(needed=False),
    )
    client = FakeLLMClient("  ## Section\n\nbody  ")
    writer = NoteWriter(llama_client=client)
    result = await writer.generate_content(plan, vault_context)
    assert result == "## Section\n\nbody"


async def test_generate_content_sends_non_json_prompt(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    client = FakeLLMClient("## x")
    writer = NoteWriter(llama_client=client)
    await writer.generate_content(note_plan, vault_context)
    assert client.calls[0]["is_json"] is False


async def test_generate_content_error_returns_none(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    writer = NoteWriter(llama_client=ErrorLLMClient())
    assert await writer.generate_content(note_plan, vault_context) is None


def test_format_outline(note_plan: NotePlan) -> None:
    text = NoteWriter._format_outline(note_plan)
    assert "1. Core mechanism" in text
    assert "Explain how the mechanism works" in text


def test_format_related_notes_only_selected(
    note_plan: NotePlan, vault_context: VaultContext
) -> None:
    text = NoteWriter._format_related_notes(note_plan, vault_context)
    assert "ExistingNote" in text
    assert "OtherNote" not in text  # not in plan.backlinks


def test_format_related_notes_none_selected(vault_context: VaultContext) -> None:
    plan = NotePlan("T", "c", "C", [], [], [], DiagramPlan(needed=False))
    text = NoteWriter._format_related_notes(plan, vault_context)
    assert "No specifically related" in text


def test_diagram_instruction_not_needed() -> None:
    plan = NotePlan("T", "c", "C", [], [], [], DiagramPlan(needed=False))
    text = NoteWriter._build_diagram_instruction(plan)
    assert "No diagram is required" in text


def test_diagram_instruction_needed() -> None:
    plan = NotePlan(
        "T", "c", "C", [], [], [], DiagramPlan(needed=True, type="flowchart")
    )
    text = NoteWriter._build_diagram_instruction(plan)
    assert "IS required" in text
    assert "flowchart" in text
    assert "```mermaid" in text
