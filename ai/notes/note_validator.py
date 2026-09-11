import json

from ai.notes.llm import OllamaClient
from models.note_models import (
    NotePlan,
    ValidationIssue,
    ValidationResult,
    VaultContext,
)


class NoteValidator:
    """
    Validates generated Obsidian notes.

    Responsibilities:
    - Check factual/contextual consistency.
    - Check grammatical and linguistic quality.
    - Check whether the note answers the user's original request.
    - Check whether the generated content follows NotePlan.
    - Check WikiLinks against the existing Vault context.
    - Return structured ValidationResult.

    NoteValidator does NOT:
    - rewrite the note;
    - modify the Vault;
    - modify NotePlan;
    - generate a new note.
    """

    def __init__(
        self,
        llama_client: OllamaClient,
    ):
        self.llama_client = llama_client

    async def validate(
        self,
        raw_text: str,
        plan: NotePlan,
        content: str,
        context: VaultContext,
    ) -> ValidationResult | None:
        """
        Validate generated note against:

        1. Original user request.
        2. Planned information architecture.
        3. Existing Vault context.
        4. language quality.
        """

        vault_context = self._format_vault_context(context)

        plan_context = self._format_plan(plan)

        prompt = f"""
You are a strict quality-control system for an Obsidian
personal knowledge base.

Your task is to VALIDATE an AI-generated note.

Do NOT rewrite the note.

Do NOT improve the note.

Do NOT generate a replacement.

Find concrete problems and return them as structured JSON.

==================================================
ORIGINAL USER REQUEST
==================================================

{raw_text}

==================================================
NOTE PLAN
==================================================

{plan_context}

==================================================
EXISTING VAULT CONTEXT
==================================================

{vault_context}

==================================================
GENERATED NOTE
==================================================

{content}

==================================================
VALIDATION DIMENSIONS
==================================================

Evaluate the note across four dimensions.

--------------------------------------------------
1. USER REQUEST COMPLIANCE
--------------------------------------------------

Determine whether the generated note actually answers
the user's original request.

Check:

- Is the main topic correctly understood?
- Are the requested concepts covered?
- Is the scope appropriate?
- Did the note drift into unrelated topics?
- Is important information from the user's request missing?
- Does the content match the intended purpose of the note?

Do not penalize the note merely because it contains
useful additional information.

Only report meaningful deviations.

--------------------------------------------------
2. FACTUAL AND CONTEXTUAL ACCURACY
--------------------------------------------------

Look for:

- factual inaccuracies;
- contradictory statements;
- technically incorrect explanations;
- unsupported claims presented as facts;
- incorrect terminology;
- incorrect formulas;
- incorrect code;
- incorrect causal relationships;
- contradictions with the provided Vault context.

Be especially careful with technical topics.

Do NOT report something as factually incorrect merely because
you personally prefer another explanation.

Only report an issue when there is a strong reason to believe
the statement is incorrect, misleading, contradictory,
or insufficiently qualified.

If a statement cannot be verified from the provided context,
do NOT automatically mark it as false.

Instead use an appropriate severity and explain that
the claim requires verification when necessary.

--------------------------------------------------
3. LANGUAGE AND GRAMMAR
--------------------------------------------------

The note should be written in natural English.

Check for:

- incorrect word forms;
- unnatural constructions;
- Russianisms;
- inconsistent terminology;
- unnecessary repetition;
- malformed Markdown caused by language generation.

Do NOT report stylistic preferences as errors.

Focus on actual language problems.

--------------------------------------------------
4. STRUCTURE AND PLAN COMPLIANCE
--------------------------------------------------

Check whether the generated note follows the NotePlan.

Verify:

- all planned sections are present;
- sections actually fulfil their stated purpose;
- required elements are covered;
- requested examples/tables/code are present when appropriate;
- diagram is present when the plan requires one;
- diagram is NOT present when the plan explicitly says it is unnecessary;
- the note does not introduce major structural drift.

Do not require an element merely because it was listed
as an optional possibility.

==================================================
WIKILINK VALIDATION
==================================================

Every WikiLink in the generated note should refer to an
existing Vault note.

If the note contains:

[[Some Note]]

and "Some Note" does not exist in the provided Vault context,
report it as a contextual/linking issue.

Do not require every possible related note to be linked.

Only validate links that the Writer actually generated.

==================================================
SEVERITY
==================================================

Use exactly one of:

"critical"
"major"
"minor"

Definitions:

critical:
The note is fundamentally wrong, answers a different question,
or contains a serious factual/technical error that makes the
note unsafe or unusable.

major:
A significant factual, structural, contextual, or requirement
problem that materially reduces the usefulness of the note.

minor:
A small grammar, wording, formatting, terminology, or
non-critical completeness issue.

Do not inflate severity.

==================================================
SCORING
==================================================

Return a score from 0.0 to 10.0.

Suggested interpretation:

9.0 - 10.0
Excellent. No meaningful problems.

8.0 - 8.9
Good. Minor corrections recommended.

6.0 - 7.9
Usable but requires meaningful corrections.

4.0 - 5.9
Major revision required.

0.0 - 3.9
Fundamentally incorrect or unsuitable.

The score should reflect the overall usefulness of the note,
not the number of issues alone.

A note with several tiny grammar mistakes may still score 9.

A note with one serious technical error may score much lower.

==================================================
VALID FIELD
==================================================

"valid" should be true only when the note is sufficiently
correct and useful to be saved into the knowledge base.

Use:

true:
No critical issues and no unresolved major issues.

false:
At least one critical issue or a major issue that materially
affects correctness, usefulness, or user-request compliance.

Minor issues alone should normally not make the note invalid.

==================================================
RECOMMENDATION
==================================================

Provide a short recommendation.

Examples:

"Нотатка готова до збереження."

"Потрібно виправити декілька граматичних помилок."

"Потрібно виправити технічне твердження щодо lifecycle запиту."

"Нотатка не повністю відповідає початковому запиту."

==================================================
RETURN FORMAT
==================================================

Return STRICTLY valid JSON.

Use exactly this structure:

{{
    "valid": true,
    "score": 9.2,
    "issues": [
        {{
            "severity": "minor",
            "type": "grammar",
            "description": "Конкретний опис проблеми",
            "section": "Назва секції"
        }}
    ],
    "recommendation": "Нотатка готова до збереження."
}}

Allowed issue types:

- factual_error
- contextual_error
- user_request
- grammar
- terminology
- structure
- missing_content
- wikilink
- markdown
- diagram

If an issue applies to the whole document,
set "section" to null.

Every issue must describe a concrete problem.

Do not create vague issues such as:

"Текст можна покращити."

"Потрібно більше деталей."

"Стиль можна зробити кращим."

Return ONLY JSON.
"""

        try:
            raw_result = await self.llama_client.query(
                prompt,
                is_json=True,
                temperature=0.1,
            )

            data = json.loads(raw_result)

        except Exception as exc:
            print(f"Validator error: {exc}")
            return None

        try:
            issues = [
                ValidationIssue(
                    severity=issue["severity"],
                    type=issue["type"],
                    description=issue["description"],
                    section=issue.get("section"),
                )
                for issue in data.get(
                    "issues",
                    [],
                )
            ]

            return ValidationResult(
                valid=bool(
                    data.get(
                        "valid",
                        False,
                    )
                ),
                score=float(
                    data.get(
                        "score",
                        0.0,
                    )
                ),
                issues=issues,
                recommendation=data.get(
                    "recommendation",
                    "",
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            print(f"Invalid ValidationResult returned by LLM: {exc}")
            return None

    @staticmethod
    def _format_plan(
        plan: NotePlan,
    ) -> str:
        """
        Convert NotePlan into compact validation context.
        """

        sections = []

        for index, section in enumerate(
            plan.outline,
            start=1,
        ):
            sections.append(
                f"""
{index}. {section.title}

Purpose:
{section.purpose}

Required elements:
{", ".join(section.elements)}
""".strip()
            )

        diagram = plan.diagram

        diagram_info = (
            f"Required: {'yes' if diagram.needed else 'no'}\n"
            f"Type: {diagram.type or 'none'}\n"
            f"Purpose: {diagram.purpose or 'none'}"
        )

        return f"""
Title:
{plan.title}

Type:
{plan.type}

Tags:
{", ".join(plan.tags)}

Planned backlinks:
{", ".join(plan.backlinks) or "none"}

Sections:

{chr(10).join(sections)}

Diagram:

{diagram_info}
""".strip()

    @staticmethod
    def _format_vault_context(
        context: VaultContext,
    ) -> str:
        """
        Format only the information needed to validate
        contextual relationships and WikiLinks.
        """

        if not context.notes:
            return "Vault contains no indexed notes."

        notes = []

        for note in context.notes:
            notes.append(
                f"""
Name: {note.name}
Path: {note.path}
Type: {note.type or "unknown"}
Tags: {", ".join(note.tags) or "none"}
""".strip()
            )

        return "\n\n".join(notes)
