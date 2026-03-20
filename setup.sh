#!/usr/bin/env bash
set -e

VENV_DIR=".venv"
GPT4ALL_MODEL="mistral-7b-openorca.Q4_0.gguf"

echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r requirements.txt

echo ""
echo "Downloading LLM model (~4.1 GB, one-time)..."
echo "This may take a few minutes depending on your connection."
"$VENV_DIR/bin/python" -c "
from gpt4all import GPT4All
GPT4All('$GPT4ALL_MODEL')
print('Model ready.')
"

echo ""
echo "Setup complete. To run:"
echo ""
echo "  source $VENV_DIR/bin/activate"
echo "  python run.py"
echo ""
echo "Or without activating:"
echo "  $VENV_DIR/bin/python run.py"
echo ""
echo "Tests:  $VENV_DIR/bin/pytest tests/ -v"
