import json
from rich.console import Console
from llm import OllamaClient

console = Console()

class NoteGenerator:
    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    async def generate_deep_note(self, topic: str, existing_tags: list[str], existing_files: list[str]) -> dict | None:
        # ЕТАП 1: Метадані, вибір тегів, перелінківка та план розділів
        step1_prompt = f"""
            You are an expert knowledge architect for Obsidian.
            Analyze topic: "{topic}"

            Existing Vault Tags: {json.dumps(existing_tags)}
            Existing Vault Files for cross-linking: {json.dumps(existing_files)}

            Task: Create note metadata, select relevant tags/backlinks, and generate a brief section outline.

            Return STRICTLY JSON:
            {{
                "title": "Clear descriptive note title in Ukrainian",
                "type": "reference",
                "folder": "Concepts",
                "tags": ["ai-generated"],
                "backlinks": ["ExistingFileName1"],
                "outline": ["1. Вступ та основні визначення", "2. Порівняльний аналіз", "3. Ключові відмінності", "4. Підсумки"]
            }}
            """
        try:
            console.print("  └─ [cyan]Етап 1:[/cyan] Побудова плану та вибір метаданих...")
            raw_plan = await self.llm.query(step1_prompt, is_json=True, temperature=0.2)
            plan_data = json.loads(raw_plan)
        except Exception as e:
            console.print(f"[bold red]Помилка генерації плану (Етап 1):[/bold red] {e}")
            return None

        # ЕТАП 2: Генерація повного вмісту нотатки за ОДИН запит (у 3-4 рази швидше)
        outline_str = "\n".join([f"- {item}" for item in plan_data.get("outline", [])])
        backlinks_str = ", ".join([f"[[{b}]]" for b in plan_data.get("backlinks", [])])

        step2_prompt = f"""
Write a comprehensive, highly detailed technical note in Markdown for Obsidian in Ukrainian.

Topic: "{topic}"
Title: "{plan_data.get('title')}"
Outline to follow:
{outline_str}

Available context files for natural in-text cross-linking: {json.dumps(existing_files)}
Target backlinks to weave into paragraph text: {backlinks_str}

STRICT REQUIREMENTS:
- Start DIRECTLY with the first section heading "## 1. ...". DO NOT write the main "# Title" header at the top.
- Weave the target backlinks and context files organically INTO the sentences using [[WikiLink]] syntax where contextually relevant.
- DO NOT append a raw list of [[WikiLinks]] at the very end of the document.
- Use Markdown tables, code blocks, or bullet points where beneficial.
- Output ONLY raw Markdown without JSON or wrap syntax.
"""
        console.print("  └─ [cyan]Етап 2:[/cyan] Генерація повного тексту нотатки...")
        try:
            full_markdown = await self.llm.query(step2_prompt, is_json=False, temperature=0.4)
            plan_data["content"] = full_markdown.strip()
            return plan_data
        except Exception as e:
            console.print(f"[bold red]Помилка генерації вмісту (Етап 2):[/bold red] {e}")
            return None