# Obsidian Master AI CLI

**Obsidian Master** is a local CLI tool for generating structured, information-dense technical and conceptual notes for [Obsidian](https://obsidian.md/).

The project uses local Large Language Models through **Ollama** and integrates the generated notes directly into an existing Obsidian Vault.

The main goal is not simply to generate text, but to build a small **AI-assisted knowledge management system** that understands the existing Vault, creates connections between notes, validates generated content, and stores the result using consistent Obsidian metadata.

---

## Features

- Local LLM inference through Ollama

- Structured note planning before generation

- Dedicated note writer

- Validation of generated notes

- Automatic revision for serious validation errors

- Obsidian `[[WikiLinks]]` integration

- Reuse of existing Vault tags

- Existing Vault context for planning and cross-linking

- Optional Mermaid diagrams

- Per-stage pipeline timing

- Automatic Markdown + YAML frontmatter generation

- Automatic folder placement

- Optional Git commit and push

- Local Vault indexing layer

- Separation between AI generation, Vault I/O and infrastructure

---

# Environment Requirements

- **OS:** Linux / macOS

- **Python:** 3.14+

- **Ollama:** Locally running Ollama server

- **Git:** Optional, required only for automatic version control

- **Obsidian:** Recommended for viewing and managing the generated Vault

Default Ollama endpoint:

```text
http://localhost:11434
```

The default model is currently:

```text
qwen2.5:14b
```

The model can be changed during installation/configuration.

---

# Installation

The project provides an interactive installation script.

## 1. Prepare the repository

```bash
git clone <your-repo-url> ~/note
cd ~/note
```

## 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer:

1. Creates a Python virtual environment.

2. Installs Python dependencies.

3. Checks the local Ollama installation.

4. Lists available Ollama models.

5. Asks for the Ollama model.

6. Asks for the Obsidian Vault path.

7. Configures optional Git integration.

8. Creates the application configuration.

9. Registers the `note` command for Fish, Bash or Zsh.

## 3. Reload your shell

For Bash:

```bash
source ~/.bashrc
```

For Zsh:

```bash
source ~/.zshrc
```

Fish:

```bash
source ~/.config/fish/functions/note.fish
```

---

# Usage

The primary interface is the `note` CLI command.

### Conceptual note

```bash
note "Nihilism, existentialism, absurdism. Differences and common traits"
```

### Technical note

```bash
note "PostgreSQL Query Optimization and B-Tree Indexes"
```

The command accepts the user's raw prompt and passes it through the complete generation pipeline.

---

# Architecture

The project follows a lightweight **layered architecture** with explicit separation of responsibilities.

```text
                         ┌──────────────────┐
                         │      User        │
                         │   CLI command    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     note.py      │
                         │   CLI / entry    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  NotePipeline    │
                         │   Orchestrator   │
                         └───────┬──────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
       ┌────────────┐     ┌────────────┐     ┌────────────┐
       │   Vault    │     │ NotePlanner│     │    LLM     │
       │  Context   │     │            │     │   Client   │
       └─────┬──────┘     └─────┬──────┘     └─────┬──────┘
             │                  │                  │
             ▼                  ▼                  │
       VaultIndexer       NotePlan                │
             │                  │                  │
             │                  ▼                  │
             │           ┌────────────┐            │
             │           │ NoteWriter │◄───────────┘
             │           └─────┬──────┘
             │                 │
             │                 ▼
             │           Generated Markdown
             │                 │
             │                 ▼
             │          ┌──────────────┐
             └─────────►│ NoteValidator│
                        └──────┬───────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
               minor issues        major/critical
                    │                     │
                    │                     ▼
                    │                Revision
                    │                     │
                    │                     ▼
                    │                Validation
                    │                     │
                    └──────────┬──────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ VaultManager │
                        │ Save Note    │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ GitClient    │
                        └──────────────┘
```

---

# Project Structure

```text
.
├── ai/
│   ├── generator.py
│   ├── llm.py
│   ├── note_pipeline.py
│   ├── note_planner.py
│   ├── note_validator.py
│   └── note_writer.py
│
├── config/
│   ├── config.json
│   └── config.py
│
├── vault/
│   ├── vault.py
│   └── vault_indexer.py
│
├── git_client.py
├── install.sh
├── models.py
├── note.py
├── requirements.txt
├── README.md
└── .gitignore
```

The `__pycache__` and `venv` directories are development/runtime artifacts and are not part of the application architecture.

---

# Components

## `note.py`

The CLI entry point.

Responsibilities:

- Parse the user's command-line input.

- Load application configuration.

- Initialize infrastructure components.

- Start the `NotePipeline`.

- Display progress and results.

It intentionally contains very little business logic.

The CLI should not know how notes are planned, generated or validated.

---

## `ai/llm.py`

Low-level abstraction over Ollama.

Responsibilities:

- HTTP communication with Ollama.

- Model selection.

- Context window configuration.

- Temperature configuration.

- JSON responses.

- Raw Markdown responses.

- Timeout handling.

The rest of the application should not need to know how Ollama's HTTP API works.

This creates a simple dependency boundary:

```text
AI components
      │
      ▼
 OllamaClient
      │
      ▼
   Ollama API
```

This also makes it possible to replace Ollama later without rewriting the Planner, Writer or Validator.

---

# AI Pipeline

## `ai/note_pipeline.py`

The central orchestration layer.

The Pipeline does **not** generate content itself.

Its responsibility is to coordinate the other components:

```text
Context
   ↓
Planner
   ↓
Writer
   ↓
Validator
   ↓
Revision if necessary
   ↓
Save
```

It also owns pipeline-level concerns such as:

- execution order

- timing

- revision policy

- validation flow

- error handling

- final result assembly

This prevents `note.py` from becoming a large procedural script.

---

# `ai/note_planner.py`

The Planner is responsible for **information architecture**, not prose generation.

Input:

```text
User prompt
+
Vault context
```

Output:

```text
NotePlan
```

The planner determines:

- title

- note type

- folder

- tags

- relevant backlinks

- section structure

- section purpose

- required elements

- whether a diagram is useful

Example:

```text
User:
"PostgreSQL B-Tree indexes"

        ↓

Planner

        ↓

NotePlan
├── title
├── type
├── folder
├── tags
├── backlinks
├── outline
└── diagram decision
```

### Why separate planning from writing?

The LLM is asked to solve two different problems:

1. **What should the note contain?**

2. **How should that information be written?**

Separating them makes the second stage much more constrained and predictable.

It also allows the Planner to reason about the existing knowledge graph before generating prose.

---

# `ai/note_writer.py`

The Writer converts a `NotePlan` into actual Markdown.

Input:

```text
NotePlan
+
VaultContext
+
User prompt
```

Output:

```text
Markdown
```

The Writer is responsible for:

- detailed explanations

- examples

- tables

- code

- formulas

- Mermaid diagrams when requested by the plan

- contextual `[[WikiLinks]]`

- Markdown structure

The Writer does **not** decide the overall architecture of the note.

That decision belongs to the Planner.

---

# `ai/note_validator.py`

The Validator evaluates the generated note before it is stored.

The current validation goals are:

### 1. Contextual / factual consistency

Check whether the generated note contains contradictions or inaccuracies relative to the available Vault context.

### 2. User prompt compliance

Check whether the generated note actually answers the original request.

### 3. Content quality

Check whether important planned sections and required information are actually present.

Grammar and spelling are intentionally **not currently part of the LLM validation stage**.

A separate grammar-oriented mechanism can be added later.

The Validator returns:

```text
ValidationResult
├── valid
├── score
├── issues
└── recommendation
```

Each issue contains:

```text
severity
type
description
section
```

---

# Revision Policy

The system does not automatically regenerate every imperfect note.

Validation issues are classified by severity:

```text
minor
major
critical
```

Current policy:

```text
minor
  ↓
record issue
  ↓
continue

major / critical
  ↓
revision
  ↓
validation again
```

The number of automatic revisions is intentionally limited to **one**.

This prevents:

```text
Validator
   ↓
Revision
   ↓
Validator
   ↓
Revision
   ↓
...
```

from becoming an expensive generation loop.

The philosophy is:

> A generated note does not need to be perfect to be useful, but serious factual or structural problems should not be silently persisted.

---

# Vault Layer

## `vault/vault.py`

`VaultManager` is responsible for interaction with the physical Obsidian Vault.

Responsibilities:

- retrieving Vault context

- delegating indexing

- creating note directories

- generating YAML frontmatter

- saving Markdown files

- normalizing tags

- formatting backlinks

- integrating Git

The Vault layer should not contain LLM logic.

---

# `vault/vault_indexer.py`

The VaultIndexer maintains a searchable representation of the Markdown files inside the Vault.

The goal is to avoid repeatedly performing expensive full filesystem scans whenever the AI needs context.

The indexed model is conceptually:

```text
notes
────────────────────────
id
name
path
folder
type
modified_at
hash
content


tags
────────────────────────
id
name


note_tags
────────────────────────
note_id
tag_id


note_links
────────────────────────
source_note_id
target_note_id
```

This creates a lightweight local knowledge graph:

```text
Note A
 ├── tag → Python
 ├── tag → AsyncIO
 └── link → Note B

Note B
 ├── tag → Python
 └── link → Note C
```

---

# SQLite Index

The Vault index is designed around SQLite rather than making Obsidian's `.base` files a dependency of the generation engine.

This is an intentional architectural decision.

Obsidian Base is useful as a **presentation and querying mechanism inside Obsidian**, but it is not treated as the application's persistence API.

The application needs a deterministic and programmatically accessible representation of:

- notes

- metadata

- tags

- relationships

- content

- modification state

SQLite provides that directly.

---

# Why SQLite?

A simple filesystem scan works well for a small Vault.

However, as the Vault grows, repeatedly doing:

```text
walk filesystem
    ↓
open every Markdown file
    ↓
parse YAML
    ↓
extract tags
    ↓
extract links
```

becomes increasingly expensive.

The index allows the application to query:

```text
"Give me notes related to Python"

"Give me all tags"

"Which notes link to X?"

"Which notes have these tags?"

"Which files changed?"
```

without reparsing the entire Vault every time.

---

# Index Synchronization

The index should be treated as a **derived cache**, not the source of truth.

The Markdown files inside the Obsidian Vault remain authoritative.

Conceptually:

```text
Obsidian Markdown files
        │
        │ scan / synchronize
        ▼
   SQLite Index
        │
        │ query
        ▼
   AI Pipeline
```

If the SQLite database becomes corrupted or outdated, it should be possible to rebuild it from the Vault.

This is an important property: **the database must never become a single point of failure for the knowledge base.**

---

# Data Models

`models.py` contains the application's domain models.

Important models include:

### `NotePlan`

Represents the Planner's output.

```text
NotePlan
├── title
├── type
├── folder
├── tags
├── backlinks
├── outline
└── diagram
```

### `VaultNote`

Represents a note retrieved from the Vault.

### `VaultContext`

Represents the context supplied to the AI pipeline.

### `ValidationResult`

Represents the Validator's assessment.

### `ValidationIssue`

Represents an individual validation problem.

The models intentionally sit outside the AI and Vault implementations.

This keeps data structures independent from infrastructure.

---

# Configuration

## `config/config.py`

Configuration is loaded from:

```text
~/.config/obsidian-ai-note/config.json
```

Example:

```json
{
  "model_name": "qwen2.5:14b",
  "ollama_url": "http://localhost:11434/api/generate",
  "note_vault": "/home/user/Documents/obsidian/conspects",
  "auto_git": true
}
```

Configuration controls:

- Ollama model

- Ollama endpoint

- Vault location

- Git integration

---

# Git Integration

## `git_client.py`

Git integration is intentionally kept outside the Vault and AI layers.

Its responsibilities are limited to version control operations:

```text
save note
   ↓
git add
   ↓
git commit
   ↓
git push
```

Git is considered an infrastructure concern rather than part of note generation.

This makes Git optional.

The application can therefore be used with:

```text
auto_git = false
```

without changing the generation pipeline.

---

# Architectural Decisions

## 1. Planner / Writer separation

Instead of one large LLM request:

```text
Prompt → LLM → Note
```

the system uses:

```text
Prompt
  ↓
Planner
  ↓
NotePlan
  ↓
Writer
  ↓
Markdown
```

### Reason

Planning and writing require different kinds of reasoning.

The Planner focuses on:

- information architecture

- relationships

- scope

- section structure

- diagram decisions

The Writer focuses on:

- explanation

- examples

- technical detail

- Markdown

This separation also makes the pipeline easier to test and evolve.

---

## 2. Validator as a separate stage

Validation is deliberately separated from generation.

```text
Writer
  ↓
Validator
```

The system does not blindly trust generated content.

This gives the project an explicit quality-control boundary.

It also allows future validators to be added independently:

```text
Content Validator
Grammar Validator
Link Validator
Markdown Validator
```

without turning the Writer into a monolithic component.

---

## 3. Revision is conditional

Regenerating every note after validation would significantly increase execution time.

Instead:

```text
minor issue
    → keep result

major issue
    → revision

critical issue
    → revision
```

Only serious problems justify another expensive LLM generation.

---

## 4. Vault is the source of truth

SQLite is an index.

Markdown is the actual knowledge base.

This means:

```text
Markdown
    = source of truth

SQLite
    = derived searchable index
```

The index can always be rebuilt.

---

## 5. Obsidian is not coupled to the AI layer

The AI components operate on domain models such as:

```text
NotePlan
VaultContext
ValidationResult
```

rather than directly manipulating Obsidian files.

This prevents the LLM components from becoming tightly coupled to filesystem details.

---

## 6. Ollama is behind an abstraction

The AI pipeline communicates with:

```text
OllamaClient
```

instead of making HTTP requests directly.

This means the project can eventually support another backend without rewriting:

```text
NotePlanner
NoteWriter
NoteValidator
```

---

## 7. Pipeline owns orchestration

`note.py` should not contain logic such as:

```text
if validation failed:
    revise
```

or:

```text
planner → writer → validator
```

That belongs to `NotePipeline`.

The CLI should remain a thin interface around the application.

---

# Performance and Timing

Generation is intentionally multi-stage because quality is more important than minimizing the number of LLM calls.

However, LLM inference is currently the dominant cost.

The Pipeline measures individual stages:

```text
Vault Context
Planner
Writer
Validator
Revision
Final Validation
Save
```

This makes optimization data-driven.

For example:

```text
Vault context     0.4s
Planner          45.2s
Writer          380.1s
Validator       102.4s
Revision          -
Save              0.1s
────────────────────────
Total            528.2s
```

This makes it possible to determine whether optimization should target:

- prompt size

- number of LLM calls

- context size

- output length

- validation

- revision

- model selection

rather than guessing.

---

# Current Data Flow

```text
User
 │
 │ note "topic"
 ▼
note.py
 │
 ▼
NotePipeline
 │
 ├─────────────────────────────┐
 │                             │
 ▼                             ▼
VaultManager              NotePlanner
 │                             │
 ▼                             ▼
VaultContext                NotePlan
 │                             │
 └──────────────┬──────────────┘
                │
                ▼
            NoteWriter
                │
                ▼
          Markdown content
                │
                ▼
          NoteValidator
                │
          ┌─────┴─────┐
          │           │
       minor      major/critical
          │           │
          │           ▼
          │       NoteWriter
          │           │
          │           ▼
          │       Validator
          │           │
          └─────┬─────┘
                │
                ▼
          VaultManager
                │
                ▼
             .md file
                │
                ▼
            GitClient
```

---

# Development Philosophy

This is intentionally a **pet project**, so the architecture aims for a balance between engineering quality and avoiding unnecessary infrastructure.

The project prefers:

- simple abstractions

- explicit responsibilities

- local-first operation

- deterministic data storage

- replaceable infrastructure

- incremental complexity

It intentionally avoids introducing large external systems before they are actually necessary.

For example, SQLite is sufficient for the local Vault index. A dedicated vector database or external search engine would only be justified if semantic retrieval becomes a real bottleneck.

---

# Current Limitations

The project is still under active development.

Known limitations include:

- LLM inference can be slow on larger local models.

- Generated text may still contain grammatical mistakes.

- Validation is not guaranteed to detect every factual error.

- Vault indexing is currently a local derived representation.

- Semantic/vector search is not yet implemented.

- Automatic revision is intentionally limited.

- Obsidian Base is not currently used as the application's database API.

---

# Future Direction

Potential future improvements:

### Retrieval

```text
SQLite metadata index
        +
semantic/vector retrieval
        ↓
better Vault context
```

### Validation

```text
Content Validator
       +
Grammar Validator
       +
Link Validator
       +
Markdown Validator
```

### Generation

Potential improvements include:

- smarter context selection

- adaptive section depth

- better token budgeting

- parallelizable generation where appropriate

- model-specific prompts

- streaming generation/progress reporting

### Obsidian integration

Potential future integrations include:

- richer metadata

- automatic backlinks

- Base-compatible properties

- graph-aware retrieval

- semantic search across the Vault

---

# License

MIT License

---

# Project Goal

The long-term goal is not to build another generic AI text generator.

The goal is to build a **local AI knowledge assistant that incrementally improves an existing Obsidian knowledge base**.

The important distinction is:

```text
Generic AI writer:

Prompt
  ↓
Text


Obsidian Master:

Prompt
  ↓
Existing Knowledge
  ↓
Information Architecture
  ↓
Generated Knowledge
  ↓
Validation
  ↓
Knowledge Graph Integration
  ↓
Obsidian Vault
```

The Vault is therefore not merely the destination for generated text.

It is part of the context used to decide **what should be generated and how the new knowledge should connect to what already exists**.

# Known Issues:

1. **Git push issue**