"""Tests for :class:`ai.notes.note_planner.NotePlanner`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.notes.note_planner import NotePlanner
from models.note_models import VaultContext, VaultNote
from vault.vault import VaultManager

from .conftest import ErrorLLMClient, FakeLLMClient


@pytest.fixture
def vault_manager(tmp_vault: Path) -> VaultManager:
    return VaultManager(vault_path=tmp_vault, auto_git=False)


def _plan_json(**overrides) -> str:
    data = {
        "title": "Async IO",
        "type": "concept",
        "folder": "Concepts",
        "tags": ["python"],
        "backlinks": ["ExistingNote"],
        "outline": [
            {"title": "Event loop", "purpose": "explain loop", "elements": ["def"]}
        ],
        "diagram": {"needed": True, "type": "flowchart", "purpose": "flow"},
    }
    data.update(overrides)
    return json.dumps(data)


async def test_generate_plan_success(vault_manager: VaultManager) -> None:
    planner = NotePlanner(
        llama_client=FakeLLMClient(_plan_json()), vault_manager=vault_manager
    )
    plan = await planner.generate_plan("Async IO")
    assert plan is not None
    assert plan.title == "Async IO"
    assert plan.diagram.needed is True
    assert plan.outline[0].title == "Event loop"


async def test_generate_plan_invalid_json_returns_none(
    vault_manager: VaultManager,
) -> None:
    planner = NotePlanner(
        llama_client=FakeLLMClient("not json"), vault_manager=vault_manager
    )
    assert await planner.generate_plan("x") is None


async def test_generate_plan_missing_title_returns_none(
    vault_manager: VaultManager,
) -> None:
    payload = json.dumps({"outline": []})  # no title
    planner = NotePlanner(llama_client=FakeLLMClient(payload), vault_manager=vault_manager)
    assert await planner.generate_plan("x") is None


async def test_generate_plan_llm_error_returns_none(
    vault_manager: VaultManager,
) -> None:
    planner = NotePlanner(
        llama_client=ErrorLLMClient(), vault_manager=vault_manager
    )
    assert await planner.generate_plan("x") is None


async def test_generate_plan_applies_defaults(vault_manager: VaultManager) -> None:
    payload = json.dumps({"title": "T"})
    planner = NotePlanner(llama_client=FakeLLMClient(payload), vault_manager=vault_manager)
    plan = await planner.generate_plan("x")
    assert plan is not None
    assert plan.type == "reference"
    assert plan.folder == "Concepts"
    assert plan.tags == []
    assert plan.diagram.needed is False


def test_get_related_files_prefers_name_match() -> None:
    planner = NotePlanner(llama_client=FakeLLMClient(), vault_manager=None)  # type: ignore[arg-type]
    context = VaultContext(
        notes=[
            VaultNote(name="Python AsyncIO", path="C/Python AsyncIO.md", tags=[]),
            VaultNote(name="Cooking", path="C/Cooking.md", tags=[]),
        ],
        tags=[],
    )
    related = planner.get_related_files("Python AsyncIO patterns", context)
    assert related
    assert related[0].name == "Python AsyncIO"


def test_get_related_files_empty_query() -> None:
    planner = NotePlanner(llama_client=FakeLLMClient(), vault_manager=None)  # type: ignore[arg-type]
    context = VaultContext(notes=[VaultNote(name="X", path="X.md", tags=[])], tags=[])
    assert planner.get_related_files("!! !!", context) == []


def test_tokenize_filters_short_tokens() -> None:
    tokens = NotePlanner._tokenize("a bb ccc dddd")
    assert tokens == {"ccc", "dddd"}


def test_tokenize_lowercases() -> None:
    tokens = NotePlanner._tokenize("Python PYTHON")
    assert tokens == {"python"}
