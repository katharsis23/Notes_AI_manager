import time

from rich.console import Console

from ai.notes.note_planner import NotePlanner
from ai.notes.note_writer import NoteWriter
from ai.notes.note_validator import NoteValidator
from vault.vault import VaultManager

console = Console()


class NotePipeline:
    """
    Orchestrates the complete note generation pipeline:

        Vault Context
            ↓
        Note Planner
            ↓
        Note Writer
            ↓
        Note Validator
            ↓
        Optional Revision
            ↓
        Save to Vault
    """

    def __init__(
        self,
        llm_planner,
        llm_writer,
        llm_validator,
        vault_manager: VaultManager,
        max_revisions: int = 1,
    ):
        #self.llm = llm_cliet
        self.vault = vault_manager

        self.planner = NotePlanner(
            llama_client=llm_planner,
            vault_manager=vault_manager,
        )

        self.writer = NoteWriter(
            llama_client=llm_writer,
        )

        self.validator = NoteValidator(
            llama_client=llm_validator,
        )

        # Intentionally cap revisions at a single pass.
        self.max_revisions = min(max_revisions, 1)

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    @staticmethod
    def _log_duration(stage: str, started_at: float) -> float:
        elapsed = time.perf_counter() - started_at

        console.print(
            f"  └─ [dim]{stage}: {elapsed:.2f}s[/dim]"
        )

        return elapsed

    # ------------------------------------------------------------------
    # Validation policy
    # ------------------------------------------------------------------

    @staticmethod
    def _requires_revision(validation_result) -> bool:
        """
        Revision is triggered only if the Validator finds
        a major or critical issue.

        minor → record only
        major / critical → trigger revision
        """

        return any(
            issue.severity.lower() in {"major", "critical"}
            for issue in validation_result.issues
        )

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def generate(self, raw_text: str):
        pipeline_started = time.perf_counter()

        console.print(
            "\n[bold blue]━━━ Note Generation Pipeline ━━━[/bold blue]"
        )

        # --------------------------------------------------------------
        # 1. Vault context
        # --------------------------------------------------------------

        stage_started = time.perf_counter()

        console.print(
            "  ├─ [cyan]Fetching Vault context...[/cyan]"
        )

        context = self.vault.get_existing_context_v2()

        context_time = self._log_duration(
            "Vault context",
            stage_started,
        )

        console.print(
            f"  │  [dim]Notes: {len(context.notes)}, "
            f"tags: {len(context.tags)}[/dim]"
        )

        # --------------------------------------------------------------
        # 2. Planner
        # --------------------------------------------------------------

        stage_started = time.perf_counter()

        console.print(
            "  ├─ [cyan]Building note plan...[/cyan]"
        )

        plan = await self.planner.generate_plan(
            raw_text=raw_text,
        )

        self._log_duration(
            "Planner",
            stage_started,
        )

        if not plan:
            console.print(
                "[bold red]✘ Planner failed to generate a plan.[/bold red]"
            )
            return None

        # --------------------------------------------------------------
        # 3. Writer
        # --------------------------------------------------------------

        stage_started = time.perf_counter()

        console.print(
            "  ├─ [cyan]Generating note content...[/cyan]"
        )

        content = await self.writer.generate_content(
            plan=plan,
            context=context,
        )

        self._log_duration(
            "Writer",
            stage_started,
        )

        if not content:
            console.print(
                "[bold red]✘ Writer failed to generate content.[/bold red]"
            )
            return None

        # --------------------------------------------------------------
        # 4. Validation
        # --------------------------------------------------------------

        stage_started = time.perf_counter()

        console.print(
            "  ├─ [cyan]Validating note...[/cyan]"
        )

        validation = await self.validator.validate(
            raw_text=raw_text,
            plan=plan,
            content=content,
            context=context,
        )

        self._log_duration(
            "Validator",
            stage_started,
        )

        if validation is None:
            console.print(
                "[yellow]⚠ Validator returned no result.[/yellow]"
            )
        else:
            console.print(
                f"  │  [dim]Score: "
                f"{validation.score:.2f} | "
                f"Issues: {len(validation.issues)}[/dim]"
            )

        # --------------------------------------------------------------
        # 5. Optional revision
        # --------------------------------------------------------------

        revision_count = 0

        if (
            validation
            and self._requires_revision(validation)
            and revision_count < self.max_revisions
        ):
            revision_count += 1

            console.print(
                "\n  ├─ [yellow]"
                "Major issues detected → starting revision..."
                "[/yellow]"
            )

            stage_started = time.perf_counter()

            content = await self.writer.revise(
                plan=plan,
                content=content,
                validation=validation,
                context=context,
            )

            self._log_duration(
                "Revision",
                stage_started,
            )

            # ----------------------------------------------------------
            # 6. Re-validation
            # ----------------------------------------------------------

            stage_started = time.perf_counter()

            console.print(
                "  ├─ [cyan]Re-validating note...[/cyan]"
            )

            validation = await self.validator.validate(
                raw_text=raw_text,
                plan=plan,
                content=content,
                context=context,
            )

            self._log_duration(
                "Final validation",
                stage_started,
            )

        elif validation:
            console.print(
                "  ├─ [green]"
                "Revision not required."
                "[/green]"
            )

        # --------------------------------------------------------------
        # 7. Build result
        # --------------------------------------------------------------

        total_time = time.perf_counter() - pipeline_started

        console.print(
            "\n[bold blue]━━━ Pipeline Summary ━━━[/bold blue]"
        )

        console.print(
            f"  Total: [yellow]{total_time:.2f}s[/yellow]"
        )

        console.print(
            f"  Revision count: [yellow]{revision_count}[/yellow]"
        )

        if validation:
            console.print(
                f"  Validation score: "
                f"[yellow]{validation.score:.2f}[/yellow]"
            )

        return {
            "title": plan.title,
            "type": plan.type,
            "folder": plan.folder,
            "tags": plan.tags,
            "backlinks": plan.backlinks,
            "content": content,
            "validation": validation,
        }

    # ------------------------------------------------------------------
    # Generate + save
    # ------------------------------------------------------------------

    async def generate_and_save(self, raw_text: str):
        data = await self.generate(raw_text)

        if not data:
            return None

        stage_started = time.perf_counter()

        console.print(
            "\n  └─ [cyan]Saving note to Vault...[/cyan]"
        )

        note_path = self.vault.save_note(data)

        self._log_duration(
            "Save",
            stage_started,
        )

        return note_path