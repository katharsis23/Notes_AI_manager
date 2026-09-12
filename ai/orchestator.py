"""
Global orchestrator.

Responsibility
--------------
Given a runtime ``ExecutionStrategy`` (note / whisper / whisper+note) and a set
of resolved workers, pick the right pipeline and run it. Dev-tools settings
are applied dynamically as decorators around the selected strategy, so a
disabled tool costs nothing at runtime.

Design notes
------------
* Strategy selection is a dict dispatch, not an if/elif ladder.
* Dev tools (benchmark / logging) are pure decorators.
* ``ai_quality_judgement`` is an *async decorator factory*, so ``_apply_dev_tools``
  is async and takes an injected ``ollama_client``.
* The orchestrator is config-agnostic: it never imports ``config``. Whatever the
  composition root (``note.py``) injects only needs to expose the flag attributes
  of :class:`DevToolsLike`.
* Strategy methods are named ``run_*`` to avoid clashing with the ``notes`` /
  ``whisper`` worker attributes.
"""

from typing import Any, Awaitable, Callable, Optional, Protocol

from dev_tools import ai_quality_judgement, benchmark, log_calls
from models.orchestrator import (
    ExecutionStrategy,
    NoteStrategy,
    StrategyKind,
    WhisperNoteStrategy,
    WhisperStrategy,
)

from ai.notes.llm import OllamaClient
from ai.notes.note_pipeline import NotePipeline
from ai.whisper.client import WhisperClient
from models.note_models import Source


class DevToolsLike(Protocol):
    """
    Structural contract for the injected dev-tools flags.

    The orchestrator does NOT import the config; whatever object ``note.py``
    injects just has to expose these attributes. This keeps the orchestrator
    config-agnostic and trivially testable with a stub.
    """

    enable_time_benchmark: bool
    enable_logging: bool
    enable_ai_judge: bool


class Orchestrator:
    def __init__(
        self,
        execution_strategy: ExecutionStrategy,
        dev_tools: DevToolsLike,
        # Judge backend (only required when enable_ai_judge is on).
        ollama_client: Optional[OllamaClient] = None,
        # Workers (optional -> only what the strategy needs).
            notes: Optional[NotePipeline] = None,
        whisper: Optional[WhisperClient] = None,
    ):
        self.execution_strategy = execution_strategy
        self.dev_tools = dev_tools
        self.ollama_client = ollama_client
        self.notes = notes
        self.whisper = whisper

        # Kind -> bound method name.
        self._dispatch: dict[StrategyKind, str] = {
            StrategyKind.NOTE: "run_notes",
            StrategyKind.WHISPER: "run_whisper",
            StrategyKind.WHISPER_NOTE: "run_whisper_and_notes",
        }

    # ------------------------------------------------------------------
    # Dev tools
    # ------------------------------------------------------------------

    async def _apply_dev_tools(
        self, func: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        """
        Wrap ``func`` with the decorators enabled in the config.

        Order (outermost first): logging -> benchmark -> ai_judge -> func.
        Logging is outermost so every entry/exit is captured; the AI judge is
        innermost so it observes the raw strategy result.
        """
        wrapped = func

        if self.dev_tools.enable_ai_judge:
            if self.ollama_client is None:
                raise RuntimeError(
                    "enable_ai_judge is on but no ollama_client was injected."
                )

            # ai_quality_judgement is an async decorator *factory*:
            # awaiting it yields the decorator, which we then apply.
            decorator = await ai_quality_judgement(self.ollama_client)
            wrapped = decorator(wrapped)

        if self.dev_tools.enable_time_benchmark:
            wrapped = benchmark(wrapped)

        if self.dev_tools.enable_logging:
            wrapped = log_calls(wrapped)

        return wrapped

    # ------------------------------------------------------------------
    # Entrypoint
    # ------------------------------------------------------------------

    async def run(self) -> Any:
        """
        Execute the configured strategy, applying dev tools.

        Single public entrypoint the CLI / callers should use.
        """
        strategy = self.execution_strategy

        method_name = self._dispatch.get(strategy.kind)
        if method_name is None:
            raise ValueError(f"Unsupported strategy: {strategy.kind!r}")

        method = getattr(self, method_name)
        wrapped = await self._apply_dev_tools(method)

        return await wrapped()

    # ------------------------------------------------------------------
    # Worker guards
    # ------------------------------------------------------------------

    def _require_notes(self) -> NotePipeline:
        if self.notes is None:
            raise RuntimeError(
                "NotePipeline is required for this strategy but was not provided."
            )
        return self.notes

    def _require_whisper(self) -> WhisperClient:
        if self.whisper is None:
            raise RuntimeError(
                "WhisperClient is required for this strategy but was not provided."
            )
        return self.whisper

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    async def run_notes(self) -> Any:
        strategy = self.execution_strategy
        assert isinstance(strategy, NoteStrategy)

        pipeline = self._require_notes()
        return await pipeline.generate_and_save(strategy.prompt)

    async def run_whisper(self) -> Any:
        strategy = self.execution_strategy
        assert isinstance(strategy, WhisperStrategy)

        client = self._require_whisper()
        return await client.transcribe(strategy.audio_path, language=strategy.language)

    async def run_whisper_and_notes(self) -> Any:
        strategy = self.execution_strategy
        assert isinstance(strategy, WhisperNoteStrategy)

        client = self._require_whisper()
        pipeline = self._require_notes()

        transcription = await client.transcribe(
            strategy.audio_path, language=strategy.language
        )

        source = Source(
            kind="transcript",
            text=transcription.text,
            language=transcription.additional_info.get("language"),
            instruction=strategy.prompt,
        )

        return await pipeline.generate_and_save(source=source)
