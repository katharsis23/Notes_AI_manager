#!/usr/bin/env python3

import argparse
import asyncio

from rich.console import Console

from ai.notes.llm import OllamaClient
from ai.notes.note_pipeline import NotePipeline
from ai.orchestator import Orchestrator
from ai.whisper.client import WhisperClient
from config.config import config
from models.orchestrator import (
    NoteStrategy,
    WhisperNoteStrategy,
    WhisperStrategy,
)
from vault.vault import VaultManager

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Obsidian Master Note Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # 1) Note from a text prompt (default strategy)
  python note.py note "PostgreSQL B-Tree indexes"
  python note.py "PostgreSQL B-Tree indexes"

  # 2) Transcribe an audio file only
  python note.py whisper ./audio/lecture.mp3
  python note.py whisper ./audio/lecture.mp3 --language uk

  # 3) Transcribe audio, then generate a note from the transcript
  python note.py whisper-note ./audio/lecture.mp3
  python note.py whisper-note ./audio/lecture.mp3 --language uk
  python note.py whisper-note ./audio/lecture.mp3 --prompt "Focus on indexing"
  python note.py whisper-note ./audio/lecture.mp3 --save-transcript
""",
    )

    sub = parser.add_subparsers(dest="strategy")

    p_note = sub.add_parser("note", help="Generate a note from text (default)")
    p_note.add_argument("prompt", nargs="+", help="Topic or prompt for the note")

    p_whisper = sub.add_parser("whisper", help="Transcribe an audio file only")
    p_whisper.add_argument("audio", help="Path to the audio file")
    p_whisper.add_argument(
        "--language",
        default=None,
        help="Audio language ISO-639-1 (e.g. uk, en). Empty string = auto-detect.",
    )

    p_wn = sub.add_parser(
        "whisper-note", help="Transcribe audio then generate a note"
    )
    p_wn.add_argument("audio", help="Path to the audio file")
    p_wn.add_argument(
        "--prompt",
        default=None,
        help="Optional prompt to steer the note (defaults to the transcript)",
    )
    p_wn.add_argument(
        "--language",
        default=None,
        help="Audio language ISO-639-1 (e.g. uk, en). Empty string = auto-detect.",
    )

    return parser


def _parse_args() -> NoteStrategy | WhisperStrategy | WhisperNoteStrategy:
    """Build the runtime strategy from CLI args.

    Backwards-compatible: a bare ``python note.py "some topic"`` is treated as
    the ``note`` strategy.
    """
    parser = _build_parser()
    args = parser.parse_args()

    # No subcommand -> treat positional args as a note prompt.
    if args.strategy is None:
        raw = " ".join(parser.parse_known_args()[1]).strip()
        if not raw:
            parser.error("a topic or a subcommand is required")
        return NoteStrategy(prompt=raw)

    if args.strategy == "note":
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            parser.error("note prompt must not be empty")
        return NoteStrategy(prompt=prompt)

    if args.strategy == "whisper":
        return WhisperStrategy(audio_path=args.audio, language=args.language)

    if args.strategy == "whisper-note":
        return WhisperNoteStrategy(
            audio_path=args.audio,
            prompt=args.prompt,
            language=args.language,
        )

    parser.error(f"unknown strategy: {args.strategy}")


async def main():
    strategy = _parse_args()

    console.print("[bold blue]Starting Obsidian Master...[/bold blue]")
    console.print(f"Vault: [yellow]{config.notes.note_vault}[/yellow]")
    console.print(f"Model: [yellow]{config.notes.model_name}[/yellow]")
    console.print(f"Strategy: [yellow]{strategy.kind}[/yellow]")

    # ----------------------------------------------------------
    # Infrastructure
    # ----------------------------------------------------------

    vault_manager = VaultManager(
        vault_path=config.notes.note_vault,
        auto_git=config.notes.auto_git,
    )

    model_planner = config.notes.model_planner
    model_writer = config.notes.model_name
    model_validator = config.notes.model_validator

    llm_planner = OllamaClient(url=config.notes.ollama_url, model_name=model_planner)
    llm_writer = OllamaClient(url=config.notes.ollama_url, model_name=model_writer)
    llm_validator = OllamaClient(
        url=config.notes.ollama_url, model_name=model_validator
    )

    # ----------------------------------------------------------
    # Workers (only what the strategy needs is injected)
    # ----------------------------------------------------------

    pipeline = NotePipeline(
        llm_validator=llm_validator,
        llm_planner=llm_planner,
        llm_writer=llm_writer,
        vault_manager=vault_manager,
        max_revisions=2,
    )

    orchestrator = Orchestrator(
        execution_strategy=strategy,
        dev_tools=config.dev_tools,
        ollama_client=llm_writer,          # judge backend for enable_ai_judge
        notes=pipeline,                    # note / whisper-note strategies
        whisper=WhisperClient(),           # whisper / whisper-note strategies
    )

    # ----------------------------------------------------------
    # Run
    # ----------------------------------------------------------

    with console.status("[bold green]Running...[/bold green]"):
        result = await orchestrator.run()

    if result:
        console.print(f"\n[bold green]✔ Result: {result}[/bold green]")
    else:
        console.print("\n[bold red]✘ No result produced.[/bold red]")


if __name__ == "__main__":
    asyncio.run(main())
