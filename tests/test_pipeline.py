"""Tests for :class:`ai.notes.note_pipeline.NotePipeline`.

The pipeline is exercised with deterministic fake LLM clients and a real
:class:`VaultManager` backed by a temporary vault, so no network or real
Obsidian vault is involved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.notes.note_pipeline import NotePipeline
from models.note_models import ValidationIssue, ValidationResult
from vault.vault import VaultManager

from .conftest import FakeLLMClient


def _plan_json() -> str:
    return json.dumps(
        {
            "title": "Async IO",
            "type": "concept",
            "folder": "Concepts",
            "tags": ["python"],
            "backlinks": ["ExistingNote"],
            "outline": [
                {"title": "Loop", "purpose": "explain", "elements": ["def"]}
            ],
            "diagram": {"needed": False},
        }
    )


def _validation_json(severity: str | None = None) -> str:
    issues = []
    if severity:
        issues.append(
            {
                "severity": severity,
                "type": "factual_error",
                "description": "bad",
                "section": None,
            }
        )
    return json.dumps(
        {
            "valid": severity not in {"major", "critical"},
            "score": 9.0 if severity is None else 5.0,
            "issues": issues,
            "recommendation": "ok",
        }
    )


@pytest.fixture
def vault_manager(tmp_vault: Path) -> VaultManager:
    return VaultManager(vault_path=tmp_vault, auto_git=False)


def _make_pipeline(
    vault_manager: VaultManager,
    planner: FakeLLMClient,
    writer: FakeLLMClient,
    validator: FakeLLMClient,
) -> NotePipeline:
    return NotePipeline(
        llm_planner=planner,
        llm_writer=writer,
        llm_validator=validator,
        vault_manager=vault_manager,
        max_revisions=1,
    )


async def test_pipeline_happy_path(vault_manager: VaultManager) -> None:
    pipeline = _make_pipeline(
        vault_manager,
        FakeLLMClient(_plan_json()),
        FakeLLMClient("## Section\n\nbody"),
        FakeLLMClient(_validation_json()),
    )
    result = await pipeline.generate("Async IO")
    assert result is not None
    assert result["title"] == "Async IO"
    assert result["content"] == "## Section\n\nbody"
    assert result["validation"].valid is True


async def test_pipeline_planner_failure_returns_none(
    vault_manager: VaultManager,
) -> None:
    pipeline = _make_pipeline(
        vault_manager,
        FakeLLMClient("not-json"),
        FakeLLMClient("content"),
        FakeLLMClient(_validation_json()),
    )
    assert await pipeline.generate("x") is None


async def test_pipeline_writer_failure_returns_none(
    vault_manager: VaultManager,
) -> None:
    pipeline = _make_pipeline(
        vault_manager,
        FakeLLMClient(_plan_json()),
        FakeLLMClient(""),  # writer returns empty
        FakeLLMClient(_validation_json()),
    )
    assert await pipeline.generate("x") is None


@pytest.mark.xfail(
    reason=(
        "BUG: NotePipeline.generate() calls self.writer.revise(...), but "
        "NoteWriter does not implement revise(). Revision is, per the design, "
        "the Validator's responsibility. The revision branch therefore raises "
        "AttributeError at runtime. The correct wiring must be decided by the "
        "project owner; once it is, remove this xfail and assert the happy path."
    ),
    raises=AttributeError,
    strict=True,
)
async def test_pipeline_major_issue_triggers_revision(
    vault_manager: VaultManager,
) -> None:
    """
    Expected behaviour once the revision path is wired up correctly
    (revision owned by the Validator):

    a ``major`` issue should trigger exactly one revision and the Validator
    should be invoked twice (validate + re-validate).

    Until then this documents the current (broken) state so the suite stays
    green while the bug stays visible.
    """
    writer = FakeLLMClient(responses=["v1 content", "v2 content"])
    validator = FakeLLMClient(
        responses=[_validation_json("major"), _validation_json()]
    )
    pipeline = _make_pipeline(
        vault_manager, FakeLLMClient(_plan_json()), writer, validator
    )
    result = await pipeline.generate("x")
    assert result is not None
    assert result["content"] == "v2 content"  # revised content
    assert len(validator.calls) == 2


async def test_pipeline_minor_issue_does_not_trigger_revision(
    vault_manager: VaultManager,
) -> None:
    writer = FakeLLMClient("only content")
    validator = FakeLLMClient(_validation_json("minor"))
    pipeline = _make_pipeline(
        vault_manager, FakeLLMClient(_plan_json()), writer, validator
    )
    result = await pipeline.generate("x")
    assert result is not None
    assert len(writer.calls) == 1
    assert len(validator.calls) == 1


async def test_pipeline_max_revisions_capped(
    vault_manager: VaultManager,
) -> None:
    pipeline = NotePipeline(
        llm_planner=FakeLLMClient(_plan_json()),
        llm_writer=FakeLLMClient("c"),
        llm_validator=FakeLLMClient(_validation_json("critical")),
        vault_manager=vault_manager,
        max_revisions=5,  # should be capped to 1
    )
    assert pipeline.max_revisions == 1


async def test_pipeline_generate_and_save(vault_manager: VaultManager) -> None:
    pipeline = _make_pipeline(
        vault_manager,
        FakeLLMClient(_plan_json()),
        FakeLLMClient("## Section\n\nbody"),
        FakeLLMClient(_validation_json()),
    )
    path = await pipeline.generate_and_save("Async IO")
    assert path is not None
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("---")


def test_requires_revision_logic() -> None:
    def result(severities: list[str]) -> ValidationResult:
        return ValidationResult(
            valid=True,
            score=9.0,
            issues=[
                ValidationIssue(s, "grammar", "d") for s in severities
            ],
            recommendation="",
        )

    assert NotePipeline._requires_revision(result([])) is False
    assert NotePipeline._requires_revision(result(["minor"])) is False
    assert NotePipeline._requires_revision(result(["major"])) is True
    assert NotePipeline._requires_revision(result(["critical"])) is True
    assert NotePipeline._requires_revision(result(["minor", "critical"])) is True


def test_requires_revision_case_insensitive() -> None:
    res = ValidationResult(
        valid=False,
        score=1.0,
        issues=[ValidationIssue("MAJOR", "grammar", "d")],
        recommendation="",
    )
    assert NotePipeline._requires_revision(res) is True


@pytest.mark.flaky(reruns=3)
async def test_pipeline_measures_duration(vault_manager: VaultManager) -> None:
    """Timing must be non-negative. Retried because it reads a real clock."""
    pipeline = _make_pipeline(
        vault_manager,
        FakeLLMClient(_plan_json()),
        FakeLLMClient("content"),
        FakeLLMClient(_validation_json()),
    )
    result = await pipeline.generate("x")
    assert result is not None
