"""
    Legacy API for v1 version
"""
import json
from rich.console import Console
from ai.notes.llm import OllamaClient

console = Console()


class NoteGenerator:
    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    async def generate_deep_note(
        self,
        topic: str,
        existing_tags: list[str],
        existing_files: list[str],
    ) -> dict | None:

        # STEP 1: Metadata, tags, linking
        step1_prompt = f"""
You are an expert knowledge architect designing a high-quality personal
knowledge-base note for Obsidian.

Your task is NOT to write the note.
Your task is to design its information architecture and content plan.

TOPIC:
"{topic}"

EXISTING VAULT TAGS:
{json.dumps(existing_tags, ensure_ascii=False)}

EXISTING VAULT FILES:
{json.dumps(existing_files, ensure_ascii=False)}

The final note will be written in English.

## PRIMARY GOAL

Design a note that is:

- precise rather than verbose
- information-dense rather than generic
- useful for future retrieval
- connected to the existing knowledge graph
- structured so that every section adds meaningful information
- suitable for long-term storage in an Obsidian knowledge base

Do NOT optimize for article-like prose.
Optimize for durable knowledge.

## ANALYZE THE TOPIC

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
6. Which related concepts from the existing vault are genuinely relevant?

## OUTLINE

Create 3-7 sections.

The outline must be specific to the topic.

Do NOT use generic sections simply because they are common in articles.

Avoid outlines such as:

- Introduction
- Main part
- Key differences
- Conclusion

unless these sections have a specific informational purpose.

Every section must explain WHAT information it should contain.

Prefer:

"Механізм роботи — покроково пояснити lifecycle запиту,
взаємодію компонентів та точки, де може виникнути блокування"

over:

"Механізм роботи"

The outline should form a logical progression of understanding.

## EXISTING VAULT

Select tags from Existing Vault Tags when they are genuinely relevant.

Prefer existing tags over inventing new ones.

Select backlinks only when an existing file is semantically related
to the topic.

A file should NOT be selected merely because its name looks vaguely related.

The selected backlinks should ideally represent:

- prerequisite concepts
- broader concepts
- narrower concepts
- related concepts
- contrasting concepts

## DIAGRAM DECISION

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

Do NOT request a diagram when it would only decorate the note or
repeat information that is already clearer in text.

At this stage, decide only whether a diagram is useful.
Do NOT generate Mermaid code.

## RETURN FORMAT

Return STRICTLY valid JSON and nothing else:

{{
    "title": "Clear and descriptive title",
    "type": "reference",
    "folder": "Concepts",
    "tags": ["relevant", "tags"],
    "backlinks": ["RelevantExistingFile"],
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

Return ONLY valid JSON.
"""

        try:
            console.print(
                "  └─ [cyan]Етап 1:[/cyan] Plan writing and gathering metadata..."
            )

            raw_plan = await self.llm.query(
                step1_prompt,
                is_json=True,
                temperature=0.2,
            )

            plan_data = json.loads(raw_plan)

        except Exception as e:
            console.print(
                f"[bold red]Error during plan writing:[/bold red] {e}"
            )
            return None


        # STEP 2: Content Generation
        outline_items = []
        raw_outline = plan_data.get("outline", [])

        if isinstance(raw_outline, list):
            for item in raw_outline:
                if isinstance(item, dict):
                    title = item.get("title", "Title")
                    purpose = item.get("purpose", "")
                    raw_elements = item.get("elements", [])
                    
                    if isinstance(raw_elements, list):
                        elements_str = ", ".join(str(e) for e in raw_elements)
                    else:
                        elements_str = str(raw_elements)
                        
                    outline_items.append(f"- {title}: {purpose} (elements: {elements_str})")
                elif isinstance(item, str):
                    outline_items.append(f"- {item}")

        outline_str = "\n".join(outline_items) if outline_items else "Automatic structure"

        # Backlinks
        raw_backlinks = plan_data.get("backlinks", [])
        if isinstance(raw_backlinks, list):
            backlinks_str = ", ".join(f"[[{b}]]" for b in raw_backlinks if isinstance(b, str))
        else:
            backlinks_str = ""

        step2_prompt = f"""
You are an expert technical writer and knowledge-base architect.

Write a deep, information-dense Markdown note for an Obsidian knowledge base.

The final note MUST be written in English.

TOPIC:
"{topic}"

TITLE:
"{plan_data.get('title')}"

NOTE TYPE:
"{plan_data.get('type', 'reference')}"

OUTLINE:
{outline_str}

EXISTING VAULT FILES:
{json.dumps(existing_files, ensure_ascii=False)}

RELEVANT BACKLINKS:
{backlinks_str}

DIAGRAM PLAN:
{json.dumps(plan_data.get("diagram", {}), ensure_ascii=False)}

## PRIMARY OBJECTIVE

The goal is NOT to make the note as long as possible.

The goal is to maximize useful information per paragraph.

The result should feel like a durable knowledge-base reference,
not like a generic AI-generated article.

Every paragraph should introduce, explain, connect, compare or clarify
something useful.

Avoid filler.

## DEPTH

When explaining an important concept, prefer answering the relevant
questions below:

1. WHAT is it?
2. WHY does it exist?
3. HOW does it work?
4. WHAT does it depend on?
5. WHERE is it useful?
6. WHAT are its limitations?
7. WHAT alternatives exist?
8. WHEN should one approach be preferred over another?

Do not mechanically answer all eight questions for every concept.
Use only those that are relevant.

The important thing is to explain mechanisms and relationships,
not merely list terminology.

## CONCRETE INFORMATION

Prefer:

- precise definitions
- causal relationships
- mechanisms
- algorithms
- formulas
- concrete examples
- counterexamples
- edge cases
- limitations
- failure modes
- trade-offs
- implementation details
- comparisons
- practical implications

When appropriate, include:

- Markdown tables
- code examples
- pseudocode
- formulas
- numbered procedures
- bullet lists
- Mermaid diagrams

Do not add these elements merely for decoration.

## AVOID GENERIC AI WRITING

Do NOT use filler such as:

- "У цьому розділі ми розглянемо..."
- "Важливо зазначити, що..."
- "Це дуже важлива концепція..."
- "Як бачимо..."
- "Підсумовуючи..."
- "У сучасному світі..."
- "Це дозволяє нам краще зрозуміти..."

Start directly with useful information.

Do not repeat the same idea in multiple sections.

Do not artificially expand short ideas into long prose.

## TECHNICAL PRECISION

When the subject is technical, be precise.

If useful, provide:

- formulas
- algorithms
- complexity analysis
- data structures
- execution flow
- implementation details
- real code examples
- edge cases
- common mistakes

Code must be syntactically plausible and directly relevant.

Do not invent:

- benchmarks
- statistics
- citations
- experiments
- API behavior
- numerical values

If information is uncertain, explicitly qualify it instead of presenting
it as an established fact.

## OUTLINE

Follow the provided outline.

However, the outline is a semantic guide, not a rigid template.

You may:

- add a subsection when it improves understanding
- merge redundant ideas
- slightly reorder information when necessary

Do NOT create a section merely to satisfy the outline.

Each section must contain substantive information.

Use:

## Section

### Subsection

only when the additional hierarchy improves readability.

## WIKILINKS

Use Obsidian WikiLinks naturally inside the text.

Example:

[[Event Loop]]

Create a WikiLink only when the concept is genuinely related to the
statement.

Prefer linking concepts that represent:

- prerequisites
- broader concepts
- narrower concepts
- related concepts
- contrasting concepts
- concepts that deserve their own note

Use the existing vault files as the primary source of possible WikiLinks.

Do NOT insert WikiLinks randomly.

Do NOT append a list of WikiLinks at the end.

Do NOT force every provided file into the note.

A WikiLink should make sense if the reader clicks it.

## TABLES

Use Markdown tables when they make comparison or structured information
easier to understand.

Good use cases:

- technology comparison
- algorithm comparison
- properties
- trade-offs
- use cases
- limitations
- terminology

Do not create tables merely for visual variety.

## MERMAID

The diagram decision from the planning stage is:

{json.dumps(plan_data.get("diagram", {}), ensure_ascii=False)}

If "needed" is true, include a meaningful Mermaid diagram.

The diagram must represent real information from the note.

Choose the Mermaid structure that best matches the subject:

- flowchart for processes and decision flows
- sequenceDiagram for interactions over time
- mindmap for conceptual hierarchies
- graph/architecture-style diagram for component relationships

Do NOT create a decorative diagram.

Do NOT create a diagram that merely repeats a simple list.

If the planning stage says a diagram is not needed, do not force one.

## OBSIDIAN COMPATIBILITY

Use standard Markdown compatible with Obsidian.

Allowed:

- [[WikiLinks]]
- Markdown tables
- fenced code blocks
- Mermaid blocks
- bullet lists
- numbered lists
- blockquotes when useful

Do NOT include YAML frontmatter.

Metadata is handled by the application.

Do NOT generate the main "# Title" heading.

Start directly with:

## ...

## FINAL QUALITY CHECK

Before returning the note, internally verify:

- Does every section contain concrete information?
- Does each paragraph add something useful?
- Are important mechanisms explained rather than merely named?
- Are cause-and-effect relationships clear?
- Are examples concrete?
- Are limitations and trade-offs mentioned where relevant?
- Are WikiLinks semantically justified?
- Is the Mermaid diagram actually useful?
- Is there unnecessary repetition?
- Are uncertain claims appropriately qualified?
- Does the result feel like a permanent knowledge-base note rather than
  a conversational AI response?

Return ONLY raw Markdown.

Do not include commentary before or after the note.
Do not wrap the entire answer in a Markdown code block.
"""

        console.print(
            "  └─ [cyan]Етап 2:[/cyan] Content generation"
        )

        try:
            full_markdown = await self.llm.query(
                step2_prompt,
                is_json=False,
                temperature=0.4,
            )

            plan_data["content"] = full_markdown.strip()

            return plan_data

        except Exception as e:
            console.print(
                f"[bold red]Failed to generate content[/bold red] {e}"
            )
            return None

