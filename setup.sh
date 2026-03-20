#!/usr/bin/env bash
set -e

VENV_DIR=".venv"
OLLAMA_MODEL="llama3.2:1b"

# ── Ollama ────────────────────────────────────────────────────────────────────

if ! command -v ollama &>/dev/null; then
    echo ""
    echo "  Ollama is not installed."
    echo "  Install it first, then re-run this script:"
    echo ""
    echo "    Mac:    brew install ollama"
    echo "    Linux:  curl -fsSL https://ollama.com/install.sh | sh"
    echo "    Windows / other: https://ollama.com"
    echo ""
    exit 1
fi

# Start ollama serve in the background if nothing is already listening on 11434
if ! curl -s http://localhost:11434 &>/dev/null; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    # Give it a moment to come up
    for i in $(seq 1 10); do
        curl -s http://localhost:11434 &>/dev/null && break
        sleep 1
    done
fi

echo "Pulling model $OLLAMA_MODEL (this may take a few minutes on first run)..."
ollama pull "$OLLAMA_MODEL"

# ── Python ────────────────────────────────────────────────────────────────────

echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r requirements.txt

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "  Setup complete. To run:"
echo ""
echo "    source $VENV_DIR/bin/activate"
echo "    python run.py"
echo ""
