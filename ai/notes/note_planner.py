import json

from ai.notes.llm import OllamaClient
from models.note_models import (
    DiagramPlan,
    NotePlan,
    NoteSection,
    Source,
    VaultContext,
    VaultNote,
)
from vault.vault import VaultManager


class NotePlanner:
    """
    Responsible for designing the information architecture of a note.

    Pipeline:

        user input
            ↓
        VaultContext
            ↓
        related notes selection
            ↓
        LLM planning
            ↓
        NotePlan
    """

    def __init__(
        self,
        llama_client: OllamaClient,
        vault_manager: VaultManager,
    ):
        self.llama_client = llama_client
        self.vault_manager = vault_manager

    async def generate_plan(
        self,
        raw_text: str,
        source: Source | None = None,
    ) -> NotePlan | None:
        """
        Generate a structured NotePlan from the user's topic or source.

        The planner does not generate note content.

        When ``source`` describes a transcript, the plan is derived FROM the
        source text (its structure is extracted), instead of inventing a plan
        about a bare topic.
        """
        if source is None:
            source = Source(kind="topic", text=raw_text)

        # ---------------------------------------------------------
        # 1. Get current Vault context
        # ---------------------------------------------------------

        vault_context = self.vault_manager.get_existing_context_v2()

        # ---------------------------------------------------------
        # 2. Select potentially related files
        # ---------------------------------------------------------

        # For a transcript the raw text is huge; use the topic/instruction
        # (or the first slice) for the cheap keyword pre-filter.
        related_query = source.instruction or raw_text
        if source.is_transcript and not source.instruction:
            related_query = raw_text[:400]

        related_files = self.get_related_files(
            related_query,
            vault_context,
        )

        # ---------------------------------------------------------
        # 2b. Build the source section for the prompt
        # ---------------------------------------------------------

        source_header, source_block = self._format_source(source)

        if source.is_transcript:
            outline_basis = (
                "The outline MUST be extracted from the SOURCE TRANSCRIPT: "
                "reflect its actual structure, arguments and content. Do not "
                "invent sections that the transcript does not support."
            )
        else:
            outline_basis = "The outline must be specific to the topic."

        # ---------------------------------------------------------
        # 3. Prepare compact context for LLM
        # ---------------------------------------------------------

        existing_tags = json.dumps(
            vault_context.tags,
            ensure_ascii=False,
        )

        existing_files = json.dumps(
            [
                {
                    "name": note.name,
                    "path": note.path,
                    "type": note.type,
                    "tags": note.tags,
                }
                for note in related_files
            ],
            ensure_ascii=False,
        )

        # ---------------------------------------------------------
        # 4. Build planner prompt
        # ---------------------------------------------------------

        step1_prompt = f"""
You are an expert knowledge architect designing a high-quality
personal knowledge-base note for Obsidian.

Your task is NOT to write the note.

Your task is to design its information architecture,
metadata, relationships and content plan.

==================================================
{source_header}
==================================================

{source_block}

==================================================
EXISTING VAULT TAGS
==================================================

{existing_tags}

==================================================
POTENTIALLY RELATED VAULT NOTES
==================================================

{existing_files}

The final note will be written in English.

==================================================
PRIMARY GOAL
==================================================

Design a note that is:

- precise rather than verbose
- information-dense rather than generic
- useful for future retrieval
- connected to the existing knowledge graph
- structured so that every section adds meaningful information
- suitable for long-term storage in an Obsidian knowledge base

Do NOT optimize for article-like prose.

Optimize for durable knowledge.

==================================================
ANALYZE THE TOPIC
==================================================

Determine what kind of knowledge the topic represents.

Possible types include:

- concept
- technical reference
- comparison
- process
- architecture
- algorithm
- philosophical idea
- practical guide
- historical/contextual explanation

Choose the type that best describes the topic.

Determine:

1. What must the reader understand first?
2. Which concepts are prerequisites?
3. Which mechanisms need to be explained?
4. Which concepts should be compared?
5. Which parts require examples, formulas, code, tables or diagrams?
6. Which related concepts from the existing Vault are genuinely relevant?

==================================================
OUTLINE
==================================================

Create 3-7 sections.

{outline_basis}

Do NOT use generic sections simply because they are
common in articles.

Avoid outlines such as:

- Introduction
- Main part
- Key differences
- Conclusion

unless these sections have a specific informational purpose.

Every section must explain WHAT information it should contain.

The outline should form a logical progression of understanding.

==================================================
TAGS
==================================================

Select tags from the existing Vault tags when they are
genuinely relevant.

Prefer existing tags over inventing new tags.

Do NOT select tags merely because they are vaguely related.

If no existing tag is appropriate, return an empty list.

==================================================
BACKLINKS
==================================================

Select backlinks only from the provided Vault notes.

A note should be selected only when it has a meaningful
semantic relationship with the new note.

Useful relationships include:

- prerequisite concept
- broader concept
- narrower concept
- related concept
- contrasting concept
- implementation dependency

Do NOT select a note merely because its filename contains
a similar word.

Never invent filenames.

Only return filenames that exist in the provided context.

==================================================
DIAGRAM DECISION
==================================================

A Mermaid diagram is OPTIONAL.

Do NOT assume every note needs a diagram.

A diagram is useful when the topic contains:

- architecture
- dependencies
- hierarchy
- workflow
- sequence of operations
- interaction between components
- conceptual relationships

Do NOT request a diagram when it would only decorate the note
or repeat information that is already clearer in text.

At this stage, decide only whether a diagram is useful.

Do NOT generate Mermaid code.

==================================================
FOLDER
==================================================

Choose a reasonable existing-style folder based on the topic.

Prefer simple categories such as:

- Concepts
- Tech
- Programming
- Math
- Philosophy
- Systems
- Projects
- References

Do not create deeply nested folder structures.

==================================================
RETURN FORMAT
==================================================

Return STRICTLY valid JSON and nothing else:

{{
    "title": "Clear and descriptive English title",
    "type": "concept",
    "folder": "Concepts",
    "tags": ["relevant", "existing", "tags"],
    "backlinks": ["ExistingNoteName"],
    "outline": [
        {{
            "title": "Specific section title",
            "purpose": "What this section must explain",
            "elements": [
                "definition",
                "mechanism",
                "example"
            ]
        }}
    ],
    "diagram": {{
        "needed": false,
        "type": null,
        "purpose": null
    }}
}}

If a diagram is useful:

"diagram": {{
    "needed": true,
    "type": "architecture",
    "purpose": "Explain the interaction between the main components"
}}

Allowed diagram types:

- flowchart
- sequence
- architecture
- hierarchy
- mindmap

Do not generate Mermaid syntax.

Do not generate note content.

Do not return Markdown.

Return ONLY valid JSON.
"""

        # ---------------------------------------------------------
        # 5. Ask LLM
        # ---------------------------------------------------------

        try:
            raw_result = await self.llama_client.query(
                step1_prompt,
                is_json=True,
                temperature=0.2,
            )

            data = json.loads(raw_result)

        except Exception as exc:
            print(f"Planner error: {exc}")
            return None

        # ---------------------------------------------------------
        # 6. Convert JSON → domain model
        # ---------------------------------------------------------

        try:
            outline = [
                NoteSection(
                    title=section["title"],
                    purpose=section["purpose"],
                    elements=section.get(
                        "elements",
                        [],
                    ),
                )
                for section in data.get(
                    "outline",
                    [],
                )
            ]

            diagram_data = data.get(
                "diagram",
                {},
            )

            diagram = DiagramPlan(
                needed=diagram_data.get(
                    "needed",
                    False,
                ),
                type=diagram_data.get(
                    "type",
                ),
                purpose=diagram_data.get(
                    "purpose",
                ),
            )

            return NotePlan(
                title=data["title"],
                type=data.get(
                    "type",
                    "reference",
                ),
                folder=data.get(
                    "folder",
                    "Concepts",
                ),
                tags=data.get(
                    "tags",
                    [],
                ),
                backlinks=data.get(
                    "backlinks",
                    [],
                ),
                outline=outline,
                diagram=diagram,
            )

        except (KeyError, TypeError, ValueError) as exc:
            print(f"Invalid NotePlan returned by LLM: {exc}")
            return None

    @staticmethod
    def _format_source(source: Source) -> tuple[str, str]:
        """
        Return the (header, block) pair that describes the source in the prompt.

        * topic      -> header "TOPIC", the topic string quoted.
        * transcript -> header "SOURCE TRANSCRIPT", the transcript verbatim,
                        plus an optional user instruction for steering.
        """
        if source.is_transcript:
            header = "SOURCE TRANSCRIPT"

            lines = [
                "The note MUST be derived from the following transcript.",
                "Treat it as the authoritative source material.",
                "Do NOT invent facts that are not supported by it.",
            ]
            if source.language:
                lines.append(f"Transcript language: {source.language}")
            if source.instruction:
                lines.append(
                    "Additional user instruction (steering only, does NOT "
                    f"replace the source): {source.instruction}"
                )

            block = "\n".join(lines) + "\n\n--- TRANSCRIPT START ---\n"
            block += source.text.strip()
            block += "\n--- TRANSCRIPT END ---"

            return header, block

        header = "TOPIC"
        block = f'"{source.text}"'
        return header, block

    def get_related_files(
        self,
        description: str,
        context: VaultContext,
        limit: int = 30,
    ) -> list[VaultNote]:
        """
        Cheap local pre-filter for potentially related notes.

        This is NOT semantic search.

        It only reduces the amount of Vault context sent to the LLM.
        A future vector/embedding search can replace this method
        without changing the planner pipeline.
        """

        query_tokens = self._tokenize(description)

        if not query_tokens:
            return []

        scored: list[tuple[int, VaultNote]] = []

        for note in context.notes:
            score = 0

            name_tokens = self._tokenize(note.name)

            path_tokens = self._tokenize(note.path)

            tag_tokens = {token for tag in note.tags for token in self._tokenize(tag)}

            # Filename match
            score += len(query_tokens & name_tokens) * 5

            # Path match
            score += len(query_tokens & path_tokens) * 2

            # Tag match
            score += len(query_tokens & tag_tokens) * 3

            if score > 0:
                scored.append(
                    (
                        score,
                        note,
                    )
                )

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [note for _, note in scored[:limit]]

    @staticmethod
    def _tokenize(
        text: str,
    ) -> set[str]:
        """
        Very small tokenizer used only for local pre-filtering.
        """

        return {
            token.lower()
            for token in __import__("re").findall(
                r"[a-zA-Zа-яА-ЯіїєґІЇЄҐ0-9]+",
                text,
            )
            if len(token) > 2
        }
