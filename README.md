
# 🚀 Obsidian Master AI CLI

**Obsidian Master** is a local CLI utility designed to automate the generation of structured, in-depth technical and conceptual Markdown notes for [Obsidian](https://obsidian.md/).

The tool uses local Large Language Models (LLMs) via **Ollama** (defaulting to `qwen2.5:14b`), scans your existing Vault for tags and cross-linking candidates, performs a two-stage content generation, and automatically commits/pushes updates to your Git repository.

---

## 🛠️ Environment Requirements

- **OS:** Linux / macOS
- **Python:** 3.10+ (uses `venv`)
- **Ollama:** Locally running service (`http://localhost:11434`)
- **Git:** (Optional) For automated Vault version control

---

## 📥 Installation & Setup

A fast deployment interactive BASH script `install.sh` is provided within the repository.

### 1. Clone / Prepare Repository

```bash
git clone <your-repo-url> ~/note
cd ~/note

```

### 2. Run the Installer

Make the script executable and run it:

```bash
chmod +x install.sh
./install.sh

```

**What `install.sh` does during execution:**

1. Creates an isolated Python virtual environment (`venv/`).
2. Installs required dependencies (`httpx`, `rich`).
3. Checks the status of the local Ollama server and lists available models.
4. Prompts for configuration parameters (model name, path to your Obsidian Vault) and generates `~/.config/obsidian-ai-note/config.json`.
5. Interactively sets up Git (initializes `.git` in the Vault, creates a default `.gitignore`, and adds a remote origin if requested).
6. Automatically registers the `note` alias/function for your shell (**Fish**, **Bash**, or **Zsh**).

### 3. Reload Shell Session

Once the installation finishes, restart your terminal or run:

```bash
source ~/.bashrc  # For Bash
# or
source ~/.zshrc   # For Zsh

```

---

## 💻 Usage

Generate a new note with a single command from anywhere in your system:

```bash
note "Nihilism, existentialism, absurdism. Differences and common traits"

```

Or for technical topics:

```bash
note "PostgreSQL Query Optimization and B-Tree Indexes"

```

---

## 📐 Architecture & File Overview

The project is built around **Single Responsibility** and **Clean Architecture** principles, separating configuration, I/O scanning, low-level network communication, content generation, and version control.

```text
.
├── config.json         # Local configuration file (generated during setup)
├── config.py           # Settings loading and validation module
├── generator.py        # Two-stage LLM generation orchestration logic
├── git_client.py       # Git interaction module (add, commit, push)
├── install.sh          # Interactive installation and setup Bash script
├── llm.py              # Async HTTP client for Ollama API (httpx)
├── note.py             # CLI entry point (argument parsing, rich UI)
├── requirements.txt    # List of external Python dependencies
├── vault.py            # I/O module for Obsidian Vault and YAML Frontmatter operations
└── venv/               # Isolated Python virtual environment

```

---

### 🔍 Detailed File Roles

#### 1. `note.py` (CLI Entry Point / Orchestrator)

The main executable file of the application.

* Accepts the note topic from command-line arguments (`sys.argv`).
* Initializes all core components (`Config`, `VaultManager`, `OllamaClient`, `NoteGenerator`).
* Manages interactive terminal progress indicators using the `rich` library.
* Coordinates the execution pipeline: **Scan Vault $\rightarrow$ Generate Note $\rightarrow$ Save $\rightarrow$ Git Commit**.

#### 2. `config.py`

Handles application configuration management.

* Reads settings from `~/.config/obsidian-ai-note/config.json`.
* Stores parameters such as `model_name`, `ollama_url`, `note_vault` (Vault directory path), and the `auto_git` flag.
* Provides default fallbacks in case configuration settings are missing.

#### 3. `llm.py`

A low-level asynchronous HTTP client communicating with the local Ollama model.

* Utilizes `httpx.AsyncClient` configured with custom timeouts (`Timeout(600.0, connect=15.0)`), preventing `ReadTimeout` exceptions during heavy inference.
* Supports setting context window size (`num_ctx`), temperature adjustments, and switching between JSON and Raw Text modes.

#### 4. `generator.py`

The primary generation engine. Implements a two-stage pipeline to ensure high-quality output:

* **Stage 1 (Plan & Metadata):** Accepts the topic, existing Vault tags, and file names. Returns JSON with the note title, folder location, matching tags, backlinks, and a structured section outline.
* **Stage 2 (Full Body Generation):** Prompts the model with the generated outline to write a complete, in-depth Markdown document natively weaving in `[[WikiLinks]]`.

#### 5. `vault.py`

Manages context scanning and note file persistence (I/O).

* **`get_existing_context()`**: Recursively scans the Vault and parses YAML frontmatter across all `.md` files to extract existing tags and cross-linking targets.
* **`save_note()`**: Constructs valid YAML Frontmatter (ensuring correct indentation without leading spaces before `---`), strips duplicate H1 headers, and saves the file to its targeted directory inside the Vault. Triggers Git integration after saving.

#### 6. `git_client.py`

Automates Vault versioning.

* Runs system `git` commands directly in the Vault directory using Python's `subprocess`.
* Executes the lifecycle: `git add <file>` $\rightarrow$ `git commit -m "..."` $\rightarrow$ `git push`.
* Validates repository state and safely handles network errors during push operations.

#### 7. `install.sh`

An automation shell script for rapid deployment on Linux/macOS environments, managing shell alias registrations and Git initialization.

#### 8. `config.json`

A JSON configuration file generated during installation containing current paths, model options, and auto-git flags.

```json
{
  "model_name": "qwen2.5:14b",
  "ollama_url": "http://localhost:11434/api/generate",
  "note_vault": "/home/user/Documents/obsidian/conspects",
  "auto_git": true
}

```

---

## ⚙️ Data Flow Architecture

```text
[User CLI Input]
       │
       ▼
  note.py ───> config.py (Load Configuration)
       │
       ├───> vault.py (Scan Tags & Context Files)
       │
       ├───> generator.py + llm.py ───> [Ollama API]
       │         ├── 1. Generate Metadata JSON & Plan
       │         └── 2. Generate Full Markdown Content
       │
       ├───> vault.py (Write .md file with Frontmatter into Vault)
       │
       └───> git_client.py (Git Add -> Commit -> Push)

```

```

