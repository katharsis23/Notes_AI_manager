#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/obsidian-ai-note"
CONFIG_FILE="$CONFIG_DIR/config.json"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== Obsidian AI Note CLI Installer ==="

# 1. Checking for python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[1/6] Creating virtualenv..."
    python3 -m venv "$VENV_DIR"
fi

echo "[2/6] Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install httpx rich > /dev/null

# 2. Ollama check
echo "[3/6] Checking Ollama..."
OLLAMA_URL="http://localhost:11434"
if curl -s --head "$OLLAMA_URL" | head -n 1 | grep "200" > /dev/null; then
    echo "✔ Ollama discovered on $OLLAMA_URL"
    AVAILABLE_MODELS=$(curl -s "$OLLAMA_URL/api/tags" | grep -o '"name":"[^"]*' | cut -d'"' -f4)
    echo "Available models:"
    echo "$AVAILABLE_MODELS"
else
    echo "⚠ Warning: Ollama is not responding on $OLLAMA_URL. Check the service is installed and started"
fi

# 3. Interactive map
mkdir -p "$CONFIG_DIR"

read -p "Enter the name of the model [qwen2.5:14b]: " CHOSEN_MODEL
CHOSEN_MODEL=${CHOSEN_MODEL:-"qwen2.5:14b"}

read -p "Enter the absolute path to the note Vault [$HOME/Documents/obsidian/conspects]: " CHOSEN_VAULT
CHOSEN_VAULT=${CHOSEN_VAULT:-"$HOME/Documents/obsidian/conspects"}

CHOSEN_VAULT="${CHOSEN_VAULT/#\~/$HOME}"

mkdir -p "$CHOSEN_VAULT"

# 4. GIT
echo "[4/6] Setting up GIT"
read -p "Enable auto commit and push (Y/n): " ENABLE_GIT
ENABLE_GIT=${ENABLE_GIT:-"y"}

AUTO_GIT=false

if [[ "$ENABLE_GIT" =~ ^[Yy]$ ]]; then
    AUTO_GIT=true

    if command -v git &> /dev/null; then
        if [ ! -d "$CHOSEN_VAULT/.git" ]; then
            read -p "Vault is not a GIT repository. Create one in $CHOSEN_VAULT? (Y/n): " INIT_GIT
            INIT_GIT=${INIT_GIT:-"y"}

            if [[ "$INIT_GIT" =~ ^[Yy]$ ]]; then
                git -C "$CHOSEN_VAULT" init
                git -C "$CHOSEN_VAULT" branch -M main

                GITIGNORE_FILE="$CHOSEN_VAULT/.gitignore"
                if [ ! -f "$GITIGNORE_FILE" ]; then
                    echo ".obsidian/workspace.json" > "$GITIGNORE_FILE"
                    echo ".obsidian/workspace-mobile.json" >> "$GITIGNORE_FILE"
                    echo ".DS_Store" >> "$GITIGNORE_FILE"
                    echo "✔ Created .gitignore"
                fi

                read -p "Enter url to your remote repository (Enter to skip): " REMOTE_URL
                if [ -n "$REMOTE_URL" ]; then
                    git -C "$CHOSEN_VAULT" remote add origin "$REMOTE_URL"
                    echo "✔ Remote 'origin' has added"
                fi
            fi
        else
            echo "✔ Vault has already remote repository"
        fi
    else
        echo "⚠ Git CLI is not installed "
    fi
fi

cat <<EOF > "$CONFIG_FILE"
{
  "model_name": "$CHOSEN_MODEL",
  "ollama_url": "$OLLAMA_URL/api/generate",
  "note_vault": "$CHOSEN_VAULT",
  "auto_git": $AUTO_GIT
}
EOF
echo "✔ Saving configuration $CONFIG_FILE"

chmod +x "$PROJECT_DIR/note.py"

# 6 Aliasing for different shells
echo "[5/6] Setting alias for..."
EXEC_CMD="$VENV_DIR/bin/python3 $PROJECT_DIR/note.py"

# Fish Shell
if command -v fish &> /dev/null; then
    mkdir -p "$HOME/.config/fish/functions"
    cat <<EOF > "$HOME/.config/fish/functions/note.fish"
function note
    $EXEC_CMD \$argv
end
EOF
    echo "✔ Alias 'note' added for Fish Shell"
fi

# Bash / Zsh
ALIAS_LINE="alias note='$EXEC_CMD'"

if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "alias note=" "$HOME/.bashrc"; then
        echo "$ALIAS_LINE" >> "$HOME/.bashrc"
        echo "✔ Alias 'note' added in ~/.bashrc"
    fi
fi

if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "alias note=" "$HOME/.zshrc"; then
        echo "$ALIAS_LINE" >> "$HOME/.zshrc"
        echo "✔ Alias 'note' is added in ~/.zshrc"
    fi
fi

echo "=== [6/6] Success ==="
echo "Конфіг: $CONFIG_FILE"
echo "Auto Git: $AUTO_GIT"
echo "Restart your terminal 'source ~/.bashrc' / 'source ~/.zshrc'."