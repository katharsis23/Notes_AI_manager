#!/bin/bash
set -e

CONFIG_PATH="/home/note_manager/.config/obsidian-ai-note/config.json"


if ! curl -s --head "$OLLAMA_URL" | grep "200" > /dev/null; then
    echo "⚠ Warning: Ollama is not responding on $OLLAMA_URL" >&2
fi

exec python3 -m note "$@"