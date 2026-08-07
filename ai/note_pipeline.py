from rich.console import Console

from ai.llm import OllamaClient
from vault.vault import VaultManager

from ai.note_planner import NotePlanner
from ai.note_writer import NoteWriter
from ai.note_validator import NoteValidator

from models import NotePlan, ValidationResult


console = Console()


class NotePipeline:
    """
    Orchestrates the complete note generation pipeline.

    Pipeline:

        User Prompt
             ↓
        Vault Context
             ↓
        NotePlanner
             ↓
        NotePlan
             ↓
        NoteWriter
             ↓
        Markdown
             ↓
        NoteValidator
             ↓
        ┌───────────────┐
        │               │
      valid          invalid
        │               │
        ▼               ▼
      Save          Revision
                        │
                        ▼
                     Writer
                        │
                        ▼
                   Validator
                        │
                        ▼
                      Save

    The pipeline itself does not implement:
    - LLM communication;
    - Vault indexing;
    - Markdown generation;
    - validation logic;
    - file persistence;
    - Git operations.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        vault_manager: VaultManager,
        max_revisions: int = 2,
    ):
        self.llm = llm_client
        self.vault = vault_manager

        self.planner = NotePlanner(
            llama_client=llm_client,
            vault_manager=vault_manager,
        )

        self.writer = NoteWriter(
            llama_client=llm_client,
        )

        self.validator = NoteValidator(
            llama_client=llm_client,
        )

        self.max_revisions = max_revisions

    async def generate(
        self,
        raw_text: str,
    ) -> dict | None:
        """
        Execute the complete note-generation pipeline.

        Args:
            raw_text:
                Original user request.

        Returns:
            Note data ready for VaultManager.save_note(),
            or None if generation failed.
        """

        if not raw_text or not raw_text.strip():
            console.print(
                "[bold red]Помилка:[/bold red] "
                "Порожній запит."
            )
            return None

        raw_text = raw_text.strip()

        console.print(
            "\n[bold cyan]══════════════════════════════════════[/bold cyan]"
        )
        console.print(
            "[bold cyan]       OBSIDIAN NOTE PIPELINE[/bold cyan]"
        )
        console.print(
            "[bold cyan]══════════════════════════════════════[/bold cyan]\n"
        )

        # ==========================================================
        # 1. CONTEXT
        # ==========================================================

        console.print(
            "[bold blue][1/5] Збір контексту Vault...[/bold blue]"
        )

        context = self.vault.get_existing_context_v2()

        if context is None:
            console.print(
                "[bold red]Не вдалося отримати контекст Vault.[/bold red]"
            )
            return None

        console.print(
            f"  └─ Нотаток: {len(context.notes)}"
        )
        console.print(
            f"  └─ Тегів: {len(context.tags)}"
        )

        # ==========================================================
        # 2. PLANNER
        # ==========================================================

        console.print(
            "\n[bold blue][2/5] Планування нотатки...[/bold blue]"
        )

        plan = await self.planner.generate_plan(
            raw_text=raw_text,
        )

        if plan is None:
            console.print(
                "[bold red]Planner не зміг створити план.[/bold red]"
            )
            return None

        console.print(
            f"  └─ Title: [bold]{plan.title}[/bold]"
        )
        console.print(
            f"  └─ Type: {plan.type}"
        )
        console.print(
            f"  └─ Sections: {len(plan.outline)}"
        )
        console.print(
            f"  └─ Backlinks: {len(plan.backlinks)}"
        )

        if plan.diagram.needed:
            console.print(
                f"  └─ Diagram: {plan.diagram.type}"
            )
        else:
            console.print(
                "  └─ Diagram: не потрібна"
            )

        # ==========================================================
        # 3. WRITER
        # ==========================================================

        console.print(
            "\n[bold blue][3/5] Генерація нотатки...[/bold blue]"
        )

        content = await self.writer.generate_content(
            plan=plan,
            context=context,
        )

        if not content:
            console.print(
                "[bold red]Writer не зміг згенерувати нотатку.[/bold red]"
            )
            return None

        console.print(
            f"  └─ Згенеровано символів: {len(content)}"
        )

        # ==========================================================
        # 4. VALIDATION + REVISION
        # ==========================================================

        console.print(
            "\n[bold blue][4/5] Валідація нотатки...[/bold blue]"
        )

        validation = await self.validator.validate(
            raw_text=raw_text,
            plan=plan,
            content=content,
            context=context,
        )

        if validation is None:
            console.print(
                "[bold red]Validator не зміг перевірити нотатку.[/bold red]"
            )
            return None

        revision_count = 0

        while (
            not validation.valid
            and revision_count < self.max_revisions
        ):
            revision_count += 1

            console.print(
                f"\n[yellow]⚠ Нотатка не пройшла валідацію "
                f"(спроба {revision_count}/{self.max_revisions}).[/yellow]"
            )

            self._print_validation_result(
                validation
            )

            console.print(
                "[cyan]→ Передаємо проблеми Writer для виправлення...[/cyan]"
            )

            content = await self._revise_content(
                raw_text=raw_text,
                plan=plan,
                content=content,
                validation=validation,
                context=context,
            )

            if not content:
                console.print(
                    "[bold red]Не вдалося виконати revision.[/bold red]"
                )
                return None

            console.print(
                "[cyan]→ Повторна валідація...[/cyan]"
            )

            validation = await self.validator.validate(
                raw_text=raw_text,
                plan=plan,
                content=content,
                context=context,
            )

            if validation is None:
                console.print(
                    "[bold red]Validator завершився з помилкою.[/bold red]"
                )
                return None

        # ==========================================================
        # VALIDATION RESULT
        # ==========================================================

        self._print_validation_result(
            validation
        )

        if not validation.valid:
            console.print(
                "\n[bold red]"
                "✘ Нотатка не пройшла валідацію після "
                f"{self.max_revisions} revision."
                "[/bold red]"
            )

            return None

        # ==========================================================
        # 5. PREPARE DATA FOR VAULT
        # ==========================================================

        console.print(
            "\n[bold blue][5/5] Підготовка до збереження...[/bold blue]"
        )

        note_data = self._build_note_data(
            plan=plan,
            content=content,
            validation=validation,
        )

        console.print(
            "[green]✔ Нотатка готова до збереження.[/green]"
        )

        return note_data

    async def generate_and_save(
        self,
        raw_text: str,
    ):
        """
        Generate, validate and save the note.

        This is a convenience method for CLI usage.
        """

        note_data = await self.generate(
            raw_text
        )

        if note_data is None:
            return None

        return self.vault.save_note(
            note_data
        )

    async def _revise_content(
        self,
        raw_text: str,
        plan: NotePlan,
        content: str,
        validation: ValidationResult,
        context,
    ) -> str | None:
        """
        Ask Writer to fix the problems found by Validator.

        We deliberately use a separate revision prompt instead of
        changing NoteWriter.generate_content().

        This keeps initial generation and correction conceptually
        separate.
        """

        issues = self._format_validation_issues(
            validation
        )

        prompt = f"""
