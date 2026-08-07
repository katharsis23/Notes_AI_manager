#!/usr/bin/env python3
import asyncio
import argparse
from rich.console import Console
from config.config import config
from vault.vault import VaultManager
from ai.llm import OllamaClient
from ai.generator import NoteGenerator

console = Console()

async def main():
    parser = argparse.ArgumentParser(description="Obsidian Master Note Generator")
    parser.add_argument("topic", nargs="+", help="Topic or prompt for the note")
    args = parser.parse_args()

    raw_topic = " ".join(args.topic)

    console.print("[bold blue]Запуск Obsidian Master...[/bold blue]")
    console.print(f"Vault: [yellow]{config.note_vault}[/yellow]")
    console.print(f"Модель: [yellow]{config.model_name}[/yellow]")

    vault_manager = VaultManager(config.note_vault, config.auto_git)
    llm_client = OllamaClient(url=config.ollama_url, model_name=config.model_name)
    generator = NoteGenerator(llm_client)

    # 1. Скануємо індекси волу
    existing_tags, existing_files = vault_manager.get_existing_context()
    console.print(f"Знайдено всього тегів: {len(existing_tags)}, нотаток для перелінківки: {len(existing_files)}")

    # 2. Генеруємо матеріал
    with console.status(f"[bold green]Генерую розширену нотатку для '{raw_topic}'...[/bold green]"):
        note_data = await generator.generate_deep_note(raw_topic, existing_tags, existing_files)

    # 3. Зберігаємо нотатку
    if note_data:
        vault_manager.save_note(note_data)

if __name__ == "__main__":
    asyncio.run(main())