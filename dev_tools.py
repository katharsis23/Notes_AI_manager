"""
Dev tools to override, intercept and estimate data

Contracts
- Benchmarks
- Streaming
- Logging

Decorators
- Time evaluation
- Enable logging
- Toggle streaming

"""
import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

from ai.notes.llm import OllamaClient
from models.dev_models import QualityJudgement

logger = logging.getLogger(__name__)

# ========= Decorators =======
def benchmark(func: Callable) -> Callable:
    """Measure execution time without changing function semantics."""

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()

            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                logger.debug(
                    "%s took %.4f seconds",
                    func.__name__,
                    elapsed,
                )

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()

        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.debug(
                "%s took %.4f seconds",
                func.__name__,
                elapsed,
            )

    return sync_wrapper


def log_calls(func: Callable) -> Callable:
    """Log function entry, exit and failures."""

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.debug("Starting %s", func.__name__)

            try:
                result = await func(*args, **kwargs)
            except Exception:
                logger.exception(
                    "Error in %s",
                    func.__name__,
                )
                raise

            logger.debug("Finished %s", func.__name__)

            return result

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug("Starting %s", func.__name__)

        try:
            result = func(*args, **kwargs)
        except Exception:
            logger.exception(
                "Error in %s",
                func.__name__,
            )
            raise

        logger.debug("Finished %s", func.__name__)

        return result

    return sync_wrapper

async def ai_quality_judgement(ollama_client: OllamaClient) -> Callable:
    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                raw_result = await func(*args, **kwargs)
                if isinstance(raw_result, str):
                    judgement = await _judge(ollama_client, raw_result)
                    logger.debug("Quality judgement: %s", judgement)
                return raw_result
            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            raw_result = func(*args, **kwargs)
            if isinstance(raw_result, str):
                logger.debug("Sync func %s: skipping async AI judge", func.__name__)
            return raw_result
        return sync_wrapper

    return decorator


async def _judge(ollama_client: OllamaClient, raw_result: str) -> QualityJudgement:
    prompt = NOTE_JUDGE_PROMPT.format(raw_result=raw_result)
    response = await ollama_client.generate(prompt)  # або як у тебе
    return QualityJudgement.model_validate_json(response)






# TODO: Consider adding transcript or else
NOTE_JUDGE_PROMPT = """
You are a strict quality-control system for a personal knowledge base.

You evaluate an AI-generated note that was produced from a transcript.
Your job is to separate TWO independent questions:

  A. SOURCE / ASR PROBLEMS   -> did Whisper (the transcriber) introduce errors?
  B. NOTE / LLM PROBLEMS     -> did the note generator misinterpret, invent, or omit?

These are different failure surfaces. Never merge them.

==================================================
INPUT
==================================================

USER REQUEST / NOTE UNDER REVIEW:
{raw_result}

==================================================
A. SOURCE / ASR EVALUATION
==================================================

Decide whether the content suggests a transcription-level problem,
i.e. content that cannot reasonably be supported by the original audio.

You are NOT given the original audio. Therefore you MUST NOT assert
that Whisper hallucinated unless the available context gives strong
evidence. When in doubt, describe the uncertainty instead of
declaring a hallucination.

Signals of a possible ASR hallucination:
- repeated phrases unrelated to the surrounding topic;
- abrupt insertion of unrelated entities or topics;
- highly specific claims unsupported by surrounding context;
- continuation/completion that does not fit the source;
- duplicated or fabricated segments;
- loops, stutters, or "phantom" sentences.

If the transcript looks questionable but you cannot prove it,
report it as an uncertainty inside the issue description, and keep
the severity conservative (usually "minor", at most "major").

==================================================
B. NOTE / LLM EVALUATION
==================================================

Decide whether the note correctly represents the transcript and
answers the user's request.

Look for:
- factual errors introduced by the note generator;
- claims unsupported by the transcript;
- incorrect interpretation of the source;
- invented technical details;
- contradictions;
- incorrect terminology;
- missing important information;
- failure to answer the user's request;
- misleading causal relationships;
- incorrect code or formulas;
- grammar problems;
- malformed Markdown;
- broken or missing wikilinks;
- broken, misleading, or missing diagrams.

Additional useful information is NOT an error by itself.
Do not penalize reasonable background knowledge unless it is
presented as a source-derived fact when it is not supported by
the source.

==================================================
ERROR CLASSIFICATION
==================================================

Every issue MUST have exactly one type from this list:

"asr_hallucination"
    The problem originates from the source transcription
    (Whisper), not from the note generator.

"factual_error"
    The note contains factually incorrect information.

"contextual_error"
    The note incorrectly interprets the source or its context.

"user_request"
    The note fails to satisfy the user's request.

"missing_content"
    Important information from the source is missing.

"grammar"
    Actual language or grammar error.

"terminology"
    Incorrect or misleading terminology.

"structure"
    Significant structural problem in the note.

"wikilink"
    Broken, missing, or incorrect wikilink.

"markdown"
    Markdown formatting problem.

"diagram"
    Broken, misleading, or missing diagram.

==================================================
SEVERITY
==================================================

critical:
    Fundamentally incorrect, unusable, or seriously misleading.

major:
    Significant problem that materially reduces usefulness.

minor:
    Small issue that does not substantially affect usefulness.

Do not inflate severity. Do not downgrade real critical problems.

==================================================
SCORING
==================================================

Return a score in [0.0, 10.0] reflecting overall usefulness of the note.

9.0-10.0  Excellent. No meaningful problems.
8.0-8.9   Good. Minor corrections recommended.
6.0-7.9   Usable but meaningful corrections required.
4.0-5.9   Major revision required.
0.0-3.9   Fundamentally incorrect or unsuitable.

Do not reduce the score merely because several tiny issues exist.
Do not raise the score because issues are "probably the source's fault".

==================================================
VALID
==================================================

"valid": true ONLY when:
- there are no critical issues;
- there are no unresolved major issues;
- the note is sufficiently accurate and useful.

Minor issues alone should normally NOT invalidate the note.

==================================================
CRITICAL RULES
==================================================

1. Do not blame the note generator for an error already present in
   the transcript. Such an issue must be typed "asr_hallucination".

2. Do not blame Whisper for an error introduced by the note generator.
   Such an issue must use a non-ASR type.

3. When the origin of an error cannot be determined reliably:
   - do NOT use "asr_hallucination";
   - pick the most plausible non-ASR type;
   - state the uncertainty explicitly in the description.

4. Each issue is independent. Do not duplicate the same issue under
   multiple types.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON. No prose, no markdown fences, no commentary.

The JSON MUST conform to this schema:

{
  "valid": true,
  "score": 9.2,
  "issues": [
    {
      "severity": "minor",
      "type": "grammar",
      "description": "Short concrete description",
      "section": "Section name or null"
    }
  ],
  "recommendation": "Short recommendation"
}

Field rules:
- "valid": boolean.
- "score": number in [0.0, 10.0].
- "issues": array, possibly empty.
- each issue.severity: one of "critical" | "major" | "minor".
- each issue.type:     one of the types listed above.
- each issue.description: short, concrete, factual.
- each issue.section:  string, or null when not applicable.
- "recommendation": short, actionable.
"""
