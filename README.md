# CeroDias

A simulated vulnerable company website for penetration testing education. Not a
trophy-based CTF: it replicates a realistic attack surface where each vulnerability
yields information or access that enables the next step.

## What It Is

CeroDias Enterprise Solutions is a fake IT certification voucher company. The platform
has two layers:

- **Formal challenges**: structured, scored SQL injection exercises (Easy and Medium)
- **Easter egg chain**: a single realistic attack path through the app - no flag strings,
  no hand-holding, real tooling required

The Easter egg chain mirrors an actual incident: an anonymous visitor can reach a server
shell by chaining SSTI, SQLi, an upload bypass, and a filesystem read into an SSH key
decryption.

## Quick Start

```bash
pip install -r requirements.txt
python run.py
```

Visit `http://localhost:5000`.

To enable real prompt injection (requires Ollama):

```bash
ollama pull mistral
LLM_MODEL=ollama OLLAMA_MODEL=mistral python run.py
```

## Running Tests

```bash
pytest tests/ -v
# 126 passing, 1 pre-existing chatbot keyword failure (known, see test_llm_interface.py)
```

## The Attack Chain

```
Recon       robots.txt, .git/COMMIT_EDITMSG, IDOR /orders/1
                yields: svc_admin username, /api/v1/users endpoint

Chatbot     optional - jailbreak the LLM to get the internal roadmap from info.md

SSTI        /search?q={{...}}
                reads app/api/users.py   - SQLi endpoint + MD5 hint + staff_messages
                reads app/logs/deploy.log - passphrase file path on server

SQLi        /api/v1/users?q=...
                OR injection  - user table: svc_admin encrypted_ssh_key blob + j.harris MD5
                UNION inject  - staff_messages table: k.chen DM confirms blob + path

Upload RCE  POST /account/settings/avatar
                shell.png.php with PNG magic bytes - substring ext check bypassed
                GET /static/uploads/shell.png.php?cmd=cat /var/cerodias/deploy.key

Decrypt     base64_decode(blob) piped through openssl enc -d -aes-256-cbc -pbkdf2

SSH         ssh -i id_rsa svc_admin@server   [Docker - future]
```

Parallel path: crack j.harris MD5 (password: `ranger`, rockyou instant) then login
and read `/messages` for the same k.chen DM without needing the UNION injection.

Optional hard path (not on main chain): crack svc_admin bcrypt/12 + decrypt TOTP seed
via SSTI source read. See `app/core/totp_util.py`.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_MODEL` | `ollama` | `ollama` uses Ollama locally, `mock` uses pattern matching |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | Model to use |

## Project Structure

```
CeroDias/
├── app/
│   ├── __init__.py               Flask factory + SSH key seeding at startup
│   ├── config.py                 SECRET_KEY (static, intentional), DEBUG=True
│   ├── routes/
│   │   ├── auth.py               /, /register, /logout, /robots.txt, /.git/*
│   │   ├── account.py            /account  (Tier 2)
│   │   ├── orders.py             /orders/id  (IDOR - no ownership check)
│   │   ├── purchase.py           /purchase  (debug crash - negative quantity)
│   │   ├── search.py             /search  (SSTI)
│   │   ├── settings.py           /account/settings  (PHP upload bypass + RCE)
│   │   ├── messages.py           /messages  (staff inbox - j.harris parallel path)
│   │   ├── chatbot.py            /chat
│   │   ├── challenges.py         /challenge/type/difficulty
│   │   ├── submit.py             /submit
│   │   ├── dashboard.py          /dashboard, /leaderboard
│   │   └── admin.py              /admin
│   ├── api/
│   │   └── users.py              /api/v1/users  (SQLi - f-string + space WAF)
│   ├── internal/
│   │   └── panel.py              /internal-panel  (bcrypt + TOTP - optional hard path)
│   ├── core/
│   │   ├── llm_interface.py      Ollama (falls back to mock)
│   │   ├── chatbot_engine.py     Chatbot logic
│   │   ├── totp_util.py          AES-128-ECB TOTP decrypt (optional path target)
│   │   └── ...                   challenge engine, scoring, session, flags
│   ├── storage/
│   │   └── memory_store.py       Singleton: players, user_table, staff_messages, orders
│   ├── data/
│   │   ├── info.md               Public + internal sections (LLM system prompt)
│   │   └── logs/deploy.log       Seeded log - DEBUG line leaks passphrase path
│   ├── templates/
│   │   ├── base.html, index.html, login.html, account.html
│   │   ├── settings.html         Profile picture upload (PHP bypass surface)
│   │   ├── messages.html         Staff inbox (j.harris parallel path)
│   │   └── ...
│   └── static/
│       ├── css/style.css
│       ├── js/main.js            innerHTML bot responses (XSS surface)
│       └── uploads/              PHP webshells land here
├── tests/
│   ├── conftest.py               Shared fixtures (client, authed_client, harris_client)
│   ├── test_chain_recon.py       Recon: robots.txt, .git, IDOR
│   ├── test_chain_ssti.py        SSTI: arithmetic, file read, deploy.log
│   ├── test_chain_sqli.py        SQLi: OR dump, j.harris MD5, UNION pivot, k.chen DM
│   ├── test_chain_rce.py         Upload bypass, shell.png.php, cmd execution
│   ├── test_chain_messages.py    Legacy login, staff session, inbox content
│   ├── test_sqli.py              SQLi endpoint baseline
│   ├── test_ssti.py              SSTI baseline
│   ├── test_integration.py       Full player workflows
│   └── ...                       flag gen, scoring, vulnerability, LLM tests
├── story.md                      Narrative of the incident (read this first)
├── HACKING.md                    Developer chain walkthrough - step by step
├── CHAIN_IMPLEMENTATION.md       Four-agent implementation spec
├── ARCHITECTURE.md               System design and data flows
└── CLAUDE.md                     Instructions for AI agents working on this project
```

## Intentional Vulnerabilities

Do not fix these. They are the education.

| Location | Vulnerability |
|----------|--------------|
| `app/routes/search.py` | SSTI via `render_template_string` f-string |
| `app/api/users.py` | SQLi via f-string + space WAF + UNION pivot |
| `app/routes/settings.py` | PHP upload - substring ext check, .php execution |
| `app/storage/memory_store.py` | j.harris MD5 hash; staff_messages co-located |
| `app/routes/auth.py` | .git directory exposure |
| `app/routes/orders.py` | IDOR - no ownership check |
| `app/routes/purchase.py` | Debug crash - Werkzeug interactive debugger |
| `app/core/llm_interface.py` | Full internal docs in LLM system prompt |
| `app/static/js/main.js` | Raw innerHTML for bot responses |

## What is Not a Vulnerability

- Session cookie manipulation: `/internal-panel` validates bcrypt + TOTP server-side
- Cracking svc_admin bcrypt: password not in rockyou, no hint remaining
- `.git/` files: hint at endpoints, no credentials or SECRET_KEY
- `/admin` panel: resets the game, not the crown jewel

## Dependencies

```
Flask, pytest, cryptography, bcrypt, pycryptodome, pyotp, requests
openssl (system binary - required for SSH key encryption at startup)
ollama (optional - for real prompt injection)
```

## What Comes Next

Steps 6 and 7 (SSH access and SUID privesc) require Docker. A `docker-compose.yml`
that wires the Flask app to an SSH-enabled container with a SUID binary is the
remaining piece. See `HACKING.md` for the full chain walkthrough including those steps.
