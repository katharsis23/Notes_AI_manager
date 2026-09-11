#!/usr/bin/env python3

import asyncio
import argparse

from rich.console import Console

from config.config import config
from vault.vault import VaultManager
from ai.notes.llm import OllamaClient
from ai.notes.note_pipeline import NotePipeline


console = Console()


async def main():
    parser = argparse.ArgumentParser(
        description="Obsidian Master Note Generator"
    )

    parser.add_argument(
        "topic",
        nargs="+",
        help="Topic or prompt for the note",
    )

    args = parser.parse_args()

    raw_topic = " ".join(args.topic).strip()

    if not raw_topic:
        console.print(
            "[bold red]Error: Empty prompt.[/bold red]"
        )
        return

    console.print(
        "[bold blue]Starting Obsidian Master...[/bold blue]"
    )

    console.print(
        f"Vault: [yellow]{config.notes.note_vault}[/yellow]"
    )

    console.print(
        f"Model: [yellow]{config.notes.model_name}[/yellow]"
    )

    # ----------------------------------------------------------
    # Infrastructure
    # ----------------------------------------------------------

    vault_manager = VaultManager(
        vault_path=config.notes.note_vault,
        auto_git=config.notes.auto_git,
    )

    # llm_client = OllamaClient(
    #     url=config.ollama_url,
    #     model_name=config.model_name,
    # )
    model_planner = config.notes.model_planner
    model_writer = config.notes.model_name
    model_validator = config.notes.model_validator

    llm_planner = OllamaClient(
        url = config.notes.ollama_url,
        model_name=model_planner
    )

    llm_writer = OllamaClient(
        url = config.notes.ollama_url,
        model_name=model_writer
    )

    llm_validator = OllamaClient(
        url = config.notes.ollama_url,
        model_name=model_validator
    )
    # ----------------------------------------------------------
    # Pipeline
    # ----------------------------------------------------------

    pipeline = NotePipeline(
        llm_validator=llm_validator,
        llm_planner=llm_planner,
        llm_writer=llm_writer,
        vault_manager=vault_manager,
        max_revisions=2,
    )

    # ----------------------------------------------------------
    # Generate + validate + save
    # ----------------------------------------------------------

    with console.status(
        f"[bold green]"
        f"Generating note for '{raw_topic}'..."
        f"[/bold green]"
    ):
        note_path = await pipeline.generate_and_save(
            raw_topic
        )

    if note_path:
        console.print(
            "\n[bold green]"
            f"✔ Note saved: {note_path}"
            "[/bold green]"
        )
    else:
        console.print(
            "\n[bold red]"
            "✘ Failed to save the note."
            "[/bold red]"
        )


if __name__ == "__main__":
    asyncio.run(main())
