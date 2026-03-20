# CeroDias

A simulated vulnerable company website for hands-on penetration testing practice. Looks and behaves like a real company. Each vulnerability you find unlocks the next step.

> **Spoiler warning:** If you are here to play, stop reading now and go to `http://localhost:5001`.

---

## Setup

**Step 1 — Install Ollama** (the free, local AI that powers the CERA chatbot)

- Mac: `brew install ollama`
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`
- Windows / other: [ollama.com](https://ollama.com)

**Step 2 — Run the setup script** (handles everything else automatically)

```bash
bash setup.sh
```

This pulls the AI model (~1.3 GB, one-time) and installs all dependencies.

**Step 3 — Run**

```bash
source .venv/bin/activate
python run.py
```

Visit `http://localhost:5001`. No accounts, no API keys, no billing.

---

## Troubleshooting

**"CERA is disabled" in the terminal**
Ollama isn't running. Fix: `ollama serve` in a separate terminal, then restart the server.

**setup.sh says Ollama is not installed**
Complete Step 1 first, then re-run `bash setup.sh`.

---

## Docker (optional, for the final two steps of the chain)

```bash
mkdir -p data && docker-compose up --build
```

Web: `http://localhost:5001` — SSH: `localhost:2222`

---

## Tests

```bash
pytest tests/ -v
```

---

## Config (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `llama3.2` | Model to use |
| `PORT` | `5001` | Port the server listens on |
