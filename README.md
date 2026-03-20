# CeroDias

A simulated vulnerable company website for penetration testing education. Not a flag-based CTF — each vulnerability yields information or access that enables the next step.

> **Spoiler warning:** Do not read source files, browse the repo, or read any docs beyond this README. The app is an interactive puzzle. Discovering the attack surface yourself is the point.

## Setup

```bash
bash setup.sh
```

Downloads all dependencies and the LLM model (~4.1 GB, one-time). Then:

```bash
source .venv/bin/activate
python run.py
```

Visit `http://localhost:5001`. The chatbot is live and ready for prompt injection.

## Full chain (Docker)

Steps 0-5 run without Docker. For SSH access and privilege escalation (Steps 6-7):

```bash
mkdir -p data
docker-compose up --build
# Web: http://localhost:5001   SSH: localhost:2222
```

## Tests

```bash
pytest tests/ -v
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_MODEL` | `auto` | `auto` tries Ollama then GPT4All; `ollama` forces Ollama; `gpt4all` forces GPT4All |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | Ollama model name |
| `GPT4ALL_MODEL` | `mistral-7b-openorca.Q4_0.gguf` | GPT4All model file |
