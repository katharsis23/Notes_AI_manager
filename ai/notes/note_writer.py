from ai.notes.llm import OllamaClient
from models.note_models import NotePlan, VaultContext


class NoteWriter:
    """
    Generates the actual Markdown content of an Obsidian note.

    Responsibilities:
    - Follow NotePlan created by NotePlanner.
    - Use VaultContext for contextual WikiLinks.
    - Generate detailed technical/conceptual content.
    - Generate Mermaid diagram when requested by the planner.

    NoteWriter does NOT:
    - choose tags;
    - choose backlinks;
    - choose folder;
    - modify the Vault;
    - save files;
    - validate the final note.
    """

    def __init__(
        self,
        llama_client: OllamaClient,
    ):
        self.llama_client = llama_client

    async def generate_content(
        self,
        plan: NotePlan,
        context: VaultContext,
    ) -> str | None:
        """
        Generate complete Markdown body according to NotePlan.
        """

        outline = self._format_outline(plan)

        related_notes = self._format_related_notes(
            plan,
            context,
        )

        diagram_instruction = self._build_diagram_instruction(plan)

        prompt = f"""
You are an expert technical writer and knowledge-base author
writing content for an Obsidian vault.

Your task is to WRITE the actual note content.

The information architecture has already been designed by another
component. You MUST follow the provided plan.

Do not redesign the structure.
Do not invent metadata.
Do not generate YAML frontmatter.

==================================================
NOTE
==================================================

Title:
{plan.title}

Type:
{plan.type}

==================================================
CONTENT PLAN
==================================================

{outline}

==================================================
RELATED VAULT NOTES
==================================================

{related_notes}

These notes belong to the existing Obsidian knowledge graph.

Use them only when they are genuinely relevant.

When referencing an existing note, use:

[[Exact Note Name]]

Do not invent WikiLinks to notes that are not listed above.

Do not add a separate "Related notes" section merely to list links.

WikiLinks must appear naturally inside the relevant explanations.

==================================================
DIAGRAM
==================================================

{diagram_instruction}

==================================================
WRITING REQUIREMENTS
==================================================

Write the note in well-formated md file.

The note should be:

- information-dense;
- technically precise;
- concrete;
- useful as a long-term knowledge-base reference;
- structured according to the provided plan;
- substantially more detailed than a short AI answer.

Avoid generic introductory prose.

Unless the phrase introduces actual useful information.

Every paragraph should communicate concrete information.

==================================================
DEPTH
==================================================

For each section:

- explain the actual concepts;
- define important terminology;
- explain mechanisms rather than merely naming them;
- explain relationships between concepts;
- include examples where they improve understanding;
- include edge cases where relevant;
- distinguish similar or easily confused concepts;
- use tables when comparing multiple entities;
- use bullet points for structured information;
- use code blocks when implementation details are relevant;
- use formulas when the topic requires mathematical reasoning.

Do not artificially make the note long.

Prefer high information density over verbosity.

==================================================
TECHNICAL ACCURACY
==================================================

Do not invent:

- APIs;
- functions;
- algorithms;
- specifications;
- historical facts;
- mathematical properties;
- implementation details.

If a claim depends on context, make the assumption explicit.

If there are multiple interpretations, distinguish them.

==================================================
MARKDOWN
==================================================

Use standard Markdown compatible with Obsidian.

Use:

- ## for main sections;
- ### for subsections;
- tables when appropriate;
- fenced code blocks;
- fenced Mermaid blocks when requested;
- [[WikiLinks]] for existing Vault concepts.

Do NOT generate a top-level "# {plan.title}" heading.

The VaultManager will add the H1 title.

==================================================
SECTION STRUCTURE
==================================================

Each planned section should become:

## Section title

followed by its actual content.

Do not skip planned sections.

Do not merge sections unless absolutely necessary.

Do not add generic "Introduction" or "Conclusion" sections
unless they are explicitly present in the plan.

==================================================
OUTPUT
==================================================

Return ONLY the raw Markdown body.

Do not return:

- JSON;
- YAML;
- frontmatter;
- Markdown fences around the entire document;
- explanations about your generation process;
- comments to the user.

Start directly with:

## ...
"""

        try:
            result = await self.llama_client.query(
                prompt,
                is_json=False,
                temperature=0.4,
            )

            return result.strip()

        except Exception as exc:
            print(f"Writer error: {exc}")
            return None

    @staticmethod
    def _format_outline(
        plan: NotePlan,
    ) -> str:
        """
        Convert NotePlan outline into a compact prompt representation.
        """

        sections = []

        for index, section in enumerate(
            plan.outline,
            start=1,
        ):
            elements = ", ".join(section.elements)

            sections.append(
                f"""
{index}. {section.title}

Purpose:
{section.purpose}

Required elements:
{elements}
""".strip()
            )

        return "\n\n".join(sections)

    @staticmethod
    def _format_related_notes(
        plan: NotePlan,
        context: VaultContext,
    ) -> str:
        """
        Prepare Vault notes for the Writer.

        Only notes selected by the Planner as backlinks are included
        in the main context, preventing the model from receiving the
        entire Vault.
        """

        selected = set(plan.backlinks)

        notes = [note for note in context.notes if note.name in selected]

        if not notes:
            return "No specifically related Vault notes were selected."

        result = []

        for note in notes:
            tags = ", ".join(note.tags)

            result.append(
                f"""
Name: {note.name}
Path: {note.path}
Type: {note.type or "unknown"}
Tags: {tags or "none"}
""".strip()
            )

        return "\n\n".join(result)

    @staticmethod
    def _build_diagram_instruction(
        plan: NotePlan,
    ) -> str:
        """
        Build diagram instructions based on Planner decision.
        """

        diagram = plan.diagram

        if not diagram.needed:
            return """
No diagram is required.

Do not generate a Mermaid diagram.
"""

        diagram_type = diagram.type or "flowchart"

        return f"""
A Mermaid diagram IS required.

Type:
{diagram_type}

Purpose:
{diagram.purpose or "Visualize the key relationships described in the note."}

Generate the diagram at the most appropriate location in the note.

Use a fenced Mermaid block:

```mermaid
...
````

The diagram must represent actual information from the note.

Do not create decorative diagrams.

Do not repeat the entire note inside the diagram.

The diagram should provide a useful visual representation of
relationships, structure, flow, sequence, hierarchy, or architecture.
"""
