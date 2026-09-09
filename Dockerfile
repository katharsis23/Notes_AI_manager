FROM python:3.14.7-trixie


RUN useradd -u 1000 -m -s /bin/bash note_manager

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=note_manager:note_manager . .

RUN mkdir -p /home/note_manager/.config/obsidian-ai-note && \
    chown -R note_manager:note_manager /home/note_manager/.config

RUN mkdir -p /vault && chown -R note_manager:note_manager /vault

USER note_manager

ENV OLLAMA_URL="http://host.docker.internal:11434"
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD []