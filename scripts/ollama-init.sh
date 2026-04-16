#!/bin/sh
# Pulled once at container start; safe to re-run (skips if model already present).
set -e

MODEL="${OLLAMA_MODEL:-gemma4:e2b}"
HOST="${OLLAMA_HOST:-http://ollama:11434}"

echo "[ollama-init] Target model : $MODEL"
echo "[ollama-init] Ollama server: $HOST"

# Wait until Ollama is reachable
until curl -sf "$HOST/api/version" > /dev/null 2>&1; do
    echo "[ollama-init] Waiting for Ollama to be ready..."
    sleep 3
done
echo "[ollama-init] Ollama is up."

# Check whether the model is already present
if curl -sf "$HOST/api/show" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$MODEL\"}" > /dev/null 2>&1; then
    echo "[ollama-init] Model '$MODEL' already present — nothing to do."
    exit 0
fi

echo "[ollama-init] Pulling '$MODEL' (may take a few minutes on first run)..."
curl -s "$HOST/api/pull" \
     -H "Content-Type: application/json" \
     -d "{\"name\":\"$MODEL\",\"stream\":false}" \
     --max-time 1800 | tail -1

echo "[ollama-init] Model '$MODEL' ready."
