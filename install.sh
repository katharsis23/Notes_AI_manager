#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/obsidian-ai-note"
CONFIG_FILE="$CONFIG_DIR/config.json"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== Obsidian AI Note CLI Installer ==="

# 1. Перевірка Python та створення venv
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[1/6] Створення virtualenv..."
    python3 -m venv "$VENV_DIR"
fi

echo "[2/6] Встановлення залежностей..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install httpx rich > /dev/null

# 2. Перевірка Ollama
echo "[3/6] Перевірка локальної Ollama..."
OLLAMA_URL="http://localhost:11434"
if curl -s --head "$OLLAMA_URL" | head -n 1 | grep "200" > /dev/null; then
    echo "✔ Ollama виявлена на $OLLAMA_URL"
    AVAILABLE_MODELS=$(curl -s "$OLLAMA_URL/api/tags" | grep -o '"name":"[^"]*' | cut -d'"' -f4)
    echo "Доступні моделі:"
    echo "$AVAILABLE_MODELS"
else
    echo "⚠ Увага: Ollama не відповідає на $OLLAMA_URL. Переконайся, що сервіс запущено і встановлено."
fi

# 3. Інтерактивна конфігурація LLM та Vault
mkdir -p "$CONFIG_DIR"

read -p "Введіть назву моделі Ollama [qwen2.5:14b]: " CHOSEN_MODEL
CHOSEN_MODEL=${CHOSEN_MODEL:-"qwen2.5:14b"}

read -p "Введіть абсолютний шлях до Obsidian Vault [$HOME/Documents/obsidian/conspects]: " CHOSEN_VAULT
CHOSEN_VAULT=${CHOSEN_VAULT:-"$HOME/Documents/obsidian/conspects"}

# Розгортаємо ~ у повний шлях, якщо користувач ввів ~
CHOSEN_VAULT="${CHOSEN_VAULT/#\~/$HOME}"

# Переконуємось, що папка Vault існує
mkdir -p "$CHOSEN_VAULT"

# 4. Налаштування Git інтеграції
echo "[4/6] Налаштування Git для Vault..."
read -p "Увімкнути авто-коміт та push у Git після створення нотатки? (Y/n): " ENABLE_GIT
ENABLE_GIT=${ENABLE_GIT:-"y"}

AUTO_GIT=false

if [[ "$ENABLE_GIT" =~ ^[Yy]$ ]]; then
    AUTO_GIT=true

    if command -v git &> /dev/null; then
        # Перевіряємо, чи є папка вже git-репозиторієм
        if [ ! -d "$CHOSEN_VAULT/.git" ]; then
            read -p "Vault не є Git-репозиторієм. Ініціалізувати новий Git репозиторій у $CHOSEN_VAULT? (Y/n): " INIT_GIT
            INIT_GIT=${INIT_GIT:-"y"}

            if [[ "$INIT_GIT" =~ ^[Yy]$ ]]; then
                git -C "$CHOSEN_VAULT" init
                git -C "$CHOSEN_VAULT" branch -M main

                # Створюємо базвий .gitignore, щоб не комітити службові кеші Obsidian
                GITIGNORE_FILE="$CHOSEN_VAULT/.gitignore"
                if [ ! -f "$GITIGNORE_FILE" ]; then
                    echo ".obsidian/workspace.json" > "$GITIGNORE_FILE"
                    echo ".obsidian/workspace-mobile.json" >> "$GITIGNORE_FILE"
                    echo ".DS_Store" >> "$GITIGNORE_FILE"
                    echo "✔ Створено базований .gitignore"
                fi

                read -p "Введіть SSH або HTTPS URL вашого GitHub/GitLab репозиторію (натисніть Enter щоб пропустити): " REMOTE_URL
                if [ -n "$REMOTE_URL" ]; then
                    git -C "$CHOSEN_VAULT" remote add origin "$REMOTE_URL"
                    echo "✔ Remote 'origin' успішно додано"
                fi
            fi
        else
            echo "✔ У Vault виявлено існуючий Git-репозиторій."
        fi
    else
        echo "⚠ Git CLI не встановлено в системі. Прапорець auto_git збережено, але рекомендується встановити git."
    fi
fi

# Запис конфігурації разом із auto_git
cat <<EOF > "$CONFIG_FILE"
{
  "model_name": "$CHOSEN_MODEL",
  "ollama_url": "$OLLAMA_URL/api/generate",
  "note_vault": "$CHOSEN_VAULT",
  "auto_git": $AUTO_GIT
}
EOF
echo "✔ Конфігурацію збережено в $CONFIG_FILE"

# 5. Надання прав на виконання note.py
chmod +x "$PROJECT_DIR/note.py"

# 6. Автоматичне додавання аліасів для різних Shell
echo "[5/6] Налаштування аліасів для Shell..."
EXEC_CMD="$VENV_DIR/bin/python3 $PROJECT_DIR/note.py"

# Fish Shell
if command -v fish &> /dev/null; then
    mkdir -p "$HOME/.config/fish/functions"
    cat <<EOF > "$HOME/.config/fish/functions/note.fish"
function note
    $EXEC_CMD \$argv
end
EOF
    echo "✔ Аліас 'note' додано для Fish Shell"
fi

# Bash / Zsh
ALIAS_LINE="alias note='$EXEC_CMD'"

if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "alias note=" "$HOME/.bashrc"; then
        echo "$ALIAS_LINE" >> "$HOME/.bashrc"
        echo "✔ Аліас 'note' додано в ~/.bashrc"
    fi
fi

if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "alias note=" "$HOME/.zshrc"; then
        echo "$ALIAS_LINE" >> "$HOME/.zshrc"
        echo "✔ Аліас 'note' додано в ~/.zshrc"
    fi
fi

echo "=== [6/6] Встановлення завершено! ==="
echo "Конфіг: $CONFIG_FILE"
echo "Auto Git: $AUTO_GIT"
echo "Перезапустіть термінал або виконайте 'source ~/.bashrc' / 'source ~/.zshrc'."