You are revising an existing Obsidian knowledge-base note.

The note was generated according to a predefined plan and then
validated by a strict quality-control system.

Your task is to FIX ONLY the identified problems while preserving
correct existing content.

==================================================
ORIGINAL USER REQUEST
==================================================

{raw_text}

==================================================
NOTE PLAN
==================================================

Title:
{plan.title}

Type:
{plan.type}

Sections:

{self._format_plan_sections(plan)}

==================================================
CURRENT NOTE
==================================================

{content}

==================================================
VALIDATION ISSUES
==================================================

{issues}

==================================================
REVISION RULES
==================================================

1. Fix every critical and major issue.
2. Fix minor issues when they are straightforward.
3. Do not remove correct information merely to avoid validation.
4. Do not change the intended topic.
5. Do not redesign the note structure.
6. Do not invent unsupported facts.
7. Preserve useful WikiLinks.
8. Do not introduce WikiLinks to unknown notes.
9. Preserve Mermaid diagrams when they are correct.
10. Fix Mermaid diagrams if the validator identified a problem.
11. Keep the note in Ukrainian.
12. Keep the note information-dense.
13. Do not add YAML frontmatter.
14. Do not add a top-level "# Title" heading.

Return ONLY the corrected raw Markdown.

Start directly with:

## ...
"""

        try:
            return (
                await self.llm.query(
                    prompt,
                    is_json=False,
                    temperature=0.2,
                )
            ).strip()

        except Exception as exc:
            console.print(
                f"[bold red]Revision error:[/bold red] {exc}"
            )
            return None

    @staticmethod
    def _build_note_data(
        plan: NotePlan,
        content: str,
        validation: ValidationResult,
    ) -> dict:
        """
        Convert pipeline result into the structure expected
        by VaultManager.save_note().
        """

        return {
            "title": plan.title,
            "type": plan.type,
            "folder": plan.folder,
            "tags": plan.tags,
            "backlinks": plan.backlinks,
            "content": content,
            "validation": {
                "valid": validation.valid,
                "score": validation.score,
                "recommendation": validation.recommendation,
            },
        }

    @staticmethod
    def _format_validation_issues(
        validation: ValidationResult,
    ) -> str:
        if not validation.issues:
            return "No issues."

        result = []

        for index, issue in enumerate(
            validation.issues,
            start=1,
        ):
            section = (
                issue.section
                if issue.section
                else "document-wide"
            )

            result.append(
                f"""
{index}. [{issue.severity.upper()}]
Type: {issue.type}
Section: {section}
Problem: {issue.description}
""".strip()
            )

        return "\n\n".join(
            result
        )

    @staticmethod
    def _format_plan_sections(
        plan: NotePlan,
    ) -> str:
        result = []

        for index, section in enumerate(
            plan.outline,
            start=1,
        ):
            result.append(
                f"""
{index}. {section.title}

Purpose:
{section.purpose}

Elements:
{", ".join(section.elements)}
""".strip()
            )

        return "\n\n".join(
            result
        )

    @staticmethod
    def _print_validation_result(
        validation: ValidationResult,
    ):
        score = validation.score

        if validation.valid:
            console.print(
                f"[bold green]✔ Validation passed "
                f"({score:.1f}/10)[/bold green]"
            )
        else:
            console.print(
                f"[bold red]✘ Validation failed "
                f"({score:.1f}/10)[/bold red]"
            )

        if validation.issues:
            console.print(
                f"  └─ Issues: {len(validation.issues)}"
            )

            for issue in validation.issues:
                severity = issue.severity.upper()

                console.print(
                    f"     [{severity}] "
                    f"{issue.type}: "
                    f"{issue.description}"
                )

        if validation.recommendation:
            console.print(
                f"  └─ {validation.recommendation}"
            )
